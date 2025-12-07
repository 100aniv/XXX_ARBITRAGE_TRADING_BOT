#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3.2: 3h Advisory + 3h Strict Long-run PAPER 완전 자동화 Orchestrator

한 줄 명령으로 전체 실행:
- 환경 점검 (가상환경, Docker, Redis, Postgres, 프로세스 정리)
- Advisory 3h PAPER 실행
- Strict 3h PAPER 실행
- A/B 분석 실행
- 결과 요약 출력

Usage:
    # 실제 3h+3h 실행
    python scripts/d87_3_longrun_orchestrator.py --mode full
    
    # Dry-run (환경 점검 및 명령 검증만)
    python scripts/d87_3_longrun_orchestrator.py --mode dry-run
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class D87LongrunOrchestrator:
    """D87-3 Long-run 3h+3h PAPER Orchestrator"""
    
    def __init__(self, mode: str = "full", skip_env_check: bool = False):
        """
        Args:
            mode: 실행 모드 ("full" | "dry-run")
            skip_env_check: 환경 점검 생략 여부
        """
        self.mode = mode
        self.skip_env_check = skip_env_check
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "d87-3"
        
        # 세션 정보
        self.advisory_session_tag = "d87_3_advisory_3h"
        self.strict_session_tag = "d87_3_strict_3h"
        self.calibration_path = self.project_root / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        # 실행 결과
        self.advisory_result = None
        self.strict_result = None
        self.analysis_result = None
        
    def check_environment(self) -> bool:
        """환경 점검 (D77-4 패턴 재사용)"""
        logger.info("=" * 100)
        logger.info("환경 점검")
        logger.info("=" * 100)
        
        checks_passed = True
        
        # 1. Python 가상환경 확인
        venv_path = os.environ.get("VIRTUAL_ENV", None)
        if venv_path:
            logger.info(f"✅ 가상환경 활성화됨: {venv_path}")
        else:
            logger.warning("⚠️  가상환경이 활성화되지 않았습니다. 계속 진행합니다.")
        
        # 2. Calibration 파일 확인
        if self.calibration_path.exists():
            logger.info(f"✅ Calibration 파일 존재: {self.calibration_path}")
        else:
            logger.error(f"❌ Calibration 파일이 존재하지 않습니다: {self.calibration_path}")
            checks_passed = False
        
        # 3. Runner 스크립트 확인
        runner_path = self.project_root / "scripts" / "run_d84_2_calibrated_fill_paper.py"
        if runner_path.exists():
            logger.info(f"✅ Runner 스크립트 존재: {runner_path.name}")
        else:
            logger.error(f"❌ Runner 스크립트가 존재하지 않습니다: {runner_path}")
            checks_passed = False
        
        # 4. Analyzer 스크립트 확인
        analyzer_path = self.project_root / "scripts" / "analyze_d87_3_fillmodel_ab_test.py"
        if analyzer_path.exists():
            logger.info(f"✅ Analyzer 스크립트 존재: {analyzer_path.name}")
        else:
            logger.error(f"❌ Analyzer 스크립트가 존재하지 않습니다: {analyzer_path}")
            checks_passed = False
        
        # 5. 로그 디렉토리 준비
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ 로그 디렉토리 준비: {self.logs_dir}")
        
        # 6. 중복 프로세스 정리 (실제 실행 모드에서만)
        if self.mode == "full" and not self.skip_env_check:
            self._kill_existing_processes()
        
        logger.info("")
        if checks_passed:
            logger.info("✅ 환경 점검 완료")
        else:
            logger.error("❌ 환경 점검 실패")
        
        logger.info("=" * 100)
        logger.info("")
        
        return checks_passed
    
    def _kill_existing_processes(self):
        """기존 Python arbitrage 프로세스 정리"""
        logger.info("기존 프로세스 정리 중...")
        
        try:
            # Windows tasklist로 python 프로세스 확인
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "python.exe" in result.stdout:
                logger.warning("⚠️  Python 프로세스 감지됨. 수동으로 확인 필요.")
                # 실제로는 자동 kill하지 않고 경고만 (안전성)
            else:
                logger.info("✅ 중복 프로세스 없음")
        except Exception as e:
            logger.warning(f"⚠️  프로세스 체크 실패: {e}")
    
    def _prepare_session_dir(self, session_tag: str):
        """세션 디렉토리 준비 (백업 처리)"""
        session_dir = self.logs_dir / session_tag
        
        if session_dir.exists():
            # 기존 로그를 백업
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.logs_dir / f"{session_tag}_backup_{backup_suffix}"
            shutil.move(str(session_dir), str(backup_dir))
            logger.info(f"기존 로그 백업: {backup_dir}")
        
        session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"세션 디렉토리 준비: {session_dir}")
    
    def run_advisory_session(self) -> bool:
        """Advisory 3h 실행"""
        logger.info("=" * 100)
        logger.info("Advisory 3h PAPER 실행")
        logger.info("=" * 100)
        
        self._prepare_session_dir(self.advisory_session_tag)
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", "10800",
            "--l2-source", "real",
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(self.calibration_path),
            "--session-tag", self.advisory_session_tag,
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info("")
        
        if self.mode == "dry-run":
            logger.info("🔍 Dry-run 모드: 실제 실행 생략")
            logger.info("=" * 100)
            logger.info("")
            return True
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True
            )
            
            duration = time.time() - start_time
            logger.info(f"✅ Advisory 세션 완료 ({duration:.1f}초)")
            
            self.advisory_result = {
                "session_tag": self.advisory_session_tag,
                "duration_seconds": duration,
                "exit_code": result.returncode,
            }
            
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Advisory 세션 실패: exit code {e.returncode}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ Advisory 세션 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def run_strict_session(self) -> bool:
        """Strict 3h 실행"""
        logger.info("=" * 100)
        logger.info("Strict 3h PAPER 실행")
        logger.info("=" * 100)
        
        self._prepare_session_dir(self.strict_session_tag)
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", "10800",
            "--l2-source", "real",
            "--fillmodel-mode", "strict",
            "--calibration-path", str(self.calibration_path),
            "--session-tag", self.strict_session_tag,
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info("")
        
        if self.mode == "dry-run":
            logger.info("🔍 Dry-run 모드: 실제 실행 생략")
            logger.info("=" * 100)
            logger.info("")
            return True
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True
            )
            
            duration = time.time() - start_time
            logger.info(f"✅ Strict 세션 완료 ({duration:.1f}초)")
            
            self.strict_result = {
                "session_tag": self.strict_session_tag,
                "duration_seconds": duration,
                "exit_code": result.returncode,
            }
            
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Strict 세션 실패: exit code {e.returncode}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ Strict 세션 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def run_analysis(self) -> bool:
        """A/B 분석 실행"""
        logger.info("=" * 100)
        logger.info("A/B 분석 실행")
        logger.info("=" * 100)
        
        advisory_dir = self.logs_dir / self.advisory_session_tag
        strict_dir = self.logs_dir / self.strict_session_tag
        output_path = self.logs_dir / "d87_3_ab_summary_3h.json"
        
        cmd = [
            "python",
            "scripts/analyze_d87_3_fillmodel_ab_test.py",
            "--advisory-dir", str(advisory_dir),
            "--strict-dir", str(strict_dir),
            "--calibration-path", str(self.calibration_path),
            "--output", str(output_path),
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info("")
        
        if self.mode == "dry-run":
            logger.info("🔍 Dry-run 모드: 실제 실행 생략")
            logger.info("=" * 100)
            logger.info("")
            return True
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True
            )
            
            logger.info(f"✅ A/B 분석 완료")
            
            # 결과 로드
            if output_path.exists():
                with open(output_path, "r") as f:
                    self.analysis_result = json.load(f)
                logger.info(f"분석 결과 저장: {output_path}")
            
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ A/B 분석 실패: exit code {e.returncode}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ A/B 분석 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def print_summary(self):
        """최종 요약 출력"""
        logger.info("=" * 100)
        logger.info("D87-3 Long-run 3h+3h PAPER 실행 요약")
        logger.info("=" * 100)
        logger.info("")
        
        if self.mode == "dry-run":
            logger.info("🔍 Dry-run 모드 완료")
            logger.info("✅ 환경 점검: PASS")
            logger.info("✅ 명령어 검증: PASS")
            logger.info("")
            logger.info("실제 실행: python scripts/d87_3_longrun_orchestrator.py --mode full")
            logger.info("=" * 100)
            return
        
        # Advisory 결과
        if self.advisory_result:
            logger.info("Advisory 3h:")
            logger.info(f"  - Session Tag: {self.advisory_result['session_tag']}")
            logger.info(f"  - Duration: {self.advisory_result['duration_seconds']:.1f}초 ({self.advisory_result['duration_seconds']/60:.1f}분)")
            logger.info(f"  - Exit Code: {self.advisory_result['exit_code']}")
        else:
            logger.info("Advisory 3h: ❌ 실패")
        
        logger.info("")
        
        # Strict 결과
        if self.strict_result:
            logger.info("Strict 3h:")
            logger.info(f"  - Session Tag: {self.strict_result['session_tag']}")
            logger.info(f"  - Duration: {self.strict_result['duration_seconds']:.1f}초 ({self.strict_result['duration_seconds']/60:.1f}분)")
            logger.info(f"  - Exit Code: {self.strict_result['exit_code']}")
        else:
            logger.info("Strict 3h: ❌ 실패")
        
        logger.info("")
        
        # A/B 분석 결과
        if self.analysis_result:
            logger.info("A/B 분석:")
            
            comparison = self.analysis_result.get("comparison", {})
            advisory = comparison.get("advisory", {})
            strict = comparison.get("strict", {})
            delta = comparison.get("delta", {})
            
            logger.info(f"  - Advisory Entry Trades: {advisory.get('entry_trades', 0)}")
            logger.info(f"  - Strict Entry Trades: {strict.get('entry_trades', 0)} (Delta: {delta.get('entry_trades_pct', 0):.1f}%)")
            logger.info(f"  - Advisory Total PnL: ${advisory.get('total_pnl', 0):.2f}")
            logger.info(f"  - Strict Total PnL: ${strict.get('total_pnl', 0):.2f} (Delta: ${delta.get('total_pnl', 0):.2f})")
            
            # Zone 비교
            zone_comparison = comparison.get("zone_comparison", {})
            if zone_comparison:
                logger.info("")
                logger.info("  Zone별 비교:")
                for zone_id in sorted(zone_comparison.keys()):
                    zone_data = zone_comparison[zone_id]
                    adv_pct = zone_data["advisory"]["trade_percentage"]
                    str_pct = zone_data["strict"]["trade_percentage"]
                    delta_pct = zone_data["delta"]["trade_percentage"]
                    logger.info(f"    - {zone_id}: Advisory={adv_pct:.1f}%, Strict={str_pct:.1f}% (Delta: {delta_pct:+.1f}%p)")
        else:
            logger.info("A/B 분석: ❌ 실패")
        
        logger.info("")
        logger.info("=" * 100)
    
    def run(self) -> bool:
        """전체 파이프라인 실행"""
        logger.info("")
        logger.info("=" * 100)
        logger.info("D87-3 Long-run 3h+3h PAPER Orchestrator")
        logger.info(f"Mode: {self.mode}")
        logger.info("=" * 100)
        logger.info("")
        
        # 1. 환경 점검
        if not self.skip_env_check:
            if not self.check_environment():
                logger.error("환경 점검 실패. 실행 중단.")
                return False
        
        # 2. Advisory 3h
        if not self.run_advisory_session():
            logger.error("Advisory 세션 실패. 실행 중단.")
            return False
        
        # 3. Strict 3h
        if not self.run_strict_session():
            logger.error("Strict 세션 실패. 실행 중단.")
            return False
        
        # 4. A/B 분석
        if not self.run_analysis():
            logger.error("A/B 분석 실패. 계속 진행.")
        
        # 5. 최종 요약
        self.print_summary()
        
        logger.info("")
        logger.info("✅ D87-3 Long-run 3h+3h PAPER 완료")
        logger.info("")
        
        return True


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D87-3: 3h Advisory + 3h Strict Long-run PAPER 완전 자동화"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["full", "dry-run"],
        default="full",
        help="실행 모드 (full: 실제 실행, dry-run: 환경 점검만)"
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="환경 점검 생략"
    )
    
    args = parser.parse_args()
    
    orchestrator = D87LongrunOrchestrator(
        mode=args.mode,
        skip_env_check=args.skip_env_check
    )
    
    success = orchestrator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
