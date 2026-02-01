"""
D_ALPHA-1U-FIX-1: Universe Smoke Test

Universe coverage 검증:
- topn_count=100 요청 시 ≥95 심볼 로드 (coverage_ratio ≥0.95)
- Wallclock ≤60s
- Binance Futures exchangeInfo 필터 동작 확인

Usage:
    python scripts/run_d_alpha_1u_universe_smoke.py --topn 100 --timeout 60
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.universe.builder import UniverseBuilder, UniverseBuilderConfig, UniverseMode

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run_universe_smoke(topn_count: int, timeout_seconds: int) -> dict:
    """
    Universe Smoke Test 실행
    
    Args:
        topn_count: 요청 심볼 수 (100)
        timeout_seconds: Wallclock 제한 (60s)
        
    Returns:
        dict: 검증 결과
    """
    logger.info("="*80)
    logger.info("D_ALPHA-1U-FIX-1: Universe Smoke Test")
    logger.info("="*80)
    
    # Config
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=topn_count,
        data_source="real",  # Real Upbit/Binance API
        cache_ttl_seconds=60,
        min_volume_usd=100_000.0,
        min_liquidity_usd=10_000.0,
        max_spread_bps=100.0,
    )
    
    logger.info(f"Config: topn_count={topn_count}, data_source=real, timeout={timeout_seconds}s")
    
    # Build universe with wallclock measurement
    builder = UniverseBuilder(config=config)
    
    start_time = time.time()
    symbols = builder.get_symbols()
    wallclock = time.time() - start_time
    
    # Calculate metrics
    loaded_count = len(symbols)
    coverage_ratio = loaded_count / topn_count if topn_count > 0 else 0.0
    
    logger.info("-"*80)
    logger.info("Results:")
    logger.info(f"  Universe Loaded: {loaded_count}/{topn_count} symbols")
    logger.info(f"  Coverage Ratio: {coverage_ratio:.2%}")
    logger.info(f"  Wallclock: {wallclock:.2f}s")
    logger.info("-"*80)
    
    # Validation
    passed = True
    reasons = []
    
    # Check 1: Coverage ≥95/100
    if loaded_count < 95:
        passed = False
        reasons.append(f"Coverage FAIL: loaded={loaded_count} < 95")
    else:
        logger.info("✅ Coverage: PASS (loaded ≥95)")
    
    # Check 2: Coverage ratio ≥0.95
    if coverage_ratio < 0.95:
        passed = False
        reasons.append(f"Coverage Ratio FAIL: {coverage_ratio:.2%} < 0.95")
    else:
        logger.info(f"✅ Coverage Ratio: PASS ({coverage_ratio:.2%} ≥0.95)")
    
    # Check 3: Wallclock ≤60s
    if wallclock > timeout_seconds:
        passed = False
        reasons.append(f"Wallclock FAIL: {wallclock:.2f}s > {timeout_seconds}s")
    else:
        logger.info(f"✅ Wallclock: PASS ({wallclock:.2f}s ≤{timeout_seconds}s)")
    
    # Sample symbols (first 10)
    logger.info("-"*80)
    logger.info("Sample Symbols (first 10):")
    for i, (sym_a, sym_b) in enumerate(symbols[:10], 1):
        logger.info(f"  {i:2d}. {sym_a:12s} <-> {sym_b:12s}")
    
    # Result
    logger.info("="*80)
    if passed:
        logger.info("✅ UNIVERSE SMOKE TEST: PASS")
    else:
        logger.error("❌ UNIVERSE SMOKE TEST: FAIL")
        for reason in reasons:
            logger.error(f"   - {reason}")
    logger.info("="*80)
    
    return {
        "passed": passed,
        "topn_requested": topn_count,
        "universe_loaded_count": loaded_count,
        "coverage_ratio": coverage_ratio,
        "wallclock_seconds": wallclock,
        "timeout_seconds": timeout_seconds,
        "reasons": reasons,
        "sample_symbols": symbols[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="D_ALPHA-1U-FIX-1: Universe Smoke Test")
    parser.add_argument("--topn", type=int, default=100, help="TopN count (default: 100)")
    parser.add_argument("--timeout", type=int, default=60, help="Wallclock timeout (default: 60s)")
    parser.add_argument("--output", type=str, help="Output JSON file path (optional)")
    args = parser.parse_args()
    
    result = run_universe_smoke(topn_count=args.topn, timeout_seconds=args.timeout)
    
    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {output_path}")
    
    # Exit code
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
