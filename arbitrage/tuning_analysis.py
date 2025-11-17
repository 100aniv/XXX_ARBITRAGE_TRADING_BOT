# -*- coding: utf-8 -*-
"""
D26 Tuning Analysis & Visualization

튜닝 결과 분석, 요약, 랭킹 기능.
"""

import csv
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TuningResult:
    """튜닝 결과"""
    session_id: str
    worker_id: str
    iteration: int
    params: Dict[str, Any]
    metrics: Dict[str, Any]
    timestamp: str
    status: str = "completed"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "session_id": self.session_id,
            "worker_id": self.worker_id,
            "iteration": self.iteration,
            "params": self.params,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "status": self.status
        }


class TuningAnalyzer:
    """튜닝 결과 분석"""
    
    def __init__(self, results: List[TuningResult]):
        """
        Args:
            results: 튜닝 결과 리스트
        """
        self.results = results
    
    def summarize(self) -> Dict[str, Any]:
        """
        결과 요약
        
        Returns:
            요약 딕셔너리
        """
        if not self.results:
            return {
                "total_iterations": 0,
                "total_workers": 0,
                "unique_sessions": 0,
                "metrics_keys": [],
                "param_keys": []
            }
        
        # 세션 및 워커 정보
        sessions = set(r.session_id for r in self.results)
        workers = set(r.worker_id for r in self.results)
        
        # 메트릭 및 파라미터 키
        metrics_keys = set()
        param_keys = set()
        
        for result in self.results:
            metrics_keys.update(result.metrics.keys())
            param_keys.update(result.params.keys())
        
        return {
            "total_iterations": len(self.results),
            "total_workers": len(workers),
            "unique_sessions": len(sessions),
            "metrics_keys": sorted(list(metrics_keys)),
            "param_keys": sorted(list(param_keys)),
            "workers": sorted(list(workers)),
            "sessions": sorted(list(sessions))
        }
    
    def rank_by_metric(
        self,
        metric_name: str,
        top_n: int = 5,
        ascending: bool = False
    ) -> List[TuningResult]:
        """
        특정 메트릭 기준 랭킹
        
        Args:
            metric_name: 메트릭 이름
            top_n: 상위 N개
            ascending: 오름차순 정렬 (기본: 내림차순)
        
        Returns:
            정렬된 결과 리스트
        """
        # 메트릭이 있는 결과만 필터링
        valid_results = [
            r for r in self.results
            if metric_name in r.metrics
        ]
        
        if not valid_results:
            logger.warning(f"No results with metric '{metric_name}'")
            return []
        
        # 정렬
        sorted_results = sorted(
            valid_results,
            key=lambda r: r.metrics[metric_name],
            reverse=not ascending
        )
        
        return sorted_results[:top_n]
    
    def get_best_params(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        최고 성능 파라미터 조합 반환
        
        Args:
            metric_name: 메트릭 이름
        
        Returns:
            최고 성능 파라미터 또는 None
        """
        ranked = self.rank_by_metric(metric_name, top_n=1, ascending=False)
        if ranked:
            return ranked[0].params
        return None


def load_results_from_csv(csv_path: str) -> List[TuningResult]:
    """
    CSV 파일에서 튜닝 결과 로드
    
    Args:
        csv_path: CSV 파일 경로
    
    Returns:
        TuningResult 리스트
    """
    results = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # 기본 필드
                session_id = row.get('session_id', '')
                iteration = int(row.get('iteration', 0))
                status = row.get('status', 'completed')
                timestamp = row.get('timestamp', '')
                worker_id = row.get('worker_id', 'main')
                
                # params와 metrics는 CSV에서는 간단히 저장되므로
                # 실제 구조는 Redis에서 가져오거나 별도 처리 필요
                # 여기서는 기본 구조만 로드
                params = {}
                metrics = {}
                
                result = TuningResult(
                    session_id=session_id,
                    worker_id=worker_id,
                    iteration=iteration,
                    params=params,
                    metrics=metrics,
                    timestamp=timestamp,
                    status=status
                )
                
                results.append(result)
        
        logger.info(f"Loaded {len(results)} results from {csv_path}")
        return results
    
    except Exception as e:
        logger.error(f"Failed to load results from CSV: {e}")
        return []


def format_result_summary(result: TuningResult) -> str:
    """
    결과를 포맷된 문자열로 변환
    
    Args:
        result: 튜닝 결과
    
    Returns:
        포맷된 문자열
    """
    params_str = ", ".join(
        f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in result.params.items()
    )
    
    metrics_str = ", ".join(
        f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in result.metrics.items()
    )
    
    return f"Iteration {result.iteration}: params=[{params_str}] metrics=[{metrics_str}]"
