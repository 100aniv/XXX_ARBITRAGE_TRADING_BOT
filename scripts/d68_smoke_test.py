"""
D68 Smoke Test - 빠른 검증용 (30초 x 3조합 = ~2분)

D68 Acceptance 요구사항:
- PostgreSQL DB 필수 (Docker 기동 필요)
- 최소 3개 파라미터 조합 실행
- 모든 결과가 tuning_results 테이블에 저장
- DB 저장 실패 시 테스트 FAIL
"""

import sys
import os
import logging
import psycopg2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tuning.parameter_tuner import ParameterTuner, TuningConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def check_db_connection():
    """PostgreSQL 연결 체크 (필수)"""
    logger.info("[D68_SMOKE] Checking PostgreSQL connection...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,  # arbitrage-postgres 포트
            dbname='arbitrage',
            user='arbitrage',
            password='arbitrage'
        )
        conn.close()
        logger.info("[D68_SMOKE] ✅ PostgreSQL connection OK")
        return True
    except Exception as e:
        logger.error(f"[D68_SMOKE] ❌ PostgreSQL connection FAILED: {e}")
        logger.error("[D68_SMOKE] Please start Docker PostgreSQL: docker compose up -d postgres")
        return False


def main():
    """스모크 테스트 실행"""
    logger.info("="*80)
    logger.info("[D68_SMOKE] D68 Parameter Tuning Smoke Test")
    logger.info("="*80)
    
    # DB 연결 체크 (필수)
    if not check_db_connection():
        logger.error("[D68_SMOKE] ❌ SMOKE TEST FAILED: PostgreSQL not available")
        return 1
    
    # 최소 파라미터 조합 (3개)
    param_ranges = {
        'min_spread_bps': [20.0, 30.0, 40.0],  # 3개 값
    }
    
    # 짧은 테스트 설정 (30초)
    config = TuningConfig(
        param_ranges=param_ranges,
        mode='grid',
        campaign_id='C1',
        duration_seconds=30,  # 30초만 실행
        symbols=['BTCUSDT'],
        notes='D68 smoke test'
    )
    
    logger.info("[D68_SMOKE] Configuration:")
    logger.info(f"  - Mode: {config.mode}")
    logger.info(f"  - Campaign: {config.campaign_id}")
    logger.info(f"  - Duration: {config.duration_seconds}s")
    logger.info(f"  - Param ranges: {param_ranges}")
    logger.info(f"  - Expected combinations: 3")
    logger.info(f"  - Estimated time: ~2 minutes")
    
    # 튜너 실행
    tuner = ParameterTuner(config)
    
    try:
        results = tuner.run_tuning()
        
        # 결과 확인
        logger.info("="*80)
        logger.info("[D68_SMOKE] Smoke Test Results:")
        logger.info("="*80)
        
        valid_results = [r for r in results if not r.error_message and r.total_exits > 0]
        logger.info(f"Valid results: {len(valid_results)}/{len(results)}")
        
        for idx, result in enumerate(results, start=1):
            logger.info(
                f"  #{idx}: params={result.param_set}, "
                f"PnL=${result.total_pnl:.2f}, "
                f"Winrate={result.winrate:.1f}%, "
                f"Trades={result.total_exits}, "
                f"run_id={result.run_id}"
            )
        
        # DB 저장 검증
        logger.info("="*80)
        logger.info("[D68_SMOKE] DB Storage Verification:")
        logger.info("="*80)
        
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,  # arbitrage-postgres 포트
                dbname='arbitrage',
                user='arbitrage',
                password='arbitrage'
            )
            cursor = conn.cursor()
            
            # 이번 세션의 결과 개수 확인
            cursor.execute(
                "SELECT COUNT(*) FROM tuning_results WHERE session_id = %s",
                (config.session_id,)
            )
            db_row_count = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            logger.info(f"  ✓ DB rows for session {config.session_id}: {db_row_count}")
            
            if db_row_count < len(results):
                logger.error(f"  ❌ DB row count mismatch: expected {len(results)}, got {db_row_count}")
                return 1
            
        except Exception as e:
            logger.error(f"  ❌ DB verification failed: {e}")
            return 1
        
        # Acceptance 체크
        logger.info("="*80)
        logger.info("[D68_SMOKE] Acceptance Checks:")
        logger.info("="*80)
        
        check1 = len(valid_results) >= 3
        logger.info(f"  ✓ Valid results >= 3: {'PASS' if check1 else 'FAIL'} ({len(valid_results)})")
        
        check2 = len([r for r in results if r.error_message]) == 0
        logger.info(f"  ✓ No errors: {'PASS' if check2 else 'FAIL'}")
        
        check3 = tuner.best_result is not None
        logger.info(f"  ✓ Best result found: {'PASS' if check3 else 'FAIL'}")
        
        check4 = db_row_count >= len(results)
        logger.info(f"  ✓ DB storage verified: {'PASS' if check4 else 'FAIL'} ({db_row_count} rows)")
        
        acceptance_passed = check1 and check2 and check3 and check4
        
        logger.info("="*80)
        if acceptance_passed:
            logger.info("[D68_SMOKE] ✅ Smoke test PASSED!")
        else:
            logger.error("[D68_SMOKE] ❌ Smoke test FAILED!")
        logger.info("="*80)
        
        return 0 if acceptance_passed else 1
        
    except Exception as e:
        logger.error(f"[D68_SMOKE] ❌ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
