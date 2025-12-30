#!/usr/bin/env python3
"""
D205-4: Reality Wiring — Real Market Data → Detector → Paper Intent + Latency/KPI Evidence

목표:
- 리얼 마켓 데이터(Upbit/Binance) → Opportunity Detection → Paper OrderIntent
- DecisionTrace: "왜 0 trades인가?" 숫자로 설명
- Latency 계측: tick→decision, decision→intent, tick→intent (ms)
- Evidence: manifest.json, kpi.json, decision_trace.json, latency.json

SSOT: docs/v2/design/EVIDENCE_FORMAT.md
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# V2 imports
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.opportunity.detector import detect_candidates, OpportunityDirection
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.core.decision_trace import DecisionTrace, LatencyMetrics
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logger = logging.getLogger(__name__)


class RealityWiringRunner:
    """
    D205-4: Reality Wiring Runner
    
    리얼 마켓 데이터 → Detector → Paper Intent 플로우
    DecisionTrace + Latency 증거 수집
    """
    
    def __init__(
        self,
        symbols: List[str],
        duration_sec: int = 120,
        sample_interval_sec: float = 5.0,
        env: str = "test",
        run_id: Optional[str] = None,
    ):
        self.symbols = symbols
        self.duration_sec = duration_sec
        self.sample_interval_sec = sample_interval_sec
        self.env = env
        self.run_id = run_id or datetime.now().strftime("d205_4_reality_wiring_%Y%m%d_%H%M%S")
        
        # Providers
        self.upbit_rest = UpbitRestProvider()
        self.binance_rest = BinanceRestProvider()
        
        # Break-even params (기본값)
        fee_a = FeeStructure(
            exchange_name="upbit",
            maker_fee_bps=5.0,
            taker_fee_bps=25.0,
        )
        fee_b = FeeStructure(
            exchange_name="binance",
            maker_fee_bps=10.0,
            taker_fee_bps=25.0,
        )
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        self.break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        # Decision trace
        self.decision_trace = DecisionTrace()
        
        # KPI tracking
        self.start_time = None
        self.end_time = None
        self.opportunities_count = 0
        self.opportunities_profitable = 0
        self.errors: List[Dict] = []
        self.sample_ticks: List[Dict] = []
        
        # Evidence path
        self.evidence_dir = Path("logs/evidence") / self.run_id
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[D205-4] RealityWiringRunner initialized: run_id={self.run_id}")
        logger.info(f"[D205-4] Symbols: {symbols}")
        logger.info(f"[D205-4] Duration: {duration_sec}s, Interval: {sample_interval_sec}s")
        logger.info(f"[D205-4] Evidence: {self.evidence_dir}")
    
    async def run(self):
        """메인 실행: duration 동안 주기적 샘플링"""
        self.start_time = time.time()
        logger.info(f"[D205-4] Starting reality wiring... (duration={self.duration_sec}s)")
        
        try:
            elapsed = 0.0
            iteration = 0
            while elapsed < self.duration_sec:
                iteration += 1
                await self._sample_iteration()
                await asyncio.sleep(self.sample_interval_sec)
                elapsed = time.time() - self.start_time
                
                if int(elapsed) % 30 == 0:  # 30초마다 진행 상황
                    logger.info(
                        f"[D205-4] Progress: {elapsed:.0f}s / {self.duration_sec}s "
                        f"(opportunities={self.opportunities_count}, profitable={self.opportunities_profitable})"
                    )
        
        except KeyboardInterrupt:
            logger.warning("[D205-4] Interrupted by user")
        
        finally:
            self.end_time = time.time()
            await self._save_evidence()
    
    async def _sample_iteration(self):
        """1회 샘플링: 모든 심볼에 대해 기회 탐지"""
        tick_received_ts = time.time() * 1000  # ms
        
        for symbol in self.symbols:
            try:
                # 1. Tick 수신 (Upbit)
                upbit_ticker = self.upbit_rest.get_ticker(symbol)
                if not upbit_ticker:
                    self.decision_trace.record_gate_ratelimit()
                    continue
                
                # 2. Tick 수신 (Binance) - 심볼 매핑 (BTC/KRW → BTC/USDT)
                binance_symbol = symbol.replace("/KRW", "/USDT")
                binance_ticker = self.binance_rest.get_ticker(binance_symbol)
                if not binance_ticker:
                    self.decision_trace.record_gate_ratelimit()
                    continue
                
                decision_ts = time.time() * 1000  # ms
                tick_to_decision_ms = decision_ts - tick_received_ts
                self.decision_trace.latency_metrics.add_tick_to_decision(tick_to_decision_ms)
                
                # 3. Opportunity Detection
                self.decision_trace.record_tick_evaluated()
                
                candidate = detect_candidates(
                    symbol=symbol,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=upbit_ticker.bid,  # Upbit bid
                    price_b=binance_ticker.ask,  # Binance ask
                    params=self.break_even_params,
                )
                
                if candidate:
                    self.decision_trace.record_opportunity(candidate.edge_bps)
                    self.opportunities_count += 1
                    
                    if candidate.profitable:
                        self.opportunities_profitable += 1
                    
                    # 4. OrderIntent 생성 (Paper, 실거래 없음)
                    intent_ts = time.time() * 1000  # ms
                    decision_to_intent_ms = intent_ts - decision_ts
                    tick_to_intent_ms = intent_ts - tick_received_ts
                    
                    self.decision_trace.latency_metrics.add_decision_to_intent(decision_to_intent_ms)
                    self.decision_trace.latency_metrics.add_tick_to_intent(tick_to_intent_ms)
                    
                    # Sample tick 저장 (1/10 sampling)
                    if self.opportunities_count % 10 == 0:
                        self.sample_ticks.append({
                            "timestamp": datetime.now().isoformat(),
                            "symbol": symbol,
                            "upbit_bid": upbit_ticker.bid,
                            "binance_ask": binance_ticker.ask,
                            "spread_bps": candidate.spread_bps,
                            "edge_bps": candidate.edge_bps,
                            "direction": candidate.direction.value,
                            "profitable": candidate.profitable,
                            "latency_tick_to_decision_ms": tick_to_decision_ms,
                            "latency_decision_to_intent_ms": decision_to_intent_ms,
                            "latency_tick_to_intent_ms": tick_to_intent_ms,
                        })
                else:
                    # Spread 부족
                    self.decision_trace.record_gate_spread_insufficient()
            
            except Exception as e:
                self.decision_trace.record_gate_ratelimit()
                self.errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "error": str(e),
                    "type": type(e).__name__,
                })
                logger.error(f"[D205-4] Sample error ({symbol}): {e}")
    
    async def _save_evidence(self):
        """Evidence 파일 저장 (SSOT 규격)"""
        logger.info(f"[D205-4] Saving evidence to {self.evidence_dir}")
        
        # 1) manifest.json
        manifest = {
            "run_id": self.run_id,
            "task": "D205-4",
            "description": "Reality Wiring - Real market data → Detector → Paper Intent",
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
            "duration_sec": self.duration_sec,
            "env": self.env,
            "symbols": self.symbols,
            "sample_interval_sec": self.sample_interval_sec,
            "git_sha": self._get_git_sha(),
        }
        with open(self.evidence_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        # 2) kpi.json
        uptime_sec = self.end_time - self.start_time
        latency_metrics = self.decision_trace.latency_metrics
        
        kpi = {
            "uptime_sec": round(uptime_sec, 2),
            "opportunities_count": self.opportunities_count,
            "opportunities_profitable": self.opportunities_profitable,
            "profitability_rate_pct": round(
                (self.opportunities_profitable / self.opportunities_count * 100) 
                if self.opportunities_count > 0 else 0, 2
            ),
            "latency_p50_ms": latency_metrics.percentile(
                latency_metrics.tick_to_intent_ms, 50
            ),
            "latency_p95_ms": latency_metrics.percentile(
                latency_metrics.tick_to_intent_ms, 95
            ),
            "latency_p99_ms": latency_metrics.percentile(
                latency_metrics.tick_to_intent_ms, 99
            ),
            "edge_mean": self._compute_edge_mean(),
            "edge_std": self._compute_edge_std(),
            "error_count": len(self.errors),
        }
        with open(self.evidence_dir / "kpi.json", "w", encoding="utf-8") as f:
            json.dump(kpi, f, indent=2, ensure_ascii=False)
        
        # 3) decision_trace.json
        decision_trace_dict = self.decision_trace.to_dict()
        with open(self.evidence_dir / "decision_trace.json", "w", encoding="utf-8") as f:
            json.dump(decision_trace_dict, f, indent=2, ensure_ascii=False)
        
        # 4) latency.json
        latency_dict = latency_metrics.to_dict()
        with open(self.evidence_dir / "latency.json", "w", encoding="utf-8") as f:
            json.dump(latency_dict, f, indent=2, ensure_ascii=False)
        
        # 5) sample_ticks.ndjson (최근 100개)
        with open(self.evidence_dir / "sample_ticks.ndjson", "w", encoding="utf-8") as f:
            for tick in self.sample_ticks[-100:]:
                f.write(json.dumps(tick, ensure_ascii=False) + "\n")
        
        # 6) errors.ndjson
        with open(self.evidence_dir / "errors.ndjson", "w", encoding="utf-8") as f:
            for error in self.errors:
                f.write(json.dumps(error, ensure_ascii=False) + "\n")
        
        # 7) README.md
        readme = f"""# D205-4 Reality Wiring Evidence

