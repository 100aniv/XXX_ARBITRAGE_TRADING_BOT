#!/usr/bin/env python3
"""
D205-15-6c: Component Registry Static Checker Script

목적: V2_COMPONENT_REGISTRY.json 기반 정적 검사
- ops_critical 컴포넌트 파일 존재 확인
- evidence_kpi_fields가 paper_runner.py에서 사용되는지 확인
- config_keys가 설정에 존재하는지 확인

Exit Code:
- 0: PASS (모든 검사 통과)
- 1: FAIL (하나라도 실패)

Note: ComponentRegistryChecker 클래스는 arbitrage/v2/core/component_registry_checker.py에 정의됨
"""

import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from arbitrage.v2.core.component_registry_checker import ComponentRegistryChecker


def main():
    """Main entry point"""
    registry_path = repo_root / "docs" / "v2" / "design" / "V2_COMPONENT_REGISTRY.json"
    
    print("[Component Registry Check]")
    print("Registry: {}".format(registry_path))
    print("Repo root: {}".format(repo_root))
    print("")
    
    checker = ComponentRegistryChecker(repo_root, registry_path)
    error_count, warning_count = checker.run_checks()
    
    # 결과 출력
    if checker.errors:
        print("ERRORS:")
        for error in checker.errors:
            print("  - {}".format(error))
        print("")
    
    if checker.warnings:
        print("WARNINGS:")
        for warning in checker.warnings:
            print("  - {}".format(warning))
        print("")
    
    if error_count == 0:
        print("PASS: Component Registry validation passed")
        print("   {} warning(s)".format(warning_count))
        return 0
    else:
        print("FAIL: {} error(s), {} warning(s)".format(error_count, warning_count))
        return 1


if __name__ == "__main__":
    sys.exit(main())
