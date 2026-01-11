#!/usr/bin/env python3
"""
D205-15-6c: Component Registry Static Checker

목적: V2_COMPONENT_REGISTRY.json 기반 정적 검사
- ops_critical 컴포넌트 파일 존재 확인
- evidence_kpi_fields가 paper_runner.py에서 사용되는지 확인
- config_keys가 설정에 존재하는지 확인

Exit Code:
- 0: PASS (모든 검사 통과)
- 1: FAIL (하나라도 실패)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ComponentRegistryChecker:
    """Component Registry 정적 검사기"""
    
    def __init__(self, repo_root: Path, registry_path: Path):
        self.repo_root = repo_root
        self.registry_path = registry_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def load_registry(self) -> Dict:
        """Registry JSON 로드"""
        if not self.registry_path.exists():
            self.errors.append(f"Registry not found: {self.registry_path}")
            return {}
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.errors.append(f"Failed to load registry: {e}")
            return {}
    
    def check_component_files(self, component: Dict) -> bool:
        """컴포넌트 파일 존재 확인"""
        comp_id = component.get("id", "unknown")
        files = component.get("files", [])
        
        if not files:
            return True  # files 없으면 스킵
        
        all_exist = True
        for file_path in files:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                self.errors.append(
                    f"[{comp_id}] File not found: {file_path}"
                )
                all_exist = False
        
        return all_exist
    
    def check_evidence_fields(self, component: Dict, paper_runner_content: str) -> bool:
        """evidence_kpi_fields가 paper_runner.py에서 사용되는지 확인"""
        comp_id = component.get("id", "unknown")
        evidence_fields = component.get("evidence_kpi_fields", [])
        
        if not evidence_fields:
            return True  # 필드 없으면 스킵
        
        all_found = True
        for field in evidence_fields:
            # paper_runner.py에서 "field" 또는 'field' 형태로 사용되는지 확인
            if f'"{field}"' not in paper_runner_content and f"'{field}'" not in paper_runner_content:
                self.warnings.append(
                    f"[{comp_id}] Evidence field not found in paper_runner.py: {field}"
                )
                # Evidence field는 warning으로 처리 (ops_critical만 error)
                if component.get("ops_critical", False):
                    all_found = False
        
        return all_found
    
    def check_config_keys(self, component: Dict, config_content: str) -> bool:
        """config_keys가 설정에 존재하는지 확인"""
        comp_id = component.get("id", "unknown")
        config_keys = component.get("config_keys", [])
        
        if not config_keys:
            return True  # 키 없으면 스킵
        
        all_found = True
        for key in config_keys:
            # config.yml 또는 PaperRunnerConfig에서 키 존재 확인
            # 간단히 텍스트 검색 (완벽하진 않지만 충분히 유효)
            if key not in config_content:
                self.warnings.append(
                    f"[{comp_id}] Config key not found: {key}"
                )
                # Config key는 warning으로 처리
        
        return all_found
    
    def run_checks(self) -> Tuple[int, int]:
        """모든 검사 실행
        
        Returns:
            (error_count, warning_count)
        """
        # Registry 로드
        registry = self.load_registry()
        if not registry:
            return (len(self.errors), len(self.warnings))
        
        components = registry.get("components", [])
        if not components:
            self.errors.append("No components found in registry")
            return (len(self.errors), len(self.warnings))
        
        # paper_runner.py 내용 로드 (Evidence field 검사용)
        paper_runner_path = self.repo_root / "arbitrage" / "v2" / "harness" / "paper_runner.py"
        paper_runner_content = ""
        if paper_runner_path.exists():
            with open(paper_runner_path, 'r', encoding='utf-8') as f:
                paper_runner_content = f.read()
        else:
            self.errors.append(f"paper_runner.py not found: {paper_runner_path}")
        
        # config 내용 로드 (간단히 PaperRunnerConfig 스캔)
        config_py_path = self.repo_root / "arbitrage" / "v2" / "harness" / "paper_runner.py"
        config_content = paper_runner_content  # 동일 파일에 Config 정의됨
        
        # 각 컴포넌트 검사
        for component in components:
            comp_id = component.get("id", "unknown")
            ops_critical = component.get("ops_critical", False)
            
            # 1. 파일 존재 확인
            files_ok = self.check_component_files(component)
            
            # 2. Evidence fields 확인
            evidence_ok = self.check_evidence_fields(component, paper_runner_content)
            
            # 3. Config keys 확인
            config_ok = self.check_config_keys(component, config_content)
            
            # ops_critical 컴포넌트는 모든 검사 통과 필수
            if ops_critical and not (files_ok and evidence_ok and config_ok):
                self.errors.append(
                    f"[{comp_id}] ops_critical component failed validation"
                )
        
        return (len(self.errors), len(self.warnings))


def main():
    """Main entry point"""
    repo_root = Path(__file__).parent.parent
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
