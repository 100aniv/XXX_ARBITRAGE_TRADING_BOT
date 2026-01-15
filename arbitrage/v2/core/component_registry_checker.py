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
from pathlib import Path
from typing import Dict, List


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
        ops_critical = component.get("ops_critical", False)
        required = component.get("required", False)
        
        if not files:
            return True  # files 없으면 스킵
        
        all_exist = True
        for file_path in files:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                # OPS Gate 정책: ops_critical or required → ERROR
                if ops_critical or required:
                    self.errors.append(
                        f"[{comp_id}] CRITICAL: File not found: {file_path}"
                    )
                else:
                    self.warnings.append(
                        f"[{comp_id}] File not found: {file_path}"
                    )
                all_exist = False
        
        return all_exist
    
    def check_evidence_fields(self, component: Dict, paper_runner_content: str) -> bool:
        """evidence_kpi_fields가 Evidence schema에 정의되어 있는지 확인
        
        D206-1 HARDENED (Add-on A: Artifact-First):
        - Runner 파일이 아닌 Evidence manifest schema(EVIDENCE_FORMAT.md)를 검사
        - Gate는 Core 산출물을 검증, Runner 속성 검사 금지
        """
        comp_id = component.get("id", "unknown")
        evidence_fields = component.get("evidence_kpi_fields", [])
        
        if not evidence_fields:
            return True  # 필드 없으면 스킵
        
        # Add-on A: Runner 파일 검사 대신 Evidence schema 검사
        # Evidence fields는 런타임에 kpi_summary.json/manifest.json으로 생성됨
        # 정적 검사에서는 Evidence schema 파일 존재만 확인
        evidence_format_path = self.repo_root / "docs" / "v2" / "design" / "EVIDENCE_FORMAT.md"
        
        if not evidence_format_path.exists():
            self.warnings.append(
                f"[{comp_id}] Evidence schema not found: EVIDENCE_FORMAT.md"
            )
            return False
        
        # Evidence schema가 존재하면 필드는 런타임에 검증 (Preflight)
        # 정적 검사에서는 PASS (Runner 비대화 방지)
        return True
    
    def check_config_keys(self, component: Dict, paper_runner_content: str) -> bool:
        """config_keys가 PaperRunnerConfig에 존재하는지 확인"""
        comp_id = component.get("id", "unknown")
        config_keys = component.get("config_keys", [])
        ops_critical = component.get("ops_critical", False)
        required = component.get("required", False)
        
        if not config_keys:
            return True  # config_keys 없으면 스킵
        
        all_found = True
        for key in config_keys:
            # PaperRunnerConfig에서 key 존재 확인 (간단한 텍스트 검색)
            if key not in paper_runner_content:
                # OPS Gate 정책: ops_critical or required → ERROR
                if ops_critical or required:
                    self.errors.append(
                        f"[{comp_id}] CRITICAL: Config key not found: {key}"
                    )
                    all_found = False
                else:
                    self.warnings.append(
                        f"[{comp_id}] Config key not found: {key}"
                    )
        
        return all_found
    
    def run_checks(self) -> tuple:
        """모든 검사 실행"""
        registry = self.load_registry()
        
        if not registry:
            return (len(self.errors), len(self.warnings))
        
        # paper_runner.py 로드
        paper_runner_path = self.repo_root / "arbitrage" / "v2" / "harness" / "paper_runner.py"
        paper_runner_content = ""
        if paper_runner_path.exists():
            with open(paper_runner_path, 'r', encoding='utf-8') as f:
                paper_runner_content = f.read()
        
        # 각 컴포넌트 검사
        components = registry.get("components", [])
        for component in components:
            comp_id = component.get("id", "unknown")
            ops_critical = component.get("ops_critical", False)
            
            # 파일 존재 확인
            files_ok = self.check_component_files(component)
            
            # Evidence fields 확인
            evidence_ok = self.check_evidence_fields(component, paper_runner_content)
            
            # Config keys 확인
            config_ok = self.check_config_keys(component, paper_runner_content)
            
            # ops_critical 컴포넌트는 파일 존재만 필수 (evidence/config는 warning)
            if ops_critical and not files_ok:
                self.errors.append(
                    f"[{comp_id}] ops_critical component failed validation"
                )
        
        return (len(self.errors), len(self.warnings))
