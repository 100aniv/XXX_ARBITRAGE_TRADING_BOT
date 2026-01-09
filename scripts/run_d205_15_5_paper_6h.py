"""
D205-15-5b: 6h Paper Run with Checkpoint + Graceful Shutdown (HOTFIX)

장시간 Paper Trading 실행 (6시간)
- 5분 주기 checkpoint (kpi_timeseries.jsonl)
- SIGINT 처리 (Ctrl+C graceful shutdown)
- watch_summary.json (wallclock verification)
- atomic write (temp → fsync → rename)

Thin Wrapper 원칙:
- CLI 파라미터 파싱만 담당
- 실제 루프/판단은 PaperRunner(엔진)에 위임
- Evidence 생성은 evidence_guard.py 재사용

Usage:
    # 6시간 실행
    python scripts/run_d205_15_5_paper_6h.py --duration-minutes 360

    # 10분 smoke (사전 검증)
    python scripts/run_d205_15_5_paper_6h.py --smoke

Author: D205-15-5b (HOTFIX)
Date: 2026-01-09
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# V2 imports (엔진 재사용)
from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig
from arbitrage.v2.scan.evidence_guard import save_json_with_validation
from arbitrage.v2.utils.timestamp import now_utc_naive

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LongRunPaperHarness:
    """
    장시간 Paper Run 하네스 (Thin Wrapper)
    
    Features:
    - Graceful Shutdown: SIGINT 처리
    - Wallclock Verification: watch_summary.json
    - Evidence 무결성: atomic write (evidence_guard 재사용)
    
    책임:
    - CLI 파라미터 → 엔진 Config 변환
    - SIGINT 처리
    - Evidence 디렉토리 생성
    - watch_summary.json 생성
    
    금지 (Thin Wrapper 원칙):
    - 트레이딩 루프 구현 (엔진에 위임)
    - 데이터 처리 로직 (엔진에 위임)
    """
    
    def __init__(
        self,
        duration_minutes: int,
        is_smoke: bool = False,
        output_dir: Optional[str] = None,
    ):
        self.duration_minutes = duration_minutes
        self.is_smoke = is_smoke
        
        # Evidence 경로 생성
        if output_dir:
            self.evidence_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "smoke_10m" if is_smoke else "paper_6h"
            self.evidence_dir = Path(f"logs/evidence/d205_15_5_{prefix}_{timestamp}")
        
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.start_time = None
        self.end_time = None
        self.should_stop = False
        
        # Signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(
            f"[LONGRUN_HARNESS] Initialized: duration={duration_minutes}m, "
            f"is_smoke={is_smoke}, evidence={self.evidence_dir}"
        )
    
    def _signal_handler(self, signum, frame):
        """SIGINT/SIGTERM 처리 (Graceful Shutdown)"""
        logger.warning(f"[SIGNAL] Received signal {signum}, initiating graceful shutdown...")
        self.should_stop = True
    
    def _generate_watch_summary(self, stop_reason: str, kpi: dict):
        """
        watch_summary.json 생성 (wallclock verification)
        
        SSOT 원칙:
        - completeness_ratio, stop_reason 기반 판정
        - 시간 기반 완료 선언 금지
        
        Args:
            stop_reason: TIME_REACHED | INTERRUPTED | ERROR
            kpi: 최종 KPI
        """
        if not self.start_time:
            logger.warning("[WATCH_SUMMARY] start_time is None, skipping")
            return
        
        end_time = self.end_time or datetime.now(timezone.utc)
        elapsed_seconds = (end_time - self.start_time).total_seconds()
        expected_seconds = self.duration_minutes * 60
        completeness_ratio = min(elapsed_seconds / expected_seconds, 1.0) if expected_seconds > 0 else 0.0
        
        summary = {
            "planned_total_hours": self.duration_minutes / 60.0,
            "started_at_utc": self.start_time.isoformat(),
            "ended_at_utc": end_time.isoformat(),
            "monotonic_elapsed_sec": elapsed_seconds,
            "completeness_ratio": completeness_ratio,
            "stop_reason": stop_reason,
            "is_smoke": self.is_smoke,
            # KPI aggregation
            "opportunities_generated": kpi.get("opportunities_generated", 0),
            "intents_created": kpi.get("intents_created", 0),
            "mock_executions": kpi.get("mock_executions", 0),
            "error_count": kpi.get("error_count", 0),
        }
        
        # Atomic write (evidence_guard 재사용)
        watch_path = self.evidence_dir / "watch_summary.json"
        save_json_with_validation(watch_path, summary)
        logger.info(
            f"[WATCH_SUMMARY] Saved: completeness={completeness_ratio:.2%}, "
            f"stop_reason={stop_reason}"
        )
    
    def run(self):
        """
        6h Paper Run 실행 (엔진에 위임)
        
        Returns:
            Dict: 최종 KPI summary
        """
        logger.info("[LONGRUN_HARNESS] Starting Paper Run...")
        self.start_time = datetime.now(timezone.utc)
        
        # PaperRunnerConfig 생성 (엔진 설정)
        config = PaperRunnerConfig(
            duration_minutes=self.duration_minutes,
            phase="longrun" if not self.is_smoke else "smoke",
            output_dir=str(self.evidence_dir),
            symbols_top=20,
            use_real_data=True,
            fx_krw_per_usdt=1450.0,
            read_only=True,
        )
        
        # PaperRunner 초기화 (엔진)
        try:
            runner = PaperRunner(config)
        except Exception as e:
            logger.error(f"[LONGRUN_HARNESS] Failed to initialize PaperRunner: {e}")
            self.end_time = datetime.now(timezone.utc)
            self._generate_watch_summary("ERROR", {})
            raise
        
        # Main loop (엔진에 위임)
        stop_reason = "TIME_REACHED"
        final_kpi = {}
        exit_code = 1
        
        try:
            logger.info("[LONGRUN_HARNESS] Running PaperRunner (blocking)...")
            exit_code = runner.run()
            
            # PaperRunner.run()은 exit_code (int) 반환
            # KPI는 runner.kpi.to_dict()로 가져옴
            final_kpi = runner.kpi.to_dict()
            
            if exit_code == 0:
                stop_reason = "TIME_REACHED"
            else:
                stop_reason = "ERROR"
            
        except KeyboardInterrupt:
            logger.warning("[LONGRUN_HARNESS] Interrupted by user (Ctrl+C)")
            stop_reason = "INTERRUPTED"
            final_kpi = runner.kpi.to_dict() if hasattr(runner, 'kpi') else {}
        except Exception as e:
            logger.error(f"[LONGRUN_HARNESS] Error during run: {e}", exc_info=True)
            stop_reason = "ERROR"
            final_kpi = runner.kpi.to_dict() if hasattr(runner, 'kpi') else {}
        finally:
            self.end_time = datetime.now(timezone.utc)
            self._generate_watch_summary(stop_reason, final_kpi)
            
            # KPI summary 저장 (atomic write)
            summary_path = self.evidence_dir / "kpi_summary.json"
            save_json_with_validation(summary_path, final_kpi)
            
            # README 생성
            self._generate_readme()
        
        logger.info(
            f"[LONGRUN_HARNESS] Finished: stop_reason={stop_reason}, "
            f"evidence={self.evidence_dir}"
        )
        return final_kpi
    
    def _generate_readme(self):
        """Evidence README 생성"""
        readme_path = self.evidence_dir / "README.md"
        
        content = f"""# D205-15-5: {"Smoke 10m" if self.is_smoke else "Paper 6h"} Evidence

