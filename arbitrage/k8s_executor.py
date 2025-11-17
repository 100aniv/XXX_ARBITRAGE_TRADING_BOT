# -*- coding: utf-8 -*-
"""
D30 Kubernetes Execution Layer (Read-Only Mode)

생성된 K8s Job YAML 파일을 검증하고 실행 계획을 생성.
실제 kubectl 실행 없음 (검증 및 분석만).
"""

import logging
import yaml
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class K8sValidationError(Exception):
    """K8s 검증 에러"""
    pass


@dataclass
class K8sJobValidation:
    """K8s Job 검증 결과"""
    valid: bool
    job_name: str
    namespace: str
    errors: List[str]
    warnings: List[str]
    job_data: Optional[Dict[str, Any]] = None


@dataclass
class K8sExecutionPlan:
    """K8s 실행 계획"""
    total_jobs: int
    valid_jobs: int
    invalid_jobs: int
    jobs: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
    summary: Dict[str, Any]


class K8sJobValidator:
    """K8s Job 검증기"""
    
    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: 엄격한 검증 모드
        """
        self.strict_mode = strict_mode
        logger.info(f"[D30_K8S_EXEC] K8sJobValidator initialized: strict_mode={strict_mode}")
    
    def validate_job_yaml(self, yaml_content: str, filename: str = "") -> K8sJobValidation:
        """
        K8s Job YAML 검증
        
        Args:
            yaml_content: YAML 파일 내용
            filename: 파일명 (로깅용)
        
        Returns:
            K8sJobValidation
        """
        errors = []
        warnings = []
        job_data = None
        
        try:
            # YAML 파싱
            job_data = yaml.safe_load(yaml_content)
            
            if not job_data:
                errors.append("YAML 파일이 비어있음")
                return K8sJobValidation(
                    valid=False,
                    job_name=filename,
                    namespace="unknown",
                    errors=errors,
                    warnings=warnings
                )
            
            # 기본 필드 검증
            job_name = self._validate_basic_structure(job_data, errors)
            namespace = job_data.get("metadata", {}).get("namespace", "default")
            
            # 상세 검증
            self._validate_metadata(job_data, errors, warnings)
            self._validate_spec(job_data, errors, warnings)
            self._validate_containers(job_data, errors, warnings)
            self._validate_resources(job_data, errors, warnings)
            
            valid = len(errors) == 0
            
            if valid:
                logger.info(f"[D30_K8S_EXEC] Job validation passed: {job_name}")
            else:
                logger.warning(f"[D30_K8S_EXEC] Job validation failed: {job_name}")
            
            return K8sJobValidation(
                valid=valid,
                job_name=job_name,
                namespace=namespace,
                errors=errors,
                warnings=warnings,
                job_data=job_data
            )
        
        except yaml.YAMLError as e:
            errors.append(f"YAML 파싱 에러: {str(e)}")
            logger.error(f"[D30_K8S_EXEC] YAML parse error in {filename}: {e}")
            
            return K8sJobValidation(
                valid=False,
                job_name=filename,
                namespace="unknown",
                errors=errors,
                warnings=warnings
            )
        
        except Exception as e:
            errors.append(f"검증 중 에러: {str(e)}")
            logger.error(f"[D30_K8S_EXEC] Validation error in {filename}: {e}")
            
            return K8sJobValidation(
                valid=False,
                job_name=filename,
                namespace="unknown",
                errors=errors,
                warnings=warnings
            )
    
    def _validate_basic_structure(self, job_data: Dict, errors: List[str]) -> str:
        """기본 구조 검증"""
        job_name = "unknown"
        
        # apiVersion 검증
        api_version = job_data.get("apiVersion")
        if api_version != "batch/v1":
            errors.append(f"Invalid apiVersion: {api_version} (expected: batch/v1)")
        
        # kind 검증
        kind = job_data.get("kind")
        if kind != "Job":
            errors.append(f"Invalid kind: {kind} (expected: Job)")
        
        # metadata 검증
        if "metadata" not in job_data:
            errors.append("metadata 필드 누락")
        else:
            job_name = job_data["metadata"].get("name", "unknown")
        
        # spec 검증
        if "spec" not in job_data:
            errors.append("spec 필드 누락")
        
        return job_name
    
    def _validate_metadata(self, job_data: Dict, errors: List[str], warnings: List[str]) -> None:
        """메타데이터 검증"""
        metadata = job_data.get("metadata", {})
        
        # name 검증
        name = metadata.get("name")
        if not name:
            errors.append("metadata.name 필드 누락")
        else:
            # 이름 규칙 검증: arb-tuning-*
            if not name.startswith("arb-tuning-"):
                warnings.append(f"Job 이름이 규칙을 따르지 않음: {name}")
        
        # namespace 검증
        namespace = metadata.get("namespace")
        if not namespace:
            warnings.append("namespace 지정 안 됨 (기본값: default)")
        
        # labels 검증
        labels = metadata.get("labels", {})
        required_labels = ["app", "session_id", "worker_id", "component"]
        for label in required_labels:
            if label not in labels:
                warnings.append(f"권장 레이블 누락: {label}")
    
    def _validate_spec(self, job_data: Dict, errors: List[str], warnings: List[str]) -> None:
        """spec 검증"""
        spec = job_data.get("spec", {})
        
        # backoffLimit 검증
        backoff_limit = spec.get("backoffLimit")
        if backoff_limit is None:
            warnings.append("backoffLimit 미설정")
        elif backoff_limit < 0:
            errors.append(f"Invalid backoffLimit: {backoff_limit}")
        
        # template 검증
        if "template" not in spec:
            errors.append("spec.template 필드 누락")
        else:
            template = spec["template"]
            if "spec" not in template:
                errors.append("spec.template.spec 필드 누락")
            else:
                template_spec = template["spec"]
                
                # containers 검증
                if "containers" not in template_spec:
                    errors.append("spec.template.spec.containers 필드 누락")
                elif not isinstance(template_spec["containers"], list):
                    errors.append("containers는 리스트여야 함")
                elif len(template_spec["containers"]) == 0:
                    errors.append("containers가 비어있음")
                
                # restartPolicy 검증
                restart_policy = template_spec.get("restartPolicy")
                if restart_policy not in ["Never", "Always", "OnFailure"]:
                    warnings.append(f"Unusual restartPolicy: {restart_policy}")
    
    def _validate_containers(self, job_data: Dict, errors: List[str], warnings: List[str]) -> None:
        """컨테이너 검증"""
        containers = job_data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        
        for idx, container in enumerate(containers):
            # name 검증
            if "name" not in container:
                errors.append(f"containers[{idx}].name 필드 누락")
            
            # image 검증
            image = container.get("image")
            if not image:
                errors.append(f"containers[{idx}].image 필드 누락")
            else:
                # 이미지 형식 검증
                if ":" not in image and image != "latest":
                    warnings.append(f"containers[{idx}].image 태그 미지정: {image}")
            
            # command 검증
            if "command" not in container:
                warnings.append(f"containers[{idx}].command 필드 누락")
            
            # args 검증
            if "args" not in container:
                warnings.append(f"containers[{idx}].args 필드 누락")
            else:
                args = container["args"]
                if not isinstance(args, list):
                    errors.append(f"containers[{idx}].args는 리스트여야 함")
            
            # env 검증
            env = container.get("env", [])
            if not env:
                warnings.append(f"containers[{idx}].env가 비어있음")
            else:
                for env_var in env:
                    if "name" not in env_var or "value" not in env_var:
                        errors.append(f"containers[{idx}].env 항목 형식 오류")
    
    def _validate_resources(self, job_data: Dict, errors: List[str], warnings: List[str]) -> None:
        """리소스 검증"""
        containers = job_data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        
        for idx, container in enumerate(containers):
            resources = container.get("resources", {})
            
            if not resources:
                warnings.append(f"containers[{idx}].resources 미설정")
            else:
                # requests 검증
                requests = resources.get("requests", {})
                if not requests:
                    warnings.append(f"containers[{idx}].resources.requests 미설정")
                else:
                    if "cpu" not in requests:
                        warnings.append(f"containers[{idx}].resources.requests.cpu 미설정")
                    if "memory" not in requests:
                        warnings.append(f"containers[{idx}].resources.requests.memory 미설정")
                
                # limits 검증
                limits = resources.get("limits", {})
                if not limits:
                    warnings.append(f"containers[{idx}].resources.limits 미설정")
                else:
                    if "cpu" not in limits:
                        warnings.append(f"containers[{idx}].resources.limits.cpu 미설정")
                    if "memory" not in limits:
                        warnings.append(f"containers[{idx}].resources.limits.memory 미설정")


class K8sExecutionPlanner:
    """K8s 실행 계획 생성기"""
    
    def __init__(self, validator: K8sJobValidator):
        """
        Args:
            validator: K8sJobValidator 인스턴스
        """
        self.validator = validator
        logger.info("[D30_K8S_EXEC] K8sExecutionPlanner initialized")
    
    def plan_from_directory(self, jobs_dir: str) -> K8sExecutionPlan:
        """
        디렉토리의 모든 K8s Job YAML 파일을 검증하고 실행 계획 생성
        
        Args:
            jobs_dir: K8s Job YAML 파일 디렉토리
        
        Returns:
            K8sExecutionPlan
        """
        jobs_path = Path(jobs_dir)
        
        if not jobs_path.exists():
            logger.error(f"[D30_K8S_EXEC] Directory not found: {jobs_dir}")
            return K8sExecutionPlan(
                total_jobs=0,
                valid_jobs=0,
                invalid_jobs=0,
                jobs=[],
                errors=[f"디렉토리를 찾을 수 없음: {jobs_dir}"],
                warnings=[],
                summary={}
            )
        
        # YAML 파일 수집
        yaml_files = sorted(jobs_path.glob("*.yaml"))
        
        if not yaml_files:
            logger.warning(f"[D30_K8S_EXEC] No YAML files found in {jobs_dir}")
            return K8sExecutionPlan(
                total_jobs=0,
                valid_jobs=0,
                invalid_jobs=0,
                jobs=[],
                errors=[f"YAML 파일을 찾을 수 없음: {jobs_dir}"],
                warnings=[],
                summary={}
            )
        
        logger.info(f"[D30_K8S_EXEC] Found {len(yaml_files)} YAML files")
        
        # 각 파일 검증
        valid_jobs = []
        invalid_jobs = []
        all_errors = []
        all_warnings = []
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                
                validation = self.validator.validate_job_yaml(yaml_content, yaml_file.name)
                
                if validation.valid:
                    valid_jobs.append(validation)
                else:
                    invalid_jobs.append(validation)
                
                all_errors.extend(validation.errors)
                all_warnings.extend(validation.warnings)
            
            except Exception as e:
                logger.error(f"[D30_K8S_EXEC] Error reading {yaml_file}: {e}")
                all_errors.append(f"파일 읽기 실패: {yaml_file.name} - {str(e)}")
        
        # 실행 계획 생성
        plan = K8sExecutionPlan(
            total_jobs=len(yaml_files),
            valid_jobs=len(valid_jobs),
            invalid_jobs=len(invalid_jobs),
            jobs=[v.job_data for v in valid_jobs if v.job_data],
            errors=all_errors,
            warnings=all_warnings,
            summary=self._create_summary(valid_jobs, invalid_jobs)
        )
        
        logger.info(f"[D30_K8S_EXEC] Execution plan created: {len(valid_jobs)} valid, {len(invalid_jobs)} invalid")
        
        return plan
    
    def _create_summary(self, valid_jobs: List[K8sJobValidation], invalid_jobs: List[K8sJobValidation]) -> Dict[str, Any]:
        """실행 계획 요약 생성"""
        summary = {
            "total_jobs": len(valid_jobs) + len(invalid_jobs),
            "valid_jobs": len(valid_jobs),
            "invalid_jobs": len(invalid_jobs),
            "job_names": [v.job_name for v in valid_jobs],
            "namespaces": list(set(v.namespace for v in valid_jobs)),
            "invalid_job_names": [v.job_name for v in invalid_jobs]
        }
        
        return summary


def generate_execution_plan_text(plan: K8sExecutionPlan) -> str:
    """
    K8s 실행 계획을 텍스트로 변환
    
    Args:
        plan: K8sExecutionPlan
    
    Returns:
        포맷된 텍스트
    """
    lines = []
    
    lines.append("=" * 70)
    lines.append("[D30_K8S_EXEC] KUBERNETES EXECUTION PLAN")
    lines.append("=" * 70)
    lines.append("")
    
    # 요약
    lines.append("[SUMMARY]")
    lines.append(f"Total Jobs:              {plan.summary.get('total_jobs', 0)}")
    lines.append(f"Valid Jobs:              {plan.valid_jobs}")
    lines.append(f"Invalid Jobs:            {plan.invalid_jobs}")
    lines.append(f"Namespaces:              {', '.join(plan.summary.get('namespaces', []))}")
    lines.append("")
    
    # 유효한 Job 목록
    if plan.valid_jobs > 0:
        lines.append("[VALID JOBS]")
        for job_name in plan.summary.get("job_names", []):
            lines.append(f"  ✓ {job_name}")
        lines.append("")
    
    # 무효한 Job 목록
    if plan.invalid_jobs > 0:
        lines.append("[INVALID JOBS]")
        for job_name in plan.summary.get("invalid_job_names", []):
            lines.append(f"  ✗ {job_name}")
        lines.append("")
    
    # 에러
    if plan.errors:
        lines.append("[ERRORS]")
        for error in plan.errors:
            lines.append(f"  ✗ {error}")
        lines.append("")
    
    # 경고
    if plan.warnings:
        lines.append("[WARNINGS]")
        for warning in plan.warnings:
            lines.append(f"  ⚠ {warning}")
        lines.append("")
    
    # Job 상세 정보
    if plan.jobs:
        lines.append("[JOB DETAILS]")
        for idx, job in enumerate(plan.jobs, 1):
            lines.append(f"\n[Job {idx}]")
            
            # 메타데이터
            metadata = job.get("metadata", {})
            lines.append(f"  Name:                  {metadata.get('name', 'N/A')}")
            lines.append(f"  Namespace:             {metadata.get('namespace', 'default')}")
            
            # 레이블
            labels = metadata.get("labels", {})
            if labels:
                lines.append(f"  Labels:")
                for key, value in labels.items():
                    lines.append(f"    {key}: {value}")
            
            # 컨테이너
            containers = job.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if containers:
                container = containers[0]
                lines.append(f"  Image:                 {container.get('image', 'N/A')}")
                
                # 명령
                command = container.get("command", [])
                args = container.get("args", [])
                if command:
                    lines.append(f"  Command:               {' '.join(command)}")
                if args:
                    lines.append(f"  Args:                  {' '.join(args[:3])}...")
                
                # 환경 변수
                env = container.get("env", [])
                if env:
                    lines.append(f"  Environment Variables: ({len(env)} total)")
                    for env_var in env[:5]:
                        lines.append(f"    {env_var.get('name', 'N/A')}: {env_var.get('value', 'N/A')}")
                    if len(env) > 5:
                        lines.append(f"    ... and {len(env) - 5} more")
                
                # 리소스
                resources = container.get("resources", {})
                if resources:
                    requests = resources.get("requests", {})
                    limits = resources.get("limits", {})
                    if requests:
                        lines.append(f"  Resources (requests):  CPU={requests.get('cpu', 'N/A')}, Memory={requests.get('memory', 'N/A')}")
                    if limits:
                        lines.append(f"  Resources (limits):    CPU={limits.get('cpu', 'N/A')}, Memory={limits.get('memory', 'N/A')}")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("[D30_K8S_EXEC] END OF EXECUTION PLAN")
    lines.append("=" * 70)
    
    return "\n".join(lines)
