#!/usr/bin/env python3
"""
D202-2: MarketData 1h Sampler + Evidence SSOT

목표:
- Upbit/Binance Top10 심볼 대상
- REST (ticker/trades) + WS (L2 orderbook) 주기적 수집
- KPI: uptime, samples_ok/fail, reconnect_count, latency_p50/p95/max, parse_errors
- Evidence: logs/evidence/d202_2_market_sample_YYYYMMDD_HHMM/

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
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# V2 imports
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider

# Redis (fakeredis for local testing)
try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class MarketDataSampler:
    """
    D202-2: MarketData Sampler (REST only for v1.0)
    
    Evidence 구조 (SSOT):
    logs/evidence/d202_2_market_sample_YYYYMMDD_HHMM/
        manifest.json
        kpi.json
        errors.ndjson
        raw_sample.ndjson (optional, 1/N sampling)
        README.md
    """
    
    def __init__(
        self,
        symbols: List[str],
        duration_sec: int = 3600,
        sample_interval_sec: float = 5.0,
        env: str = "test",
        run_id: Optional[str] = None,
    ):
        self.symbols = symbols
        self.duration_sec = duration_sec
        self.sample_interval_sec = sample_interval_sec
        self.env = env
        self.run_id = run_id or datetime.now().strftime("d202_2_market_sample_%Y%m%d_%H%M%S")
        
        # Providers
        self.upbit_rest = UpbitRestProvider()
        self.binance_rest = BinanceRestProvider()
        
        # KPI tracking
        self.start_time = None
        self.end_time = None
        self.samples_ok = 0
        self.samples_fail = 0
        self.parse_errors = 0
        self.latencies_ms: List[float] = []
        self.errors: List[Dict] = []
        self.raw_samples: List[Dict] = []
        
        # Evidence path
        self.evidence_dir = Path("logs/evidence") / self.run_id
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[D202-2] MarketDataSampler initialized: run_id={self.run_id}")
        logger.info(f"[D202-2] Symbols: {symbols}")
        logger.info(f"[D202-2] Duration: {duration_sec}s, Interval: {sample_interval_sec}s")
        logger.info(f"[D202-2] Evidence: {self.evidence_dir}")
    
    async def run(self):
        """메인 실행: duration 동안 주기적 샘플링"""
        self.start_time = time.time()
        logger.info(f"[D202-2] Starting sampler... (duration={self.duration_sec}s)")
        
        try:
            elapsed = 0.0
            while elapsed < self.duration_sec:
                await self._sample_iteration()
                await asyncio.sleep(self.sample_interval_sec)
                elapsed = time.time() - self.start_time
                
                if int(elapsed) % 60 == 0:  # 1분마다 진행 상황
                    logger.info(
                        f"[D202-2] Progress: {elapsed:.0f}s / {self.duration_sec}s "
                        f"(ok={self.samples_ok}, fail={self.samples_fail})"
                    )
        
        except KeyboardInterrupt:
            logger.warning("[D202-2] Interrupted by user")
        
        finally:
            self.end_time = time.time()
            await self._save_evidence()
    
    async def _sample_iteration(self):
        """1회 샘플링: 모든 심볼에 대해 REST ticker 수집"""
        for symbol in self.symbols:
            try:
                # Upbit ticker
                start_ms = time.time() * 1000
                ticker = self.upbit_rest.get_ticker(symbol)
                latency_ms = (time.time() * 1000) - start_ms
                
                if ticker:
                    self.samples_ok += 1
                    self.latencies_ms.append(latency_ms)
                    
                    # Raw sample (1/10 sampling to reduce size)
                    if self.samples_ok % 10 == 0:
                        self.raw_samples.append({
                            "timestamp": datetime.now().isoformat(),
                            "exchange": "upbit",
                            "symbol": symbol,
                            "ticker": {
                                "bid": ticker.bid,
                                "ask": ticker.ask,
                                "last": ticker.last,
                                "volume": ticker.volume,
                            },
                            "latency_ms": latency_ms,
                        })
                else:
                    self.samples_fail += 1
            
            except Exception as e:
                self.samples_fail += 1
                self.parse_errors += 1
                self.errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "exchange": "upbit",
                    "symbol": symbol,
                    "error": str(e),
                    "type": type(e).__name__,
                })
                logger.error(f"[D202-2] Sample error (upbit/{symbol}): {e}")
    
    async def _save_evidence(self):
        """Evidence 파일 저장 (SSOT 규격)"""
        logger.info(f"[D202-2] Saving evidence to {self.evidence_dir}")
        
        # 1) manifest.json
        manifest = {
            "run_id": self.run_id,
            "task": "D202-2",
            "description": "MarketData 1h sampler + Evidence SSOT",
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
        kpi = {
            "uptime_sec": round(uptime_sec, 2),
            "samples_ok": self.samples_ok,
            "samples_fail": self.samples_fail,
            "parse_errors_count": self.parse_errors,
            "latency_ms_p50": self._percentile(self.latencies_ms, 50),
            "latency_ms_p95": self._percentile(self.latencies_ms, 95),
            "latency_ms_max": max(self.latencies_ms) if self.latencies_ms else 0,
            "ws_reconnect_count": 0,  # WS는 v2.0에서 추가
            "ws_disconnect_count": 0,
        }
        with open(self.evidence_dir / "kpi.json", "w", encoding="utf-8") as f:
            json.dump(kpi, f, indent=2, ensure_ascii=False)
        
        # 3) errors.ndjson
        with open(self.evidence_dir / "errors.ndjson", "w", encoding="utf-8") as f:
            for error in self.errors:
                f.write(json.dumps(error, ensure_ascii=False) + "\n")
        
        # 4) raw_sample.ndjson (1/10 sampling)
        with open(self.evidence_dir / "raw_sample.ndjson", "w", encoding="utf-8") as f:
            for sample in self.raw_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        
        # 5) README.md
        readme = f"""# D202-2 MarketData Sampler Evidence

