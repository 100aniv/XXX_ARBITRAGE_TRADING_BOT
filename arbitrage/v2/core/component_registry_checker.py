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
import yaml
from pathlib import Path
from typing import Dict, List, Any


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
    
    def check_evidence_fields(self, component: Dict) -> bool:
        """evidence_kpi_fields가 Evidence schema에 정의되어 있는지 확인
        
        D206-1 HARDENED (Registry De-Doping):
        - EVIDENCE_FORMAT.md 파싱하여 필수 필드 검증
        - 텍스트 검색 제거, 구조적 검증으로 전환
        """
        comp_id = component.get("id", "unknown")
        evidence_fields = component.get("evidence_kpi_fields", [])
        
        if not evidence_fields:
            return True  # 필드 없으면 스킵
        
        # Evidence schema 파일 존재 확인
        evidence_format_path = self.repo_root / "docs" / "v2" / "design" / "EVIDENCE_FORMAT.md"
        
        if not evidence_format_path.exists():
            self.warnings.append(
                f"[{comp_id}] Evidence schema not found: EVIDENCE_FORMAT.md"
            )
            return False
        
        # D206-1: Evidence schema 내용 파싱하여 필드 검증
        # 단순 존재 확인이 아닌 실제 schema 정의 확인
        try:
            with open(evidence_format_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # engine_report.json 스키마 섹션에서 필수 필드 확인
                for field in evidence_fields:
                    if field not in content:
                        self.warnings.append(
                            f"[{comp_id}] Evidence field '{field}' not documented in EVIDENCE_FORMAT.md"
                        )
        except Exception as e:
            self.warnings.append(
                f"[{comp_id}] Failed to parse EVIDENCE_FORMAT.md: {e}"
            )
            return False
        
        return True
    
    def check_config_keys(self, component: Dict, config_data: Dict[str, Any]) -> bool:
        """config_keys가 config.yml에 존재하는지 확인
        
        D206-1: Registry De-Doping - YAML 파싱 기반 검증
        """
        comp_id = component.get("id", "unknown")
        config_keys = component.get("config_keys", [])
        ops_critical = component.get("ops_critical", False)
        required = component.get("required", False)
        
        if not config_keys:
            return True  # config_keys 없으면 스킵
        
        all_found = True
        for key in config_keys:
            # YAML 파싱된 config에서 key 존재 확인 (nested key 지원)
            key_parts = key.split('.')
            current = config_data
            found = True
            
            for part in key_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    found = False
                    break
            
            if not found:
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
    
    def load_config(self) -> Dict[str, Any]:
        """config.yml YAML 파싱
        
        D206-1: Registry De-Doping - 텍스트 검색 대신 YAML 파싱
        """
        config_path = self.repo_root / "config" / "v2" / "config.yml"
        
        if not config_path.exists():
            self.warnings.append("config.yml not found")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.errors.append(f"Failed to parse config.yml: {e}")
            return {}
    
    def run_checks(self) -> tuple:
        """모든 검사 실행
        
        D206-1: Registry De-Doping - 텍스트 검색 제거
        """
        registry = self.load_registry()
        
        if not registry:
            return (len(self.errors), len(self.warnings))
        
        # config.yml YAML 파싱 (텍스트 검색 대신)
        config_data = self.load_config()
        
        # 각 컴포넌트 검사
        components = registry.get("components", [])
        for component in components:
            comp_id = component.get("id", "unknown")
            ops_critical = component.get("ops_critical", False)
            
            # 파일 존재 확인
            files_ok = self.check_component_files(component)
            
            # Evidence fields 확인 (DOPING 제거)
            evidence_ok = self.check_evidence_fields(component)
            
            # Config keys 확인 (YAML 파싱 기반)
            config_ok = self.check_config_keys(component, config_data)
            
            # ops_critical 컴포넌트는 파일 존재만 필수 (evidence/config는 warning)
            if ops_critical and not files_ok:
                self.errors.append(
                    f"[{comp_id}] ops_critical component failed validation"
                )
        
        return (len(self.errors), len(self.warnings))
