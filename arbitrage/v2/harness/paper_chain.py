"""
D204-2: Paper Execution Chain Runner

20m → 1h → 3h 자동 연쇄 실행

Purpose:
- Phase별 자동 실행 (smoke → baseline → longrun)
- 각 phase별 자동 검증 (exit code, db_inserts_failed, db_counts)
- 실패 시 즉시 중단 + 원인 로그

Usage:
    python -m arbitrage.v2.harness.paper_chain --durations 1,2,3 --phases smoke,baseline,longrun
    python -m arbitrage.v2.harness.paper_chain --durations 20,60,180 --phases smoke,baseline,longrun

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import argparse
import json
import logging
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChainRunner:
    """
    Chain Runner for Paper Execution Gate
    
    Flow:
        1. smoke (20m) → baseline (60m) → longrun (180m)
        2. 각 phase별 자동 검증
        3. 실패 시 즉시 중단
    
    D205-2 REOPEN: SSOT 프로파일 강제
        - longrun 라벨 + duration < 180 → FAIL (SSOT 위반)
        - quick 프로파일 (1,2,3)은 _q suffix 강제 (smoke_q/baseline_q/longrun_q)
    """
    
    # SSOT 프로파일 정의
    # D205-2 REOPEN-2: SSOT 프로파일 (phase명 통일, _q suffix 제거)
    SSOT_PROFILE = {
        "smoke": 20,
        "baseline": 60,
        "longrun": 180,
        "extended": 720,
    }
    
    def __init__(
        self,
        durations: List[int],
        phases: List[str],
        db_mode: str = "strict",
        evidence_root: str = "logs/evidence",
        profile: str = "ssot",
    ):
        """
        Initialize Chain Runner
        
        Args:
            durations: 각 phase별 실행 시간 (분) [20, 60, 180]
            phases: 각 phase 이름 ["smoke", "baseline", "longrun"]
            db_mode: DB 모드 (strict/optional/off)
            evidence_root: Evidence 루트 경로
            profile: SSOT 프로파일 (ssot/quick)
        """
        self.profile = profile
        
        # D205-2 REOPEN: SSOT 프로파일 검증
        for phase, duration in zip(phases, durations):
            self._validate_ssot_profile(phase, duration)
        
        self.durations = durations
        self.phases = phases
        self.db_mode = db_mode
        self.evidence_root = Path(evidence_root)
        
        # Chain 결과
        self.chain_id = f"d204_2_chain_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.chain_dir = self.evidence_root / self.chain_id
        self.chain_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: List[Dict[str, Any]] = []
        
        logger.info(f"[ChainRunner] Initialized")
        logger.info(f"[ChainRunner] chain_id: {self.chain_id}")
        logger.info(f"[ChainRunner] profile: {profile}")
        logger.info(f"[ChainRunner] durations: {durations}")
        logger.info(f"[ChainRunner] phases: {phases}")
        logger.info(f"[ChainRunner] db_mode: {db_mode}")
    
    def _validate_ssot_profile(self, phase: str, duration: int) -> None:
        """
        D205-2 REOPEN-2: SSOT 프로파일 검증 (phase명 통일)
        
        profile=ssot: SSOT 시간 준수 강제 (20/60/180/720m)
        profile=quick: phase명 동일, durations만 짧게 허용 (1/2/3m)
        
        _q suffix 제거: 체인 검증 파이프라인 통일
        """
        logger.info(f"[SSOT] Validating phase='{phase}', duration={duration}m, profile={self.profile}")
        
        # Rule 1: phase는 SSOT_PROFILE 키 중 하나여야 함
        if phase not in self.SSOT_PROFILE:
            logger.error(f" SSOT FAIL: phase '{phase}' not in {list(self.SSOT_PROFILE.keys())}")
            sys.exit(1)
        
        # Rule 2: profile=ssot → SSOT 시간 준수
        if self.profile == "ssot":
            expected = self.SSOT_PROFILE[phase]
            if duration < expected:
                logger.error(f" SSOT FAIL: phase '{phase}' requires {expected}m, got {duration}m")
                sys.exit(1)
            logger.info(f" SSOT PASS: phase '{phase}' duration {duration}m >= {expected}m")
        
        # Rule 3: profile=quick → 짧은 시간 허용 (phase명은 동일)
        elif self.profile == "quick":
            logger.info(f" SSOT PASS: profile=quick allows short duration for phase '{phase}'")
        
        else:
            logger.error(f" SSOT FAIL: unknown profile '{self.profile}'")
            sys.exit(1)
    
    def run(self) -> int:
        """
        Chain 실행
        
        Returns:
            0: 전체 성공
            1: 실패
        """
        logger.info("[ChainRunner] ========================================")
        logger.info(f"[ChainRunner] CHAIN EXECUTION START ({len(self.phases)} phases)")
        logger.info("[ChainRunner] ========================================")
        
        for idx, (duration, phase) in enumerate(zip(self.durations, self.phases), 1):
            logger.info(f"[ChainRunner] Phase {idx}/{len(self.phases)}: {phase} ({duration}m)")
            
            # Phase 실행
            success = self._run_phase(duration, phase)
            
            if not success:
                logger.error(f"[ChainRunner] Phase {phase} FAILED, aborting chain")
                self._save_chain_summary(success=False, failed_phase=phase)
                return 1
            
            logger.info(f"[ChainRunner] Phase {phase} PASSED")
        
        # 전체 성공
        logger.info("[ChainRunner] ========================================")
        logger.info(f"[ChainRunner] CHAIN EXECUTION COMPLETE ({len(self.phases)} phases)")
        logger.info("[ChainRunner] ========================================")
        self._save_chain_summary(success=True)
        return 0
    
    def _run_phase(self, duration: int, phase: str) -> bool:
        """
        단일 Phase 실행
        
        Args:
            duration: 실행 시간 (분)
            phase: Phase 이름
            
        Returns:
            True if success, False otherwise
        """
        # D205-2 REOPEN-2: phase명 통일 (_q suffix 제거 완료)
        runner_phase = phase
        
        # paper_runner 실행
        # D205-18-1: baseline/longrun은 REAL data 강제 (Paper-LIVE Parity)
        cmd = [
            sys.executable,
            "-m", "arbitrage.v2.harness.paper_runner",
            "--duration", str(duration),
            "--phase", runner_phase,
            "--db-mode", self.db_mode,
        ]
        
        # D205-18-1: 운영 검증 단계는 Real MarketData 필수
        if runner_phase in ["smoke", "baseline", "longrun"]:
            cmd.extend(["--use-real-data"])
            logger.info(f"[D205-18-1] ✅ REAL data enforced for phase '{runner_phase}'")
        
        logger.info(f"[ChainRunner] Running: {' '.join(cmd)}")
        
        try:
            # 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            
            # Exit code 확인
            if result.returncode != 0:
                logger.error(f"[ChainRunner] Phase {phase} failed with exit code {result.returncode}")
                logger.error(f"[ChainRunner] stderr: {result.stderr[:500]}")
                
                self.results.append({
                    "phase": phase,
                    "duration_minutes": duration,
                    "exit_code": result.returncode,
                    "status": "FAIL",
                    "reason": "Non-zero exit code",
                })
                return False
            
            # KPI 파일 확인
            kpi_file = Path(f"logs/evidence/d204_2_{phase}_{datetime.now().strftime('%Y%m%d_%H')}*/kpi_{phase}.json")
            kpi_files = list(Path("logs/evidence").glob(f"d204_2_{phase}_*/kpi_{phase}.json"))
            
            if not kpi_files:
                logger.error(f"[ChainRunner] KPI file not found for phase {phase}")
                self.results.append({
                    "phase": phase,
                    "duration_minutes": duration,
                    "exit_code": 0,
                    "status": "FAIL",
                    "reason": "KPI file not found",
                })
                return False
            
            # 최신 KPI 파일 선택
            kpi_file = sorted(kpi_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            
            with open(kpi_file, "r", encoding="utf-8") as f:
                kpi = json.load(f)
            
            # KPI 검증
            if not self._verify_kpi(kpi, phase):
                self.results.append({
                    "phase": phase,
                    "duration_minutes": duration,
                    "exit_code": 0,
                    "status": "FAIL",
                    "reason": "KPI verification failed",
                    "kpi": kpi,
                })
                return False
            
            # 성공
            self.results.append({
                "phase": phase,
                "duration_minutes": duration,
                "exit_code": 0,
                "status": "PASS",
                "kpi": kpi,
            })
            return True
            
        except Exception as e:
            logger.error(f"[ChainRunner] Phase {phase} execution error: {e}", exc_info=True)
            self.results.append({
                "phase": phase,
                "duration_minutes": duration,
                "exit_code": -1,
                "status": "FAIL",
                "reason": str(e),
            })
            return False
    
    def _verify_kpi(self, kpi: Dict[str, Any], phase: str) -> bool:
        """
        KPI 검증
        
        Args:
            kpi: KPI dict
            phase: Phase 이름
            
        Returns:
            True if pass, False otherwise
        """
        # 필수 필드 확인
        required_fields = [
            "opportunities_generated",
            "db_inserts_ok",
            "db_inserts_failed",
            "error_count",
        ]
        
        for field in required_fields:
            if field not in kpi:
                logger.error(f"[ChainRunner] KPI missing field: {field}")
                return False
        
        # Strict 검증
        if self.db_mode == "strict":
            # db_inserts_failed must be 0
            if kpi["db_inserts_failed"] > 0:
                logger.error(f"[ChainRunner] db_inserts_failed = {kpi['db_inserts_failed']} (expected 0)")
                return False
            
            # db_inserts_ok must be > 0
            if kpi["db_inserts_ok"] == 0:
                logger.error(f"[ChainRunner] db_inserts_ok = 0 (expected > 0)")
                return False
        
        logger.info(f"[ChainRunner] KPI verification PASS for phase {phase}")
        logger.info(f"[ChainRunner]   opportunities: {kpi['opportunities_generated']}")
        logger.info(f"[ChainRunner]   db_inserts_ok: {kpi['db_inserts_ok']}")
        logger.info(f"[ChainRunner]   db_inserts_failed: {kpi['db_inserts_failed']}")
        
        return True
    
    def _save_chain_summary(self, success: bool, failed_phase: str = None):
        """Chain 요약 저장"""
        summary = {
            "chain_id": self.chain_id,
            "timestamp": datetime.now().isoformat(),
            "durations": self.durations,
            "phases": self.phases,
            "db_mode": self.db_mode,
            "success": success,
            "failed_phase": failed_phase,
            "results": self.results,
        }
        
        summary_file = self.chain_dir / "chain_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[ChainRunner] Chain summary saved: {summary_file}")
        
        # D205-3: daily_report 자동 생성
        if success:
            self._generate_daily_report()
    
    def _generate_daily_report(self):
        """
        Daily report 자동 생성 (D205-3 CLOSEOUT)
        
        증거 SSOT:
        - 성공/실패 모두 evidence 폴더에 기록
        - 실패해도 체인을 FAIL로 만들지 않음 (운영상)
        - 대신 daily_report_status.json에 실패 원인 명확히 기록
        """
        today = datetime.now().date().strftime("%Y-%m-%d")
        report_path = self.chain_dir / f"daily_report_{today}.json"
        status_path = self.chain_dir / "daily_report_status.json"
        
        try:
            logger.info("[ChainRunner] Generating daily report...")
            logger.info(f"[ChainRunner] Target: {report_path}")
            
            cmd = [
                sys.executable, "-m", "arbitrage.v2.reporting.run_daily_report",
                "--date", today,
                "--run-id-prefix", self.chain_id.split("_20")[0],
                "--output-dir", str(self.chain_dir),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            # 증거 SSOT: 성공/실패 상태 기록
            status = {
                "timestamp": datetime.now().isoformat(),
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "report_path": str(report_path),
                "report_exists": report_path.exists(),
            }
            
            if result.returncode == 0:
                logger.info(f"[ChainRunner] Daily report generated: {report_path}")
                status["status"] = "SUCCESS"
                status["stdout"] = result.stdout[-500:] if result.stdout else ""
            else:
                logger.warning(f"[ChainRunner] Daily report generation failed (rc={result.returncode})")
                logger.warning(f"[ChainRunner] stderr: {result.stderr}")
                status["status"] = "FAILED"
                status["stderr"] = result.stderr
                status["stdout"] = result.stdout
            
            # 증거 저장
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[ChainRunner] Daily report status saved: {status_path}")
        
        except Exception as e:
            logger.error(f"[ChainRunner] Daily report generation exception: {e}")
            
            # 예외 발생 시에도 증거 기록
            status = {
                "timestamp": datetime.now().isoformat(),
                "status": "EXCEPTION",
                "error": str(e),
                "report_path": str(report_path),
                "report_exists": report_path.exists(),
            }
            
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2, ensure_ascii=False)


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="D204-2 Paper Execution Chain Runner (D205-2 REOPEN: SSOT 프로파일 강제)")
    parser.add_argument(
        "--durations",
        type=str,
        default="20,60,180",
        help="Duration for each phase (comma-separated, in minutes). Example: 20,60,180"
    )
    parser.add_argument(
        "--phases",
        type=str,
        default="smoke,baseline,longrun",
        help="Phase names (comma-separated). Example: smoke,baseline,longrun"
    )
    parser.add_argument(
        "--db-mode",
        default="strict",
        choices=["strict", "optional", "off"],
        help="DB mode"
    )
    parser.add_argument(
        "--profile",
        default="ssot",
        choices=["ssot", "quick"],
        help="SSOT profile: 'ssot' (20,60,180) or 'quick' (1,2,3 with _q suffix)"
    )
    
    args = parser.parse_args()
    
    # Parse durations and phases
    durations = [int(d.strip()) for d in args.durations.split(",")]
    phases = [p.strip() for p in args.phases.split(",")]
    
    if len(durations) != len(phases):
        logger.error(f"Durations and phases must have the same length")
        sys.exit(1)
    
    # Run chain
    runner = ChainRunner(
        durations=durations,
        phases=phases,
        db_mode=args.db_mode,
        profile=args.profile,
    )
    
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
