#!/usr/bin/env python3
"""
문서 경로 린트 (Documentation Layout Lint)

규칙:
- 루트: D_ROADMAP.md만 SSOT
- D92 보고서/체인지로그는 docs/D92/ 이하에 위치해야 함
- docs 바로 아래에 D92 관련 파일이 있으면 FAIL

Exit Code:
- 0: PASS (모든 규칙 준수)
- 1: FAIL (위반 사항 발견)
"""

import sys
from pathlib import Path


def check_docs_layout(project_root: Path) -> tuple[bool, list[str]]:
    """문서 레이아웃 검사"""
    violations = []
    
    # 규칙 1: 루트에 D_ROADMAP.md 존재 확인
    roadmap_path = project_root / "D_ROADMAP.md"
    if not roadmap_path.exists():
        violations.append(f"FAIL: 루트에 D_ROADMAP.md가 없습니다: {roadmap_path}")
    else:
        # 라인수 확인 (너무 작으면 FAIL)
        lines = roadmap_path.read_text(encoding='utf-8').splitlines()
        if len(lines) < 100:
            violations.append(f"FAIL: D_ROADMAP.md 라인수가 너무 적습니다: {len(lines)}줄 (최소 100줄 필요)")
    
    # 규칙 2: docs/D92/ 디렉토리 존재 확인
    d92_dir = project_root / "docs" / "D92"
    if not d92_dir.exists():
        violations.append(f"FAIL: docs/D92/ 디렉토리가 없습니다: {d92_dir}")
    
    # 규칙 3: docs 바로 아래에 D92 관련 파일이 있으면 FAIL
    docs_dir = project_root / "docs"
    if docs_dir.exists():
        for item in docs_dir.iterdir():
            if item.is_file() and item.name.startswith("D92") and item.suffix == ".md":
                violations.append(f"FAIL: docs/ 바로 아래에 D92 파일이 있습니다 (docs/D92/로 이동 필요): {item.name}")
    
    return len(violations) == 0, violations


def main():
    project_root = Path(__file__).parent.parent
    
    print("=" * 80)
    print("문서 경로 린트 (Documentation Layout Lint)")
    print("=" * 80)
    print(f"프로젝트 루트: {project_root}")
    print()
    
    passed, violations = check_docs_layout(project_root)
    
    if passed:
        print("[PASS] 모든 문서 경로 규칙을 준수합니다.")
        print()
        print("확인된 항목:")
        print("  - D_ROADMAP.md 존재 및 라인수 충분")
        print("  - docs/D92/ 디렉토리 존재")
        print("  - docs/ 바로 아래에 D92 파일 없음")
        return 0
    else:
        print("[FAIL] 문서 경로 규칙 위반 사항 발견:")
        print()
        for violation in violations:
            print(f"  {violation}")
        print()
        print("위반 사항을 수정한 후 다시 실행하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
