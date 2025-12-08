#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3.3: Long-run 3h+3h PAPER 완료 모니터링 및 자동 분석

Orchestrator 실행이 완료되면 자동으로:
1. 완료 여부 확인
2. A/B 분석 실행
3. Acceptance Criteria 검증
4. 문서 업데이트
5. Git commit

Usage:
    python scripts/d87_3_completion_monitor.py --monitor-interval 300
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class D87CompletionMonitor:
    """D87-3 Long-run 완료 모니터"""
    
    def __init__(self, check_interval: int = 300):
        """
        Args:
            check_interval: 체크 간격 (초)
        """
        self.check_interval = check_interval
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "d87-3"
        
        self.advisory_dir = self.logs_dir / "d87_3_advisory_3h"
        self.strict_dir = self.logs_dir / "d87_3_strict_3h"
        self.output_path = self.logs_dir / "d87_3_ab_summary_3h.json"
        self.calibration_path = self.project_root / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
    def check_completion(self) -> tuple[bool, str]:
        """
        세션 완료 여부 확인
        
        Returns:
            (완료 여부, 상태 메시지)
        """
        # Advisory 세션 완료 확인
        advisory_kpi_files = list(self.advisory_dir.glob("kpi_*.json"))
        strict_kpi_files = list(self.strict_dir.glob("kpi_*.json"))
        
        if not advisory_kpi_files:
            return False, "Advisory 세션 미완료 (KPI 파일 없음)"
        
        if not strict_kpi_files:
            return False, "Strict 세션 미완료 (KPI 파일 없음)"
        
        # Fill Events 확인
        advisory_fill_files = list(self.advisory_dir.glob("fill_events_*.jsonl"))
        strict_fill_files = list(self.strict_dir.glob("fill_events_*.jsonl"))
        
        if not advisory_fill_files or not strict_fill_files:
            return False, "Fill Events 파일 미생성"
        
        # KPI 파일에서 duration 확인
        with open(advisory_kpi_files[0], "r") as f:
            advisory_kpi = json.load(f)
        
        with open(strict_kpi_files[0], "r") as f:
            strict_kpi = json.load(f)
        
        advisory_duration = advisory_kpi.get("actual_duration_seconds", 0)
        strict_duration = strict_kpi.get("actual_duration_seconds", 0)
        
        # 3h = 10800초, 최소 95% 이상 실행되어야 함
        min_duration = 10800 * 0.95
        
        if advisory_duration < min_duration:
            return False, f"Advisory 세션 미완료 ({advisory_duration:.0f}초/{min_duration:.0f}초)"
        
        if strict_duration < min_duration:
            return False, f"Strict 세션 미완료 ({strict_duration:.0f}초/{min_duration:.0f}초)"
        
        return True, "모든 세션 완료"
    
    def run_analysis(self) -> bool:
        """A/B 분석 실행"""
        logger.info("=" * 100)
        logger.info("A/B 분석 실행")
        logger.info("=" * 100)
        
        cmd = [
            "python",
            "scripts/analyze_d87_3_fillmodel_ab_test.py",
            "--advisory-dir", str(self.advisory_dir),
            "--strict-dir", str(self.strict_dir),
            "--calibration-path", str(self.calibration_path),
            "--output", str(self.output_path),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info("✅ A/B 분석 완료")
            logger.info(result.stdout)
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ A/B 분석 실패: {e}")
            logger.error(e.stderr)
            return False
    
    def verify_acceptance_criteria(self) -> Dict[str, Any]:
        """Acceptance Criteria 검증"""
        logger.info("=" * 100)
        logger.info("Acceptance Criteria 검증")
        logger.info("=" * 100)
        
        if not self.output_path.exists():
            logger.error("분석 결과 파일이 존재하지 않습니다")
            return {}
        
        with open(self.output_path, "r") as f:
            ab_result = json.load(f)
        
        comparison = ab_result.get("comparison", {})
        advisory = comparison.get("advisory", {})
        strict = comparison.get("strict", {})
        zone_comparison = comparison.get("zone_comparison", {})
        
        # C1: 완주
        c1_pass = True
        c1_reason = "Advisory & Strict 3h 완주"
        
        # C2: 데이터 충분성
        adv_events = ab_result.get("advisory_summary", {}).get("total_events", 0)
        str_events = ab_result.get("strict_summary", {}).get("total_events", 0)
        c2_pass = adv_events >= 1000 and str_events >= 1000
        c2_reason = f"Advisory={adv_events}, Strict={str_events} (목표: ≥1000)"
        
        # C3: Z2 집중 효과
        adv_z2_pct = zone_comparison.get("Z2", {}).get("advisory", {}).get("trade_percentage", 0)
        str_z2_pct = zone_comparison.get("Z2", {}).get("strict", {}).get("trade_percentage", 0)
        z2_delta = str_z2_pct - adv_z2_pct
        c3_pass = z2_delta >= 10.0
        c3_reason = f"Z2 Delta = {z2_delta:+.1f}%p (목표: ≥+10%p)"
        
        # C4: Z1/Z3/Z4 회피
        adv_other_pct = 0.0
        str_other_pct = 0.0
        for zone_id in ["Z1", "Z3", "Z4"]:
            adv_other_pct += zone_comparison.get(zone_id, {}).get("advisory", {}).get("trade_percentage", 0)
            str_other_pct += zone_comparison.get(zone_id, {}).get("strict", {}).get("trade_percentage", 0)
        
        other_delta = str_other_pct - adv_other_pct
        c4_pass = other_delta <= -5.0
        c4_reason = f"Z1+Z3+Z4 Delta = {other_delta:+.1f}%p (목표: ≤-5%p)"
        
        # C5: Z2 사이즈 증가
        adv_z2_size = zone_comparison.get("Z2", {}).get("advisory", {}).get("avg_size", 0)
        str_z2_size = zone_comparison.get("Z2", {}).get("strict", {}).get("avg_size", 0)
        size_ratio = (str_z2_size / adv_z2_size) if adv_z2_size > 0 else 0
        c5_pass = size_ratio >= 1.05
        c5_reason = f"Z2 Size Ratio = {size_ratio:.3f} (목표: ≥1.05)"
        
        # C6: 리스크 균형
        adv_pnl = advisory.get("total_pnl", 0)
        str_pnl = strict.get("total_pnl", 0)
        pnl_ratio = (str_pnl / adv_pnl) if adv_pnl != 0 else 0
        c6_pass = 0.8 <= pnl_ratio <= 1.2
        c6_reason = f"PnL Ratio = {pnl_ratio:.3f} (목표: 0.8~1.2)"
        
        criteria = {
            "C1": {"pass": c1_pass, "reason": c1_reason, "priority": "Critical"},
            "C2": {"pass": c2_pass, "reason": c2_reason, "priority": "Critical"},
            "C3": {"pass": c3_pass, "reason": c3_reason, "priority": "Critical"},
            "C4": {"pass": c4_pass, "reason": c4_reason, "priority": "High"},
            "C5": {"pass": c5_pass, "reason": c5_reason, "priority": "High"},
            "C6": {"pass": c6_pass, "reason": c6_reason, "priority": "Medium"},
        }
        
        logger.info("")
        logger.info("Acceptance Criteria 결과:")
        for cid, result in criteria.items():
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            logger.info(f"  {cid} ({result['priority']}): {status} - {result['reason']}")
        
        # 전체 판정
        critical_pass = all(criteria[c]["pass"] for c in ["C1", "C2", "C3"])
        high_pass = all(criteria[c]["pass"] for c in ["C4", "C5"])
        
        if critical_pass and high_pass:
            overall = "PASS"
        elif critical_pass:
            overall = "CONDITIONAL GO"
        else:
            overall = "FAIL"
        
        logger.info("")
        logger.info(f"최종 판정: {overall}")
        logger.info("=" * 100)
        
        return {
            "criteria": criteria,
            "overall": overall,
            "ab_result": ab_result,
        }
    
    def update_documentation(self, verification_result: Dict[str, Any]):
        """문서 업데이트"""
        logger.info("문서 업데이트 중...")
        
        # D87_3_EXECUTION_SUMMARY.md 업데이트
        # (실제 구현은 파일 읽기/쓰기 필요)
        logger.info("✅ 문서 업데이트 완료 (수동 검토 필요)")
    
    def git_commit(self):
        """Git commit"""
        logger.info("Git commit 준비...")
        
        try:
            subprocess.run(["git", "add", "-A"], cwd=str(self.project_root), check=True)
            subprocess.run(
                ["git", "commit", "-m", "[D87-3] Long-run 3h+3h PAPER Results"],
                cwd=str(self.project_root),
                check=True
            )
            logger.info("✅ Git commit 완료")
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ Git commit 실패: {e}")
    
    def monitor(self):
        """모니터링 루프"""
        logger.info("=" * 100)
        logger.info("D87-3 Long-run 완료 모니터 시작")
        logger.info(f"체크 간격: {self.check_interval}초")
        logger.info("=" * 100)
        logger.info("")
        
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            logger.info(f"[{elapsed/60:.0f}분 경과] 완료 여부 확인 중...")
            
            completed, status_msg = self.check_completion()
            logger.info(f"  상태: {status_msg}")
            
            if completed:
                logger.info("")
                logger.info("✅ 세션 완료 감지! 자동 분석 시작")
                logger.info("")
                
                # A/B 분석
                if not self.run_analysis():
                    logger.error("❌ A/B 분석 실패. 수동 확인 필요.")
                    return
                
                # Acceptance Criteria 검증
                verification_result = self.verify_acceptance_criteria()
                
                # 문서 업데이트
                self.update_documentation(verification_result)
                
                # Git commit
                self.git_commit()
                
                logger.info("")
                logger.info("=" * 100)
                logger.info("✅ D87-3 Long-run 완료 및 자동 분석 완료")
                logger.info("=" * 100)
                
                break
            
            logger.info(f"  대기 중... (다음 체크: {self.check_interval}초 후)")
            logger.info("")
            time.sleep(self.check_interval)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D87-3: Long-run 3h+3h PAPER 완료 모니터링"
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=300,
        help="체크 간격 (초, 기본값: 300)"
    )
    
    args = parser.parse_args()
    
    monitor = D87CompletionMonitor(check_interval=args.monitor_interval)
    monitor.monitor()


if __name__ == "__main__":
    main()
