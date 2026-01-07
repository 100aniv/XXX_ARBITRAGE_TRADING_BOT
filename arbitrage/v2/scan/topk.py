"""
D205-15: TopK Selector

TopK 심볼 선정기 (Fix-4: mean_net_edge_bps + positive_rate 기반)
- mean_spread_bps 대신 mean_net_edge_bps 사용
- positive_rate도 선정 기준에 포함
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class TopKSelector:
    """
    TopK Selector (D205-15 Fix-4)
    
    수익성 기반 TopK 심볼 선정
    - Primary: mean_net_edge_bps (실제 순이익)
    - Secondary: positive_rate (수익 확률)
    
    Args:
        topk: 선정할 심볼 수
        min_positive_rate: 최소 positive_rate (기본: 0.0)
    """
    
    def __init__(self, topk: int = 3, min_positive_rate: float = 0.0):
        self.topk = topk
        self.min_positive_rate = min_positive_rate
        
        logger.info(
            f"[D205-15_TOPK] Initialized: topk={topk}, min_positive_rate={min_positive_rate}"
        )
    
    def select(
        self,
        symbol_metrics: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        TopK 심볼 선정 (Fix-4: mean_net_edge_bps + positive_rate 기반)
        
        Args:
            symbol_metrics: 심볼별 메트릭 리스트
        
        Returns:
            (topk_symbols, ranking) 튜플
        """
        # Filter: status == "calculated" only
        valid_metrics = [
            m for m in symbol_metrics
            if m.get("status") == "calculated" and "metrics" in m
        ]
        
        if not valid_metrics:
            logger.warning("[D205-15_TOPK] No valid metrics for TopK selection")
            return [], []
        
        # Filter: min_positive_rate 충족
        if self.min_positive_rate > 0:
            filtered = [
                m for m in valid_metrics
                if m["metrics"].get("positive_rate", 0) >= self.min_positive_rate
            ]
            if filtered:
                valid_metrics = filtered
                logger.info(
                    f"[D205-15_TOPK] Filtered by positive_rate >= {self.min_positive_rate}: "
                    f"{len(filtered)}/{len(symbol_metrics)} symbols"
                )
        
        # Fix-4: Sort by mean_net_edge_bps (primary) + positive_rate (secondary)
        # 정렬 기준:
        # 1. mean_net_edge_bps descending (높을수록 좋음)
        # 2. positive_rate descending (높을수록 좋음)
        sorted_metrics = sorted(
            valid_metrics,
            key=lambda x: (
                x["metrics"].get("mean_net_edge_bps", float("-inf")),
                x["metrics"].get("positive_rate", 0),
            ),
            reverse=True
        )
        
        # Build ranking
        ranking = []
        for i, m in enumerate(sorted_metrics):
            ranking.append({
                "rank": i + 1,
                "symbol": m["symbol"],
                "mean_net_edge_bps": m["metrics"].get("mean_net_edge_bps", 0),
                "positive_rate": m["metrics"].get("positive_rate", 0),
                "mean_spread_bps": m["metrics"].get("mean_spread_bps", 0),
            })
        
        # Select TopK
        topk_symbols = [r["symbol"] for r in ranking[:self.topk]]
        
        logger.info(
            f"[D205-15_TOPK] Selected {len(topk_symbols)} symbols: {topk_symbols}"
        )
        
        for r in ranking[:self.topk]:
            logger.info(
                f"[D205-15_TOPK] #{r['rank']} {r['symbol']}: "
                f"net_edge={r['mean_net_edge_bps']:.2f}bps, "
                f"positive_rate={r['positive_rate']:.2%}"
            )
        
        return topk_symbols, ranking
    
    def create_scan_summary(
        self,
        output_dir_name: str,
        duration_minutes: int,
        symbol_metrics: List[Dict[str, Any]],
        topk_symbols: List[str],
        ranking: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Scan Summary 생성
        
        Args:
            output_dir_name: 출력 디렉토리 이름
            duration_minutes: 기록 시간 (분)
            symbol_metrics: 심볼별 메트릭 리스트
            topk_symbols: 선정된 TopK 심볼
            ranking: 전체 랭킹
        
        Returns:
            scan_summary 딕셔너리
        """
        from datetime import datetime
        
        return {
            "scan_id": output_dir_name,
            "timestamp": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "symbols": symbol_metrics,
            "ranking": ranking,
            "topk_selection": {
                "topk": self.topk,
                "selected": topk_symbols,
                "selection_criteria": "mean_net_edge_bps descending + positive_rate",  # Fix-4
                "min_positive_rate_filter": self.min_positive_rate,
            }
        }
