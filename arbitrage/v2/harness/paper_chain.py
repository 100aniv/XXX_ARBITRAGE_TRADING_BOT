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
    """
    
    def __init__(
        self,
        durations: List[int],
        phases: List[str],
        db_mode: str = "strict",
        evidence_root: str = "logs/evidence",
    ):
        """
        Initialize Chain Runner
        
        Args:
            durations: 각 phase별 실행 시간 (분) [20, 60, 180]
            phases: 각 phase 이름 ["smoke", "baseline", "longrun"]
            db_mode: DB 모드 (strict/optional/off)
            evidence_root: Evidence 루트 경로
        """
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
        logger.info(f"[ChainRunner] durations: {durations}")
        logger.info(f"[ChainRunner] phases: {phases}")
        logger.info(f"[ChainRunner] db_mode: {db_mode}")
    
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
                logger.error(f"[ChainRunner] ❌ Phase {phase} FAILED, aborting chain")
                self._save_chain_summary(success=False, failed_phase=phase)
                return 1
            
            logger.info(f"[ChainRunner] ✅ Phase {phase} PASSED")
        
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
        # paper_runner 실행
        cmd = [
            sys.executable,
            "-m", "arbitrage.v2.harness.paper_runner",
            "--duration", str(duration),
            "--phase", phase,
            "--db-mode", self.db_mode,
        ]
        
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


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="D204-2 Paper Execution Chain Runner")
    parser.add_argument(
        "--durations",
        type=str,
        default="1,2,3",
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
    )
    
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
