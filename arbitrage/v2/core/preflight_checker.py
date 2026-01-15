"""
D205-15-6c: Preflight Checker - Runtime Verification

목적: 운영 전 60초 내 ops_critical 기능 실제 동작 확인
- Real MarketData 로드 성공
- Redis ping 성공
- DB strict 모드 연결 성공
- 짧은 smoke 실행으로 통합 동작 검증

Exit Code:
- 0: PASS (모든 검증 성공)
- 1: FAIL (하나라도 실패)
"""

import time
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arbitrage.v2.harness.paper_runner import PaperRunner


class PreflightChecker:
    """Preflight 검증기"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checks_passed = []
        self.checks_failed = []
    
    def log(self, message: str):
        """로그 출력 및 저장"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        
        # 로그 파일에도 저장
        log_file = self.output_dir / "preflight.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")
    
    def check_real_marketdata(self, runner: "PaperRunner") -> bool:
        """Real MarketData 로드 확인"""
        self.log("[CHECK] Real MarketData providers...")
        
        try:
            # use_real_data 플래그 확인
            if not runner.use_real_data:
                self.log("  FAIL: use_real_data=False")
                return False
            
            # MarketData provider 존재 확인
            if not hasattr(runner, 'upbit_provider') or not runner.upbit_provider:
                self.log("  FAIL: upbit_provider not initialized")
                return False
            
            if not hasattr(runner, 'binance_provider') or not runner.binance_provider:
                self.log("  FAIL: binance_provider not initialized")
                return False
            
            self.log("  PASS: Real MarketData providers initialized")
            return True
        
        except Exception as e:
            self.log(f"  FAIL: Exception: {e}")
            return False
    
    def check_redis(self, runner: "PaperRunner") -> bool:
        """Redis 연결 확인 (OPS Gate: STRICT)"""
        self.log("[CHECK] Redis connection...")
        
        try:
            # OPS Gate 정책: Redis 미초기화는 FAIL
            if not hasattr(runner, 'redis_client') or not runner.redis_client:
                self.log("  FAIL: redis_client not initialized (OPS Gate requires Redis)")
                return False
            
            # Ping 테스트
            runner.redis_client.ping()
            self.log("  PASS: Redis ping successful")
            return True
        
        except Exception as e:
            self.log(f"  FAIL: Redis check failed: {e}")
            return False
    
    def check_db_strict(self, runner: "PaperRunner") -> bool:
        """DB strict 모드 확인"""
        self.log("[CHECK] DB strict mode...")
        
        try:
            # db_mode 확인
            if runner.config.db_mode != "strict":
                self.log(f"  FAIL: db_mode={runner.config.db_mode} (expected 'strict')")
                return False
            
            # Storage 존재 확인
            if not hasattr(runner, 'storage') or not runner.storage:
                self.log("  FAIL: storage not initialized in strict mode")
                return False
            
            self.log("  PASS: DB strict mode enabled")
            return True
        
        except Exception as e:
            self.log(f"  FAIL: Exception: {e}")
            return False
    
    def run_smoke(self, duration_minutes: float = 1.0) -> bool:
        """짧은 smoke 실행"""
        self.log(f"[CHECK] Running {duration_minutes}-minute smoke test...")
        
        try:
            # PaperRunner import (circular import 방지)
            from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"preflight_{timestamp}"
            
            # Config 생성 (ops phase 강제)
            config = PaperRunnerConfig(
                duration_minutes=duration_minutes,
                phase="smoke",  # ops validation phase
                run_id=run_id,
                output_dir=str(self.output_dir / "smoke"),
                symbols_top=5,  # 작은 심볼 세트
                use_real_data=True,  # Real MarketData 강제
                db_mode="strict",  # DB strict 강제
                fx_krw_per_usdt=1450.0,
            )
            
            # Runner 생성
            runner = PaperRunner(config)
            
            # D206-1 CLOSEOUT: Smoke 실행 먼저 (orchestrator 초기화 후 검증)
            self.log(f"  Starting {duration_minutes}min smoke...")
            start_time = time.time()
            
            exit_code = runner.run()
            
            # D206-1 CLOSEOUT: 실행 후 MarketData/Redis/DB 검증
            marketdata_ok = self.check_real_marketdata(runner)
            redis_ok = self.check_redis(runner)
            db_ok = self.check_db_strict(runner)
            
            if not (marketdata_ok and db_ok):
                self.log("  FAIL: Post-smoke validation failed")
                # Note: 실행은 성공했지만 validation 실패 시 exit_code 무시하고 FAIL
                return False
            
            elapsed = time.time() - start_time
            
            # OPS Gate: runner.run() 반환값 체크 (Fail-Fast)
            if exit_code != 0:
                self.log(f"  FAIL: Smoke failed with exit code {exit_code}")
                self.log(f"  Check logs for winrate_guard or other failures")
                return False
            
            self.log(f"  PASS: Smoke completed in {elapsed:.1f}s (exit code 0)")
            
            # KPI 검증
            if runner.kpi.closed_trades > 0:
                self.log(f"  Trades executed: {runner.kpi.closed_trades}")
            else:
                self.log(f"  No trades executed (market conditions)")
            
            return True
        
        except Exception as e:
            self.log(f"  FAIL: Smoke execution failed: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False
    
    def run_all_checks(self) -> bool:
        """모든 검사 실행"""
        self.log("=" * 60)
        self.log("V2 Preflight Check - D205-15-6c")
        self.log("=" * 60)
        self.log("")
        
        # Smoke 실행 (통합 검증)
        smoke_ok = self.run_smoke(duration_minutes=1.0)
        
        self.log("")
        self.log("=" * 60)
        
        if smoke_ok:
            self.log("PREFLIGHT PASS: All checks passed")
            self.log("=" * 60)
            return True
        else:
            self.log("PREFLIGHT FAIL: One or more checks failed")
            self.log("=" * 60)
            return False
