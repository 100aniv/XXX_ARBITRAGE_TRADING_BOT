#!/usr/bin/env python3
"""
패키지 shadowing 검사 (Package Shadowing Check)

목적:
- tests/ 디렉토리가 루트 top-level 패키지를 shadowing하는 것을 방지
- 예: tests/config/ 가 루트 config/ 를 가리면 import 오류 발생

검사 규칙:
- 루트에서 top-level 패키지 목록 수집 (config, arbitrage, common, ml 등)
- tests/ 하위에 동일 이름 디렉토리가 있으면 FAIL

Exit Code:
- 0: PASS (shadowing 없음)
- 1: FAIL (shadowing 발견)
"""

import sys
from pathlib import Path


def get_top_level_packages(project_root: Path) -> set[str]:
    """루트에서 top-level 패키지 목록 수집"""
    packages = set()
    
    for item in project_root.iterdir():
        if item.is_dir():
            # __pycache__, .git, venv 등 제외
            if item.name.startswith('.') or item.name.startswith('_'):
                continue
            if item.name in ['venv', 'abt_bot_env', 'logs', 'docs', 'scripts', 'notebooks', 'data']:
                continue
            
            # __init__.py가 있으면 패키지로 간주
            if (item / '__init__.py').exists():
                packages.add(item.name)
    
    return packages


def check_shadowing(project_root: Path) -> tuple[bool, list[str]]:
    """tests/ 하위에서 루트 패키지를 shadowing하는지 검사"""
    violations = []
    
    # 루트 top-level 패키지 목록
    top_level_packages = get_top_level_packages(project_root)
    
    if not top_level_packages:
        violations.append("경고: 루트에서 top-level 패키지를 찾을 수 없습니다.")
        return False, violations
    
    # tests/ 디렉토리 확인
    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        # tests 디렉토리가 없으면 검사 통과
        return True, []
    
    # tests/ 하위의 모든 디렉토리 검사
    for item in tests_dir.iterdir():
        if item.is_dir():
            # __pycache__, .pytest_cache 등 제외
            if item.name.startswith('.') or item.name.startswith('_'):
                continue
            
            # 루트 패키지와 이름이 같으면 shadowing
            if item.name in top_level_packages:
                violations.append(
                    f"FAIL: tests/{item.name}/ 가 루트 패키지 {item.name}/ 를 shadowing합니다. "
                    f"tests/{item.name}/ 를 tests/test_{item.name}/ 로 이름을 변경하세요."
                )
    
    return len(violations) == 0, violations


def main():
    project_root = Path(__file__).parent.parent
    
    print("=" * 80)
    print("패키지 shadowing 검사 (Package Shadowing Check)")
    print("=" * 80)
    print(f"프로젝트 루트: {project_root}")
    print()
    
    # 루트 top-level 패키지 목록 출력
    top_level_packages = get_top_level_packages(project_root)
    print(f"루트 top-level 패키지: {sorted(top_level_packages)}")
    print()
    
    passed, violations = check_shadowing(project_root)
    
    if passed:
        print("[PASS] tests/ 디렉토리에서 루트 패키지 shadowing이 발견되지 않았습니다.")
        print()
        print("확인된 항목:")
        print("  - tests/ 하위에 루트 패키지와 동일한 이름의 디렉토리 없음")
        print("  - import 경로 충돌 위험 없음")
        return 0
    else:
        print("[FAIL] 패키지 shadowing이 발견되었습니다:")
        print()
        for violation in violations:
            print(f"  {violation}")
        print()
        print("위반 사항을 수정한 후 다시 실행하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
