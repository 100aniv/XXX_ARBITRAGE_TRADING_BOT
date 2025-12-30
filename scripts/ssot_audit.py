#!/usr/bin/env python3
"""
D205-2: SSOT Integrity Audit

목적:
- D_ROADMAP.md에서 DONE 체크된 항목의 Evidence 존재 여부 자동 검증
- Evidence 없으면 FAIL (exit code != 0)

Usage:
    python scripts/ssot_audit.py
    python scripts/ssot_audit.py --fix  # 거짓 DONE을 PLANNED로 되돌림 (dry-run)

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import argparse
import json
import logging
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SSOTAuditor:
    """SSOT Integrity Auditor"""
    
    def __init__(self, roadmap_path: Path, fix_mode: bool = False):
        self.roadmap_path = roadmap_path
        self.fix_mode = fix_mode
        self.violations: List[Dict[str, Any]] = []
    
    def audit(self) -> int:
        """
        SSOT 감사 실행
        
        Returns:
            0: 위반 없음
            1: 위반 발견
        """
        logger.info("=" * 60)
        logger.info("SSOT Integrity Audit")
        logger.info("=" * 60)
        logger.info(f"Roadmap: {self.roadmap_path}")
        logger.info(f"Fix Mode: {self.fix_mode}")
        
        if not self.roadmap_path.exists():
            logger.error(f"Roadmap not found: {self.roadmap_path}")
            return 1
        
        # D_ROADMAP.md 읽기
        content = self.roadmap_path.read_text(encoding='utf-8')
        
        # DONE 항목 스캔
        violations = self._scan_done_items(content)
        
        if not violations:
            logger.info("=" * 60)
            logger.info("✅ SSOT Integrity Check: PASS")
            logger.info("=" * 60)
            return 0
        
        # 위반 보고
        self._report_violations(violations)
        
        # Fix mode
        if self.fix_mode:
            logger.warning("Fix mode is not implemented yet (dry-run only)")
        
        logger.error("=" * 60)
        logger.error(f"❌ SSOT Integrity Check: FAIL ({len(violations)} violations)")
        logger.error("=" * 60)
        
        return 1
    
    def _scan_done_items(self, content: str) -> List[Dict[str, Any]]:
        """
        DONE 항목 스캔 및 Evidence 검증
        
        패턴:
        - **상태:** DONE / ✅ DONE / DONE ✅
        - **Evidence:** 경로
        - logs/evidence/ 경로
        """
        violations = []
        
        # DONE 패턴
        done_pattern = r'\*\*상태:\*\*\s+(✅\s*DONE|DONE\s*✅|DONE)'
        
        # Evidence 패턴
        evidence_pattern = r'(Evidence:|evidence/|logs/evidence/)'
        
        lines = content.split('\n')
        current_section = None
        current_section_start = 0
        
        for i, line in enumerate(lines):
            # 섹션 시작 감지 (예: #### D204-2:, ### D205:)
            if re.match(r'^#{2,4}\s+D\d+', line):
                current_section = line.strip()
                current_section_start = i
            
            # DONE 체크 감지
            if re.search(done_pattern, line, re.IGNORECASE):
                if current_section:
                    # 해당 섹션에서 Evidence 경로 찾기
                    evidence_found = self._find_evidence_in_section(
                        lines, current_section_start, i + 50
                    )
                    
                    if not evidence_found:
                        violations.append({
                            'section': current_section,
                            'line': i + 1,
                            'reason': 'DONE but no Evidence found',
                            'snippet': line.strip()
                        })
        
        return violations
    
    def _find_evidence_in_section(
        self, 
        lines: List[str], 
        start: int, 
        end: int
    ) -> bool:
        """
        섹션 내에서 Evidence 경로 찾기
        
        Returns:
            True: Evidence 경로 발견
            False: Evidence 경로 없음
        """
        evidence_pattern = r'(Evidence:|evidence/|logs/evidence/|docs/.*/evidence/)'
        
        for i in range(start, min(end, len(lines))):
            if re.search(evidence_pattern, lines[i], re.IGNORECASE):
                # Evidence 경로 추출
                evidence_path = self._extract_evidence_path(lines[i])
                if evidence_path:
                    # 경로 존재 여부 확인
                    if self._check_evidence_exists(evidence_path):
                        return True
                    else:
                        logger.debug(f"Evidence path not found: {evidence_path}")
                        return False  # 경로 언급 있지만 실제 파일 없음
                else:
                    # 경로 언급만 있고 실제 경로 없음
                    return True  # 일단 pass (경로만 명시)
        
        return False
    
    def _extract_evidence_path(self, line: str) -> str:
        """Evidence 경로 추출"""
        # `logs/evidence/...` 패턴
        match = re.search(r'`([^`]*evidence[^`]*)`', line)
        if match:
            return match.group(1)
        
        # logs/evidence/... 패턴 (backtick 없음)
        match = re.search(r'(logs/evidence/[^\s,\)]+)', line)
        if match:
            return match.group(1)
        
        # docs/.../evidence/... 패턴
        match = re.search(r'(docs/[^\s,\)]*/evidence/[^\s,\)]+)', line)
        if match:
            return match.group(1)
        
        return ""
    
    def _check_evidence_exists(self, evidence_path: str) -> bool:
        """Evidence 경로 존재 여부 확인"""
        # 절대 경로 변환
        project_root = self.roadmap_path.parent
        full_path = project_root / evidence_path
        
        # 디렉토리 또는 파일 존재 확인
        if full_path.exists():
            return True
        
        # 와일드카드 패턴 (예: logs/evidence/d204_2_*)
        if '*' in evidence_path:
            pattern_path = project_root / Path(evidence_path).parent
            if pattern_path.exists():
                pattern = Path(evidence_path).name
                matches = list(pattern_path.glob(pattern))
                return len(matches) > 0
        
        return False
    
    def _report_violations(self, violations: List[Dict[str, Any]]):
        """위반 보고"""
        logger.error("=" * 60)
        logger.error("SSOT Violations Found:")
        logger.error("=" * 60)
        
        for i, v in enumerate(violations, 1):
            logger.error(f"\n[{i}] {v['section']}")
            logger.error(f"    Line: {v['line']}")
            logger.error(f"    Reason: {v['reason']}")
            logger.error(f"    Snippet: {v['snippet']}")
        
        # Evidence 파일 저장
        self._save_violations_report(violations)
    
    def _save_violations_report(self, violations: List[Dict[str, Any]]):
        """위반 리포트 저장"""
        evidence_dir = Path("logs/evidence/d205_2_20251230_1639_ad798d5")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = evidence_dir / "ssot_audit_violations.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'roadmap': str(self.roadmap_path),
            'total_violations': len(violations),
            'violations': violations
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\nViolations report saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='SSOT Integrity Audit')
    parser.add_argument(
        '--roadmap',
        default='D_ROADMAP.md',
        help='Path to D_ROADMAP.md (default: D_ROADMAP.md)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Fix violations (dry-run, not implemented)'
    )
    
    args = parser.parse_args()
    
    roadmap_path = Path(args.roadmap)
    auditor = SSOTAuditor(roadmap_path, fix_mode=args.fix)
    
    exit_code = auditor.audit()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