**Run ID:** {self.run_id}  
**Duration:** {uptime_sec:.0f}s  
**Opportunities:** {self.opportunities_count} total, {self.opportunities_profitable} profitable  

## 재현 방법

```bash
.\\abt_bot_env\\Scripts\\python.exe scripts\\run_d205_4_reality_wiring.py \\
    --symbols BTC/KRW ETH/KRW XRP/KRW \\
    --duration-sec {self.duration_sec} \\
    --sample-interval-sec {self.sample_interval_sec}
```

## Evidence 파일

- `manifest.json`: 실행 메타 정보
- `kpi.json`: KPI 요약 (opportunities, latency, edge)
- `decision_trace.json`: Gate breakdown (spread, liquidity, cooldown, ratelimit)
- `latency.json`: Latency p50/p95/p99
- `sample_ticks.ndjson`: 샘플 tick 데이터 (최근 100개)
- `errors.ndjson`: 에러 로그
- `README.md`: 본 파일

## SSOT Reference

- Evidence 포맷: `docs/v2/design/EVIDENCE_FORMAT.md`
- D205-4 Report: `docs/v2/reports/D205/D205-4_REPORT.md`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
"""
        with open(self.evidence_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)
        
        logger.info(f"[D205-4] Evidence saved successfully")
        logger.info(f"[D205-4] KPI: uptime={uptime_sec:.0f}s, opportunities={self.opportunities_count}, profitable={self.opportunities_profitable}")
        logger.info(f"[D205-4] Latency: p50={kpi['latency_p50_ms']:.1f}ms, p95={kpi['latency_p95_ms']:.1f}ms")
        logger.info(f"[D205-4] DecisionTrace: evaluated_ticks={self.decision_trace.evaluated_ticks_total}, gate_spread_insufficient={self.decision_trace.gate_spread_insufficient_count}")
    
    def _compute_edge_mean(self) -> float:
        """Edge 평균 계산"""
        if self.opportunities_count == 0:
            return 0.0
        
        distribution = self.decision_trace.edge_after_cost_distribution
        total_edges = 0.0
        
        # 근사값으로 계산 (각 범위의 중간값 사용)
        total_edges += distribution["negative"] * -5.0  # negative 범위 중간값
        total_edges += distribution["zero_to_10"] * 5.0  # 0~10 범위 중간값
        total_edges += distribution["10_to_50"] * 30.0  # 10~50 범위 중간값
        total_edges += distribution["50_plus"] * 75.0  # 50+ 범위 중간값
        
        return round(total_edges / self.opportunities_count, 2)
    
    def _compute_edge_std(self) -> float:
        """Edge 표준편차 계산 (근사값)"""
        if self.opportunities_count == 0:
            return 0.0
        
        mean = self._compute_edge_mean()
        distribution = self.decision_trace.edge_after_cost_distribution
        
        variance = 0.0
        variance += distribution["negative"] * ((-5.0 - mean) ** 2)
        variance += distribution["zero_to_10"] * ((5.0 - mean) ** 2)
        variance += distribution["10_to_50"] * ((30.0 - mean) ** 2)
        variance += distribution["50_plus"] * ((75.0 - mean) ** 2)
        
        variance /= self.opportunities_count
        std = (variance ** 0.5)
        
        return round(std, 2)
    
    def _get_git_sha(self) -> str:
        """현재 Git SHA 가져오기"""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=Path(__file__).parent.parent,
            )
            return result.stdout.strip()[:7]
        except Exception:
            return "unknown"


def main():
    parser = argparse.ArgumentParser(description="D205-4: Reality Wiring")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/KRW", "ETH/KRW", "XRP/KRW"],
        help="Symbols to sample (default: BTC/KRW ETH/KRW XRP/KRW)",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=120,
        help="Sampling duration in seconds (default: 120)",
    )
    parser.add_argument(
        "--sample-interval-sec",
        type=float,
        default=5.0,
        help="Sampling interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--env",
        default="test",
        help="Environment (default: test)",
    )
    
    args = parser.parse_args()
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Run reality wiring
    runner = RealityWiringRunner(
        symbols=args.symbols,
        duration_sec=args.duration_sec,
        sample_interval_sec=args.sample_interval_sec,
        env=args.env,
    )
    
    asyncio.run(runner.run())
    
    logger.info("[D205-4] Reality wiring completed successfully")


if __name__ == "__main__":
    main()