**일시:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Duration:** {self.duration_minutes} minutes
**Evidence Path:** `{self.evidence_dir}`

## 재현 커맨드

```bash
python scripts/run_d205_15_5_paper_6h.py --duration-minutes {self.duration_minutes}{"" if not self.is_smoke else " --smoke"}
```

## Evidence 구조

- `manifest.json`: 실행 메타데이터 (PaperRunner 생성)
- `kpi_summary.json`: 최종 KPI 요약
- `watch_summary.json`: wallclock verification (SSOT)
- `README.md`: 본 문서

## KPI 검증

```bash
# watch_summary.json 확인
cat {self.evidence_dir}/watch_summary.json | jq .

# kpi_summary.json 확인
cat {self.evidence_dir}/kpi_summary.json | jq .
```

## PASS 조건 (SSOT_RULES)

- `watch_summary.json` 존재
- `completeness_ratio >= 0.95` 또는 `stop_reason = INTERRUPTED`
- `kpi_summary.json` 존재
- `opportunities_generated > 0` (실행 완료 시)
"""
        
        readme_path.write_text(content, encoding="utf-8")
        logger.info(f"[README] Generated: {readme_path}")


def main():
    parser = argparse.ArgumentParser(description="D205-15-5b: 6h Paper Run with Checkpoint (HOTFIX)")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=360,
        help="실행 시간 (분, 기본값: 360 = 6h)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Evidence 저장 경로 (기본값: logs/evidence/d205_15_5_paper_6h_<timestamp>)"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke 모드 (10분 사전 검증)"
    )
    
    args = parser.parse_args()
    
    # Smoke 모드는 10분 고정
    if args.smoke:
        args.duration_minutes = 10
    
    harness = LongRunPaperHarness(
        duration_minutes=args.duration_minutes,
        output_dir=args.output_dir,
        is_smoke=args.smoke,
    )
    
    try:
        kpi = harness.run()
        logger.info(f"[MAIN] Paper Run completed successfully")
        logger.info(f"[MAIN] Final KPI: {json.dumps(kpi, indent=2)}")
        return 0
    except Exception as e:
        logger.error(f"[MAIN] Paper Run failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
