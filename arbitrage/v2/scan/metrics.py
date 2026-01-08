"""
D205-15: Scan Metrics Calculator

메트릭 계산기 (Fix-3: Config-driven costs + D205-15-3: Directional/Executable KPI)
- Config에서 fee/slippage/fx_conversion 로드
- FX 정규화된 데이터 기반 spread/edge 계산
- D205-15-3: Directional/Executable spread 추가 (방향성 반영)
- D205-15-3: tradeable_rate 추가 (Upbit BUY + Binance SHORT만 tradeable)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from statistics import mean, median
import numpy as np

from arbitrage.v2.scan.scanner import ScanConfig

logger = logging.getLogger(__name__)


class ScanMetricsCalculator:
    """
    Scan Metrics Calculator (D205-15 Fix-3)
    
    Config SSOT 기반 비용 모델 적용
    
    Args:
        scan_config: ScanConfig (fees, slippage, fx_conversion 포함)
    """
    
    def __init__(self, scan_config: ScanConfig):
        self.scan_config = scan_config
        
        # Config에서 비용 파라미터 계산
        self.upbit_fee_bps = scan_config.upbit_fee_bps
        self.binance_fee_bps = scan_config.binance_fee_bps
        self.total_fee_bps = self.upbit_fee_bps + self.binance_fee_bps
        self.slippage_bps = scan_config.slippage_bps
        self.fx_conversion_bps = scan_config.fx_conversion_bps
        self.buffer_bps = scan_config.buffer_bps
        self.total_cost_bps = (
            self.total_fee_bps + 
            self.slippage_bps + 
            self.fx_conversion_bps + 
            self.buffer_bps
        )
        
        logger.info(
            f"[D205-15_METRICS] Initialized: "
            f"total_cost={self.total_cost_bps}bps "
            f"(fees={self.total_fee_bps}, slip={self.slippage_bps}, "
            f"fx={self.fx_conversion_bps}, buffer={self.buffer_bps})"
        )
    
    def calculate_symbol_metrics(
        self,
        market_file: Path,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        심볼별 메트릭 계산 (Fix-3: Config-driven)
        
        Args:
            market_file: market.ndjson 파일 경로
            symbol: 심볼 이름
        
        Returns:
            메트릭 딕셔너리
        """
        if not market_file.exists():
            return {
                "symbol": symbol,
                "status": "no_data",
                "skip_reason": "market_file_not_found",
            }
        
        ticks = []
        with open(market_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    tick_dict = json.loads(line)
                    ticks.append(tick_dict)
                except json.JSONDecodeError:
                    continue
        
        if not ticks:
            return {
                "symbol": symbol,
                "status": "empty",
                "skip_reason": "no_valid_ticks",
            }
        
        spreads = []
        raw_edges = []
        net_edges = []
        
        # D205-15-3: Directional/Executable KPI 추가
        executable_spreads = []
        executable_edges = []
        tradeable_flags = []
        
        for tick in ticks:
            # FX가 이미 정규화된 데이터 사용 (둘 다 KRW)
            upbit_mid = (tick["upbit_bid"] + tick["upbit_ask"]) / 2.0
            binance_mid = (tick["binance_bid"] + tick["binance_ask"]) / 2.0
            
            if upbit_mid <= 0 or binance_mid <= 0:
                continue
            
            # 기존: Spread 계산 (abs mid 기반 - diagnostic용으로 유지)
            spread_abs = abs(upbit_mid - binance_mid)
            spread_bps = (spread_abs / upbit_mid) * 10000
            
            # Edge 계산 (Config-driven costs)
            raw_edge_bps = spread_bps - self.total_fee_bps
            net_edge_bps = raw_edge_bps - self.slippage_bps - self.fx_conversion_bps - self.buffer_bps
            
            spreads.append(spread_bps)
            raw_edges.append(raw_edge_bps)
            net_edges.append(net_edge_bps)
            
            # D205-15-3: Directional/Executable spread 계산
            # 방향성: Upbit BUY @ask + Binance FUTURES SHORT @bid
            # executable_spread = (binance_bid - upbit_ask) / upbit_ask * 10000
            upbit_ask = tick["upbit_ask"]
            binance_bid = tick["binance_bid"]
            
            if upbit_ask > 0:
                executable_spread_bps = ((binance_bid - upbit_ask) / upbit_ask) * 10000
            else:
                executable_spread_bps = 0.0
            
            # Executable edge (비용 차감)
            executable_raw_edge_bps = executable_spread_bps - self.total_fee_bps
            executable_net_edge_bps = executable_raw_edge_bps - self.slippage_bps - self.fx_conversion_bps - self.buffer_bps
            
            executable_spreads.append(executable_spread_bps)
            executable_edges.append(executable_net_edge_bps)
            
            # tradeable = executable_net_edge > 0 (실제 수익 가능)
            is_tradeable = executable_net_edge_bps > 0
            tradeable_flags.append(is_tradeable)
        
        if not spreads:
            return {
                "symbol": symbol,
                "status": "invalid_data",
                "skip_reason": "all_ticks_invalid",
            }
        
        # Fix-4 지표: positive_rate 계산 (abs mid 기반 - diagnostic)
        positive_count = sum(1 for edge in net_edges if edge > 0)
        positive_rate = positive_count / len(net_edges) if net_edges else 0.0
        
        # D205-15-3: tradeable_rate 계산 (Directional/Executable 기반 - 실제 수익성)
        tradeable_count = sum(tradeable_flags)
        tradeable_rate = tradeable_count / len(tradeable_flags) if tradeable_flags else 0.0
        
        # D205-15-3: Executable KPI 통계
        exec_stats = {}
        if executable_edges:
            exec_stats = {
                "mean_executable_spread_bps": round(mean(executable_spreads), 4),
                "mean_executable_edge_bps": round(mean(executable_edges), 4),
                "median_executable_edge_bps": round(median(executable_edges), 4),
                "min_executable_edge_bps": round(min(executable_edges), 4),
                "max_executable_edge_bps": round(max(executable_edges), 4),
                "std_executable_edge_bps": round(float(np.std(executable_edges)), 4),
            }
        
        return {
            "symbol": symbol,
            "status": "calculated",
            "tick_count": len(ticks),
            "valid_tick_count": len(spreads),
            "metrics": {
                # 기존 (abs mid 기반 - diagnostic으로 유지)
                "mean_spread_bps": round(mean(spreads), 4),
                "median_spread_bps": round(median(spreads), 4),
                "p90_spread_bps": round(float(np.percentile(spreads, 90)), 4),
                "mean_raw_edge_bps": round(mean(raw_edges), 4),
                "mean_net_edge_bps": round(mean(net_edges), 4),  # diagnostic
                "median_net_edge_bps": round(median(net_edges), 4),
                "p90_net_edge_bps": round(float(np.percentile(net_edges, 90)), 4),
                "positive_rate": round(positive_rate, 4),  # diagnostic
                "positive_count": positive_count,
                # D205-15-3: Directional/Executable KPI (실제 수익성 판단 기준)
                **exec_stats,
                "tradeable_rate": round(tradeable_rate, 4),  # 핵심 KPI
                "tradeable_count": tradeable_count,
            },
            "cost_breakdown": {
                "upbit_fee_bps": self.upbit_fee_bps,
                "binance_fee_bps": self.binance_fee_bps,
                "total_fee_bps": self.total_fee_bps,
                "slippage_bps": self.slippage_bps,
                "fx_conversion_bps": self.fx_conversion_bps,
                "buffer_bps": self.buffer_bps,
                "total_cost_bps": self.total_cost_bps,
                "source": "config/v2/config.yml (SSOT)",
            },
            "kpi_note": "D205-15-3: executable_edge_bps = Directional (Upbit BUY @ask + Binance SHORT @bid)",
        }
    
    def calculate_all_metrics(
        self,
        output_dir: Path,
        recording_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        전체 심볼 메트릭 계산
        
        Args:
            output_dir: 출력 디렉토리
            recording_results: Recording 결과 리스트
        
        Returns:
            메트릭 리스트
        """
        metrics_list = []
        
        for rec_result in recording_results:
            if rec_result.get("status") != "completed":
                metrics_list.append({
                    "symbol": rec_result.get("symbol", "unknown"),
                    "status": "skipped",
                    "skip_reason": rec_result.get("skip_reason", "recording_failed"),
                })
                continue
            
            symbol = rec_result["symbol"]
            symbol_safe = symbol.replace("/", "_")
            market_file = output_dir / symbol_safe / "market.ndjson"
            
            metrics = self.calculate_symbol_metrics(market_file, symbol)
            metrics_list.append(metrics)
        
        return metrics_list


def create_scan_config_from_v2_config(config, fx_krw_per_usdt: float) -> ScanConfig:
    """
    V2Config에서 ScanConfig 생성
    
    Args:
        config: V2Config 객체
        fx_krw_per_usdt: FX rate (CLI 또는 실시간)
    
    Returns:
        ScanConfig
    """
    # V2Config.exchanges는 dict[str, ExchangeConfig]
    upbit_fee_bps = config.exchanges['upbit'].taker_fee_bps if 'upbit' in config.exchanges else 5.0
    binance_fee_bps = config.exchanges['binance'].taker_fee_bps if 'binance' in config.exchanges else 4.0
    slippage_bps = config.strategy.threshold.slippage_bps
    buffer_bps = config.strategy.threshold.buffer_bps
    
    # FX conversion cost (환전 비용) - config에 없으면 기본값
    fx_conversion_bps = getattr(config.strategy.threshold, 'fx_conversion_bps', 2.0)
    
    return ScanConfig(
        fx_krw_per_usdt=fx_krw_per_usdt,
        upbit_fee_bps=upbit_fee_bps,
        binance_fee_bps=binance_fee_bps,
        slippage_bps=slippage_bps,
        fx_conversion_bps=fx_conversion_bps,
        buffer_bps=buffer_bps,
    )
