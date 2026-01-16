"""
D206-0: Artifact-First Preflight Checker

목적: engine_report.json 기반 검증 (Runner 참조 금지)
- Schema validation (필수 필드 존재)
- Gate validation (warnings=0, skips=0, errors=0)
- Wallclock drift (±5% 이내)
- DB integrity (closed_trades × 3 ≈ inserts_ok)
- Exit code (0=PASS, 1=FAIL)

Exit Code:
- 0: PASS (모든 검증 성공)
- 1: FAIL (하나라도 실패)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PreflightChecker:
    """
    D206-0: Artifact-First Preflight Checker
    
    Runner 객체 참조 금지. engine_report.json만 검증.
    """
    
    def __init__(self, evidence_dir: Path):
        """
        Args:
            evidence_dir: Evidence 디렉토리 (engine_report.json 위치)
        """
        self.evidence_dir = Path(evidence_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def load_engine_report(self) -> Dict[str, Any]:
        """
        Load engine_report.json
        
        Returns:
            Engine report dict
        
        Raises:
            FileNotFoundError: engine_report.json not found
            ValueError: Invalid JSON format
        """
        report_path = self.evidence_dir / "engine_report.json"
        
        if not report_path.exists():
            raise FileNotFoundError(f"engine_report.json not found: {report_path}")
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            logger.info(f"[D206-0] Engine report loaded: {report_path}")
            return report
        
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
    
    def validate_schema(self, report: Dict[str, Any]) -> bool:
        """
        Validate engine_report.json schema (필수 필드 존재)
        
        Args:
            report: Engine report dict
        
        Returns:
            True if schema is valid, False otherwise
        """
        required_fields = [
            "schema_version",
            "run_id",
            "git_sha",
            "started_at",
            "ended_at",
            "duration_sec",
            "mode",
            "exchanges",
            "symbols",
            "gate_validation",
            "trades",
            "heartbeat_summary",
            "db_integrity",
            "status"
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in report:
                missing_fields.append(field)
        
        if missing_fields:
            self.errors.append(f"Missing required fields: {missing_fields}")
            return False
        
        # Nested fields
        gate_fields = ["warnings_count", "skips_count", "errors_count", "exit_code"]
        for field in gate_fields:
            if field not in report.get("gate_validation", {}):
                self.errors.append(f"Missing gate_validation.{field}")
                return False
        
        heartbeat_fields = ["wallclock_duration_sec", "expected_duration_sec", "wallclock_drift_pct"]
        for field in heartbeat_fields:
            if field not in report.get("heartbeat_summary", {}):
                self.errors.append(f"Missing heartbeat_summary.{field}")
                return False
        
        db_fields = ["inserts_ok", "expected_inserts", "closed_trades"]
        for field in db_fields:
            if field not in report.get("db_integrity", {}):
                self.errors.append(f"Missing db_integrity.{field}")
                return False
        
        logger.info("[D206-0] Schema validation PASS")
        return True
    
    def validate_gate(self, report: Dict[str, Any]) -> bool:
        """
        Validate gate_validation (WARN=FAIL / SKIP=FAIL)
        
        Args:
            report: Engine report dict
        
        Returns:
            True if gate validation passes, False otherwise
        """
        gate = report.get("gate_validation", {})
        
        warnings_count = gate.get("warnings_count", 0)
        skips_count = gate.get("skips_count", 0)
        errors_count = gate.get("errors_count", 0)
        exit_code = gate.get("exit_code", 1)
        
        # WARN=FAIL
        if warnings_count > 0:
            self.errors.append(f"WARN=FAIL: warnings_count={warnings_count} (expected 0)")
            return False
        
        # SKIP=FAIL
        if skips_count > 0:
            self.errors.append(f"SKIP=FAIL: skips_count={skips_count} (expected 0)")
            return False
        
        # ERROR=FAIL
        if errors_count > 0:
            self.errors.append(f"ERROR=FAIL: errors_count={errors_count}")
            return False
        
        # Exit Code
        if exit_code != 0:
            self.errors.append(f"Exit code FAIL: exit_code={exit_code} (expected 0)")
            return False
        
        logger.info("[D206-0] Gate validation PASS (warnings=0, skips=0, errors=0, exit=0)")
        return True
    
    def validate_wallclock(self, report: Dict[str, Any]) -> bool:
        """
        Validate wallclock drift (±5% 이내)
        
        Args:
            report: Engine report dict
        
        Returns:
            True if wallclock validation passes, False otherwise
        """
        heartbeat = report.get("heartbeat_summary", {})
        
        wallclock_drift_pct = heartbeat.get("wallclock_drift_pct", 100.0)
        
        if wallclock_drift_pct > 5.0:
            self.errors.append(
                f"Wallclock drift FAIL: {wallclock_drift_pct:.2f}% (expected ≤5%)"
            )
            return False
        
        logger.info(f"[D206-0] Wallclock validation PASS (drift={wallclock_drift_pct:.2f}%)")
        return True
    
    def validate_db_integrity(self, report: Dict[str, Any]) -> bool:
        """
        Validate DB integrity (closed_trades × 3 ≈ inserts_ok, ±2 허용)
        
        Args:
            report: Engine report dict
        
        Returns:
            True if DB integrity validation passes, False otherwise
        """
        db = report.get("db_integrity", {})
        
        inserts_ok = db.get("inserts_ok", 0)
        expected_inserts = db.get("expected_inserts", 0)
        closed_trades = db.get("closed_trades", 0)
        
        # ±2 허용
        if abs(inserts_ok - expected_inserts) > 2:
            self.errors.append(
                f"DB integrity FAIL: inserts_ok={inserts_ok}, "
                f"expected={expected_inserts}, closed_trades={closed_trades}"
            )
            return False
        
        logger.info(
            f"[D206-0] DB integrity PASS (inserts={inserts_ok}, trades={closed_trades})"
        )
        return True
    
    def validate_status(self, report: Dict[str, Any]) -> bool:
        """
        Validate overall status
        
        Args:
            report: Engine report dict
        
        Returns:
            True if status is PASS, False otherwise
        """
        status = report.get("status", "FAIL")
        
        if status != "PASS":
            self.errors.append(f"Overall status FAIL: status={status}")
            return False
        
        logger.info("[D206-0] Overall status PASS")
        return True
    
    def run_all_checks(self) -> bool:
        """
        Run all validation checks
        
        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("=" * 60)
        logger.info("D206-0 Artifact-First Preflight Check")
        logger.info(f"Evidence dir: {self.evidence_dir}")
        logger.info("=" * 60)
        
        try:
            # Load engine report
            report = self.load_engine_report()
            
            # Run validations
            schema_ok = self.validate_schema(report)
            if not schema_ok:
                return False
            
            gate_ok = self.validate_gate(report)
            wallclock_ok = self.validate_wallclock(report)
            db_ok = self.validate_db_integrity(report)
            status_ok = self.validate_status(report)
            
            # Overall result
            all_ok = gate_ok and wallclock_ok and db_ok and status_ok
            
            logger.info("=" * 60)
            if all_ok:
                logger.info("PREFLIGHT PASS: All checks passed")
            else:
                logger.error("PREFLIGHT FAIL: One or more checks failed")
                for error in self.errors:
                    logger.error(f"  - {error}")
            logger.info("=" * 60)
            
            return all_ok
        
        except FileNotFoundError as e:
            logger.error(f"PREFLIGHT FAIL: {e}")
            return False
        
        except ValueError as e:
            logger.error(f"PREFLIGHT FAIL: {e}")
            return False
        
        except Exception as e:
            logger.error(f"PREFLIGHT FAIL: Unexpected error: {e}", exc_info=True)
            return False