**Run ID:** {self.run_id}  
**Duration:** {uptime_sec:.0f}s  
**Samples:** {self.samples_ok} OK, {self.samples_fail} FAIL  

## 재현 방법

```bash
.\\abt_bot_env\\Scripts\\python.exe scripts\\run_d202_2_market_sampler.py \\
    --symbols BTC/KRW ETH/KRW XRP/KRW \\
    --duration-sec {self.duration_sec} \\
    --sample-interval-sec {self.sample_interval_sec}
```

## Evidence 파일

- `manifest.json`: 실행 메타 정보
- `kpi.json`: KPI 요약 (uptime, latency, errors)
- `errors.ndjson`: 에러 로그
- `raw_sample.ndjson`: Raw 샘플 (1/10 sampling)
- `README.md`: 본 파일

## SSOT Reference

- Evidence 포맷: `docs/v2/design/EVIDENCE_FORMAT.md`
- MarketData Provider: `arbitrage/v2/marketdata/`
"""
        with open(self.evidence_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)
        
        logger.info(f"[D202-2] Evidence saved successfully")
        logger.info(f"[D202-2] KPI: uptime={uptime_sec:.0f}s, ok={self.samples_ok}, fail={self.samples_fail}")
        logger.info(f"[D202-2] Latency: p50={kpi['latency_ms_p50']:.1f}ms, p95={kpi['latency_ms_p95']:.1f}ms")
    
    def _percentile(self, data: List[float], p: int) -> float:
        """퍼센타일 계산"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        return round(sorted_data[min(idx, len(sorted_data) - 1)], 2)
    
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
    parser = argparse.ArgumentParser(description="D202-2: MarketData Sampler")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/KRW", "ETH/KRW", "XRP/KRW"],
        help="Symbols to sample (default: BTC/KRW ETH/KRW XRP/KRW)",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=30,
        help="Sampling duration in seconds (default: 30, for CI; use 3600 for 1h)",
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
    
    # Run sampler
    sampler = MarketDataSampler(
        symbols=args.symbols,
        duration_sec=args.duration_sec,
        sample_interval_sec=args.sample_interval_sec,
        env=args.env,
    )
    
    asyncio.run(sampler.run())
    
    logger.info("[D202-2] Sampler completed successfully")


if __name__ == "__main__":
    main()
