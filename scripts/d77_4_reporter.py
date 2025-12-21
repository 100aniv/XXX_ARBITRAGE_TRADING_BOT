#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-4 Reporter - 최종 리포트 자동 생성

템플릿 기반 리포트 생성 및 D_ROADMAP 업데이트
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class D77Reporter:
    """D77-4 리포트 생성"""
    
    def __init__(self, project_root: Path, run_id: str):
        self.project_root = project_root
        self.run_id = run_id
        self.log_dir = project_root / "logs" / "d77-4" / run_id
        
        self._setup_logging()
    
    def _setup_logging(self):
        log_file = self.log_dir / "reporter.log"
        self._log_handler = logging.FileHandler(log_file, encoding='utf-8')
        self._log_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.INFO)
    
    def __del__(self):
        if hasattr(self, '_log_handler'):
            logger.removeHandler(self._log_handler)
            self._log_handler.close()
    
    def generate_report(self, analysis_result_path: Path) -> bool:
        """리포트 생성
        
        Args:
            analysis_result_path: 분석 결과 JSON 경로
        
        Returns:
            성공 여부
        """
        logger.info("[D77-4 Reporter] 리포트 생성 시작")
        
        # 분석 결과 로드
        if not analysis_result_path.exists():
            logger.error(f"분석 결과 없음: {analysis_result_path}")
            return False
        
        with open(analysis_result_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        
        # 템플릿 로드
        template_path = self.project_root / "docs" / "D77_4_LONG_PAPER_VALIDATION_REPORT_TEMPLATE.md"
        if not template_path.exists():
            logger.error(f"템플릿 없음: {template_path}")
            return False
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # 자동 치환
        report = template
        report = report.replace("YYYY-MM-DD", datetime.now().strftime("%Y-%m-%d"))
        report = report.replace("[RUN_ID]", self.run_id)
        report = report.replace("[DECISION]", analysis["decision"])
        report = report.replace("[DECISION_REASON]", analysis["decision_reason"])
        
        # KPI 값 치환 (있으면)
        kpi = analysis.get("kpi", {})
        report = report.replace("[ROUND_TRIPS]", str(kpi.get("round_trips_completed", "N/A")))
        report = report.replace("[TOTAL_TRADES]", str(kpi.get("total_trades", "N/A")))
        report = report.replace("[WIN_RATE]", f"{kpi.get('win_rate_pct', 0):.1f}")
        report = report.replace("[TOTAL_PNL]", f"{kpi.get('total_pnl_usd', 0):.2f}")
        
        # 리포트 저장
        output_path = self.project_root / "docs" / f"D77_4_LONG_PAPER_VALIDATION_REPORT_{self.run_id}.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"리포트 저장: {output_path}")
        
        # D_ROADMAP 업데이트
        self._update_roadmap(analysis)
        
        return True
    
    def _update_roadmap(self, analysis: Dict):
        """D_ROADMAP.md 업데이트"""
        roadmap_path = self.project_root / "D_ROADMAP.md"
        if not roadmap_path.exists():
            logger.warning("D_ROADMAP.md 없음")
            return
        
        try:
            with open(roadmap_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # D77-4 Validation Phase 체크박스 업데이트
            decision = analysis["decision"]
            if "COMPLETE GO" in decision or "CONDITIONAL GO" in decision:
                status_mark = "✅"
            else:
                status_mark = "❌"
            
            # 간단한 치환 (정확한 위치는 수동 확인 필요)
            content = content.replace(
                "- [ ] ⏳ 60초 스모크 테스트 실행 (환경/런타임 검증)",
                f"- [x] {status_mark} 60초 스모크 테스트 실행 (환경/런타임 검증)"
            )
            content = content.replace(
                "- [ ] ⏳ 1h+ 본 실행 (KPI 32종 전수 수집)",
                f"- [x] {status_mark} 1h+ 본 실행 (KPI 32종 전수 수집)"
            )
            content = content.replace(
                "- [ ] ⏳ GO / CONDITIONAL GO / NO-GO 자동 판단",
                f"- [x] {status_mark} GO / CONDITIONAL GO / NO-GO 자동 판단: {decision}"
            )
            
            with open(roadmap_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"D_ROADMAP.md 업데이트 완료 ({decision})")
        except Exception as e:
            logger.warning(f"D_ROADMAP 업데이트 예외: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="D77-4 Reporter")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--analysis-result-path", required=True)
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    analysis_result_path = Path(args.analysis_result_path)
    
    reporter = D77Reporter(project_root, args.run_id)
    success = reporter.generate_report(analysis_result_path)
    
    print(f"{'='*60}")
    print(f"D77-4 Reporter: {'SUCCESS' if success else 'FAIL'}")
    print(f"{'='*60}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
