#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3.3: Post-execution 자동 분석 스크립트

Orchestrator 완료 후 자동으로:
1. A/B 분석 실행
2. Acceptance Criteria 평가
3. 결과 리포트 생성

Usage:
    python scripts/d87_3_post_analysis.py
"""

import json
import logging
import subprocess
import sys
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


class D87PostAnalyzer:
    """D87-3.3 Post-execution 분석기"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "d87-3"
        
        self.advisory_dir = self.logs_dir / "d87_3_advisory_3h"
        self.strict_dir = self.logs_dir / "d87_3_strict_3h"
        self.calibration_path = self.project_root / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        self.ab_summary_path = self.logs_dir / "d87_3_ab_summary_3h.json"
        self.acceptance_path = self.logs_dir / "d87_3_acceptance_3h.json"
        self.report_path = self.logs_dir / "d87_3_final_report_3h.txt"
    
    def check_completion(self) -> tuple[bool, str]:
        """실행 완료 여부 확인"""
        # Advisory KPI 파일 확인
        advisory_kpi_files = list(self.advisory_dir.glob("kpi_*.json"))
        if not advisory_kpi_files:
            return False, "Advisory 세션 미완료 (KPI 파일 없음)"
        
        # Strict KPI 파일 확인
        strict_kpi_files = list(self.strict_dir.glob("kpi_*.json"))
        if not strict_kpi_files:
            return False, "Strict 세션 미완료 (KPI 파일 없음)"
        
        # Duration 확인
        with open(advisory_kpi_files[0], 'r') as f:
            advisory_kpi = json.load(f)
        
        with open(strict_kpi_files[0], 'r') as f:
            strict_kpi = json.load(f)
        
        adv_duration = advisory_kpi.get("actual_duration_seconds", 0)
        str_duration = strict_kpi.get("actual_duration_seconds", 0)
        
        min_duration = 10800 * 0.95  # 3h의 95%
        
        if adv_duration < min_duration:
            return False, f"Advisory 세션 미완료 ({adv_duration:.0f}초 < {min_duration:.0f}초)"
        
        if str_duration < min_duration:
            return False, f"Strict 세션 미완료 ({str_duration:.0f}초 < {min_duration:.0f}초)"
        
        return True, "모든 세션 완료"
    
    def run_analyzer(self) -> bool:
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
            "--output", str(self.ab_summary_path),
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
    
    def evaluate_criteria(self) -> Dict[str, Any]:
        """Acceptance Criteria 평가"""
        logger.info("=" * 100)
        logger.info("ACCEPTANCE CRITERIA 평가")
        logger.info("=" * 100)
        
        if not self.ab_summary_path.exists():
            logger.error("A/B 분석 결과 파일이 존재하지 않습니다")
            return {}
        
        with open(self.ab_summary_path, 'r') as f:
            ab_result = json.load(f)
        
        comparison = ab_result.get("comparison", {})
        advisory = comparison.get("advisory", {})
        strict = comparison.get("strict", {})
        zone_comparison = comparison.get("zone_comparison", {})
        
        # C1: 완주
        c1_pass = True
        c1_reason = "Advisory & Strict 3h 완주"
        c1_value = {"advisory": "완료", "strict": "완료"}
        
        # C2: 데이터 충분성
        adv_events = advisory.get("total_fill_events", 0)
        str_events = strict.get("total_fill_events", 0)
        c2_pass = adv_events >= 1000 and str_events >= 1000
        c2_reason = f"Advisory={adv_events}, Strict={str_events} (목표: ≥1000)"
        c2_value = {"advisory": adv_events, "strict": str_events, "target": 1000}
        
        # C3: Z2 집중 효과
        adv_z2_pct = zone_comparison.get("Z2", {}).get("advisory", {}).get("trade_percentage", 0)
        str_z2_pct = zone_comparison.get("Z2", {}).get("strict", {}).get("trade_percentage", 0)
        z2_delta = str_z2_pct - adv_z2_pct
        c3_pass = z2_delta >= 10.0
        c3_reason = f"Z2 Delta = {z2_delta:+.1f}%p (목표: ≥+10%p)"
        c3_value = {"advisory": adv_z2_pct, "strict": str_z2_pct, "delta": z2_delta, "target": 10.0}
        
        # C4: Z1/Z3/Z4 회피
        adv_other_pct = sum(
            zone_comparison.get(z, {}).get("advisory", {}).get("trade_percentage", 0)
            for z in ["Z1", "Z3", "Z4"]
        )
        str_other_pct = sum(
            zone_comparison.get(z, {}).get("strict", {}).get("trade_percentage", 0)
            for z in ["Z1", "Z3", "Z4"]
        )
        other_delta = str_other_pct - adv_other_pct
        c4_pass = other_delta <= -5.0
        c4_reason = f"Z1+Z3+Z4 Delta = {other_delta:+.1f}%p (목표: ≤-5%p)"
        c4_value = {"advisory": adv_other_pct, "strict": str_other_pct, "delta": other_delta, "target": -5.0}
        
        # C5: Z2 사이즈 증가
        adv_z2_size = zone_comparison.get("Z2", {}).get("advisory", {}).get("avg_size", 0)
        str_z2_size = zone_comparison.get("Z2", {}).get("strict", {}).get("avg_size", 0)
        size_ratio = (str_z2_size / adv_z2_size) if adv_z2_size > 0 else 0
        c5_pass = size_ratio >= 1.05
        c5_reason = f"Z2 Size Ratio = {size_ratio:.3f} (목표: ≥1.05)"
        c5_value = {"advisory": adv_z2_size, "strict": str_z2_size, "ratio": size_ratio, "target": 1.05}
        
        # C6: 리스크 균형
        adv_pnl = advisory.get("total_pnl", 0)
        str_pnl = strict.get("total_pnl", 0)
        pnl_ratio = (str_pnl / adv_pnl) if adv_pnl != 0 else 0
        c6_pass = 0.8 <= pnl_ratio <= 1.2
        c6_reason = f"PnL Ratio = {pnl_ratio:.3f} (목표: 0.8~1.2)"
        c6_value = {"advisory": adv_pnl, "strict": str_pnl, "ratio": pnl_ratio, "target_min": 0.8, "target_max": 1.2}
        
        criteria = {
            "C1": {"id": "C1", "name": "완주", "pass": c1_pass, "reason": c1_reason, "value": c1_value, "priority": "Critical"},
            "C2": {"id": "C2", "name": "데이터 충분성", "pass": c2_pass, "reason": c2_reason, "value": c2_value, "priority": "Critical"},
            "C3": {"id": "C3", "name": "Z2 집중 효과", "pass": c3_pass, "reason": c3_reason, "value": c3_value, "priority": "Critical"},
            "C4": {"id": "C4", "name": "Z1/Z3/Z4 회피", "pass": c4_pass, "reason": c4_reason, "value": c4_value, "priority": "High"},
            "C5": {"id": "C5", "name": "Z2 사이즈 증가", "pass": c5_pass, "reason": c5_reason, "value": c5_value, "priority": "High"},
            "C6": {"id": "C6", "name": "리스크 균형", "pass": c6_pass, "reason": c6_reason, "value": c6_value, "priority": "Medium"},
        }
        
        # 로그 출력
        logger.info("")
        for cid, result in criteria.items():
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            logger.info(f"  {cid} ({result['priority']}): {status} - {result['reason']}")
        
        # 전체 판정
        critical_pass = all(criteria[c]["pass"] for c in ["C1", "C2", "C3"])
        high_pass = all(criteria[c]["pass"] for c in ["C4", "C5"])
        
        if critical_pass and high_pass:
            overall = "PASS"
            overall_emoji = "✅"
        elif critical_pass:
            overall = "CONDITIONAL_GO"
            overall_emoji = "⚠️"
        else:
            overall = "FAIL"
            overall_emoji = "❌"
        
        logger.info("")
        logger.info(f"최종 판정: {overall_emoji} {overall}")
        logger.info("=" * 100)
        
        result = {
            "criteria": criteria,
            "overall": overall,
            "overall_emoji": overall_emoji,
            "critical_pass": critical_pass,
            "high_pass": high_pass,
            "evaluation_time": datetime.now().isoformat(),
            "ab_summary": ab_result,
        }
        
        # JSON 저장
        with open(self.acceptance_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def generate_report(self, acceptance_result: Dict[str, Any]):
        """최종 리포트 생성"""
        logger.info("=" * 100)
        logger.info("최종 리포트 생성")
        logger.info("=" * 100)
        
        lines = []
        lines.append("=" * 100)
        lines.append("D87-3.3: 3h+3h PAPER Long-run Validation 결과")
        lines.append("=" * 100)
        lines.append("")
        
        # 실행 정보
        lines.append(f"실행 일시: {acceptance_result.get('evaluation_time', 'N/A')}")
        lines.append("")
        
        # Advisory 세션
        ab_summary = acceptance_result.get("ab_summary", {})
        advisory_summary = ab_summary.get("advisory_summary", {})
        strict_summary = ab_summary.get("strict_summary", {})
        
        lines.append("## Advisory 3h 세션")
        lines.append(f"  - Fill Events: {advisory_summary.get('total_events', 0)}")
        lines.append(f"  - PnL: ${advisory_summary.get('total_pnl', 0):.2f}")
        lines.append("")
        
        lines.append("## Strict 3h 세션")
        lines.append(f"  - Fill Events: {strict_summary.get('total_events', 0)}")
        lines.append(f"  - PnL: ${strict_summary.get('total_pnl', 0):.2f}")
        lines.append("")
        
        # Acceptance Criteria
        lines.append("## Acceptance Criteria 평가")
        lines.append("")
        criteria = acceptance_result.get("criteria", {})
        for cid in ["C1", "C2", "C3", "C4", "C5", "C6"]:
            c = criteria.get(cid, {})
            status = "✅ PASS" if c.get("pass") else "❌ FAIL"
            lines.append(f"{cid} ({c.get('priority', 'Unknown')}): {status}")
            lines.append(f"  - {c.get('name', 'Unknown')}")
            lines.append(f"  - {c.get('reason', 'N/A')}")
            lines.append("")
        
        # 최종 판정
        overall = acceptance_result.get("overall", "UNKNOWN")
        overall_emoji = acceptance_result.get("overall_emoji", "")
        lines.append(f"## 최종 판정: {overall_emoji} {overall}")
        lines.append("")
        
        if overall == "PASS":
            lines.append("모든 Critical 및 High Priority Criteria 통과")
            lines.append("D87-3.3 Long-run Validation 완료")
        elif overall == "CONDITIONAL_GO":
            lines.append("Critical Criteria 통과, 일부 High Priority 미달")
            lines.append("조건부 진행 가능, 개선 사항 검토 필요")
        else:
            lines.append("Critical Criteria 미달")
            lines.append("D87-3.3 실패, 원인 분석 및 재검증 필요")
        
        lines.append("")
        lines.append("=" * 100)
        
        report_text = "\n".join(lines)
        
        # 파일 저장
        with open(self.report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        # 콘솔 출력
        print("\n" + report_text)
        
        logger.info(f"✅ 최종 리포트 저장: {self.report_path}")
    
    def run(self):
        """전체 분석 실행"""
        logger.info("D87-3.3 Post-execution 분석 시작")
        logger.info("")
        
        # 1. 완료 여부 확인
        completed, status_msg = self.check_completion()
        logger.info(f"완료 여부: {status_msg}")
        
        if not completed:
            logger.error("세션이 완료되지 않았습니다. 분석을 중단합니다.")
            return
        
        # 2. A/B 분석
        if not self.run_analyzer():
            logger.error("A/B 분석 실패")
            return
        
        # 3. Acceptance Criteria 평가
        acceptance_result = self.evaluate_criteria()
        
        if not acceptance_result:
            logger.error("Acceptance Criteria 평가 실패")
            return
        
        # 4. 최종 리포트 생성
        self.generate_report(acceptance_result)
        
        logger.info("")
        logger.info("=" * 100)
        logger.info("✅ D87-3.3 Post-execution 분석 완료")
        logger.info("=" * 100)


def main():
    """메인 함수"""
    analyzer = D87PostAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
