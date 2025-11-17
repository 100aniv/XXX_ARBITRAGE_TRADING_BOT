# -*- coding: utf-8 -*-
"""
D31 Safe Kubernetes Apply Layer

생성된 K8s Job YAML 파일을 안전하게 K8s 클러스터에 적용.
기본값: dry-run 모드 (실제 kubectl 실행 안 함)
--apply 플래그로만 실제 실행
"""

import logging
import subprocess
from typing import Dict, List, Optional, Literal, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class K8sApplyError(Exception):
    """K8s Apply 에러"""
    pass


@dataclass
class K8sApplyPlanItem:
    """K8s Apply 계획 항목"""
    job_name: str
    namespace: str
    yaml_path: str
    kubectl_command: List[str]


@dataclass
class K8sApplyPlan:
    """K8s Apply 계획"""
    jobs: List[K8sApplyPlanItem]
    total_jobs: int


@dataclass
class K8sApplyJobResult:
    """K8s Apply Job 결과"""
    job_name: str
    namespace: str
    yaml_path: str
    command: List[str]
    return_code: int
    stdout: str
    stderr: str
    status: Literal["SKIPPED", "SUCCESS", "FAILED"]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class K8sApplyResult:
    """K8s Apply 결과"""
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    skipped_jobs: int
    job_results: List[K8sApplyJobResult]


class K8sApplyExecutor:
    """K8s Apply 실행기"""
    
    def __init__(
        self,
        dry_run: bool = True,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None
    ):
        """
        Args:
            dry_run: True면 실제 kubectl 실행 안 함 (기본값: True)
            kubeconfig: kubeconfig 파일 경로
            context: K8s 컨텍스트
        """
        self.dry_run = dry_run
        self.kubeconfig = kubeconfig
        self.context = context
        
        logger.info(f"[D31_K8S_APPLY] K8sApplyExecutor initialized: dry_run={dry_run}, kubeconfig={kubeconfig}, context={context}")
    
    def build_plan(self, jobs_dir: str) -> K8sApplyPlan:
        """
        디렉토리의 모든 K8s Job YAML 파일로 Apply 계획 생성
        
        Args:
            jobs_dir: K8s Job YAML 파일 디렉토리
        
        Returns:
            K8sApplyPlan
        """
        jobs_path = Path(jobs_dir)
        
        if not jobs_path.exists():
            logger.error(f"[D31_K8S_APPLY] Directory not found: {jobs_dir}")
            raise K8sApplyError(f"디렉토리를 찾을 수 없음: {jobs_dir}")
        
        # YAML 파일 수집
        yaml_files = sorted(jobs_path.glob("*.yaml"))
        
        if not yaml_files:
            logger.warning(f"[D31_K8S_APPLY] No YAML files found in {jobs_dir}")
            raise K8sApplyError(f"YAML 파일을 찾을 수 없음: {jobs_dir}")
        
        logger.info(f"[D31_K8S_APPLY] Found {len(yaml_files)} YAML files")
        
        # Apply 계획 항목 생성
        plan_items = []
        
        for yaml_file in yaml_files:
            try:
                # YAML 파일에서 Job 이름과 네임스페이스 추출
                job_name, namespace = self._extract_job_info(yaml_file)
                
                # kubectl 명령 생성
                kubectl_command = self._build_kubectl_command(yaml_file)
                
                # 계획 항목 생성
                plan_item = K8sApplyPlanItem(
                    job_name=job_name,
                    namespace=namespace,
                    yaml_path=str(yaml_file),
                    kubectl_command=kubectl_command
                )
                
                plan_items.append(plan_item)
                logger.info(f"[D31_K8S_APPLY] Added plan item: {job_name}")
            
            except Exception as e:
                logger.error(f"[D31_K8S_APPLY] Error processing {yaml_file}: {e}")
                raise K8sApplyError(f"파일 처리 실패: {yaml_file} - {str(e)}")
        
        plan = K8sApplyPlan(
            jobs=plan_items,
            total_jobs=len(plan_items)
        )
        
        logger.info(f"[D31_K8S_APPLY] Apply plan built: {len(plan_items)} jobs")
        
        return plan
    
    def execute_plan(self, plan: K8sApplyPlan) -> K8sApplyResult:
        """
        Apply 계획 실행
        
        Args:
            plan: K8sApplyPlan
        
        Returns:
            K8sApplyResult
        """
        job_results = []
        successful_jobs = 0
        failed_jobs = 0
        skipped_jobs = 0
        
        logger.info(f"[D31_K8S_APPLY] Executing apply plan: {plan.total_jobs} jobs, dry_run={self.dry_run}")
        
        for plan_item in plan.jobs:
            try:
                if self.dry_run:
                    # Dry-run 모드: kubectl 실행 안 함
                    result = K8sApplyJobResult(
                        job_name=plan_item.job_name,
                        namespace=plan_item.namespace,
                        yaml_path=plan_item.yaml_path,
                        command=plan_item.kubectl_command,
                        return_code=0,
                        stdout="",
                        stderr="",
                        status="SKIPPED"
                    )
                    skipped_jobs += 1
                    logger.info(f"[D31_K8S_APPLY] Dry-run (skipped): {plan_item.job_name}")
                else:
                    # 실행 모드: kubectl 실행
                    result = self._execute_kubectl(plan_item)
                    
                    if result.status == "SUCCESS":
                        successful_jobs += 1
                        logger.info(f"[D31_K8S_APPLY] Applied successfully: {plan_item.job_name}")
                    else:
                        failed_jobs += 1
                        logger.error(f"[D31_K8S_APPLY] Apply failed: {plan_item.job_name}")
                
                job_results.append(result)
            
            except Exception as e:
                logger.error(f"[D31_K8S_APPLY] Error executing {plan_item.job_name}: {e}")
                
                result = K8sApplyJobResult(
                    job_name=plan_item.job_name,
                    namespace=plan_item.namespace,
                    yaml_path=plan_item.yaml_path,
                    command=plan_item.kubectl_command,
                    return_code=-1,
                    stdout="",
                    stderr=str(e),
                    status="FAILED"
                )
                failed_jobs += 1
                job_results.append(result)
        
        apply_result = K8sApplyResult(
            total_jobs=plan.total_jobs,
            successful_jobs=successful_jobs,
            failed_jobs=failed_jobs,
            skipped_jobs=skipped_jobs,
            job_results=job_results
        )
        
        logger.info(f"[D31_K8S_APPLY] Apply plan executed: {successful_jobs} success, {failed_jobs} failed, {skipped_jobs} skipped")
        
        return apply_result
    
    def _extract_job_info(self, yaml_file: Path) -> tuple:
        """YAML 파일에서 Job 이름과 네임스페이스 추출"""
        import yaml
        
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        job_name = data.get("metadata", {}).get("name", "unknown")
        namespace = data.get("metadata", {}).get("namespace", "default")
        
        return job_name, namespace
    
    def _build_kubectl_command(self, yaml_file: Path) -> List[str]:
        """kubectl 명령 생성"""
        command = ["kubectl", "apply", "-f", str(yaml_file)]
        
        if self.kubeconfig:
            command.extend(["--kubeconfig", self.kubeconfig])
        
        if self.context:
            command.extend(["--context", self.context])
        
        return command
    
    def _execute_kubectl(self, plan_item: K8sApplyPlanItem) -> K8sApplyJobResult:
        """kubectl 명령 실행"""
        try:
            logger.info(f"[D31_K8S_APPLY] Executing kubectl: {' '.join(plan_item.kubectl_command)}")
            
            result = subprocess.run(
                plan_item.kubectl_command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            
            return K8sApplyJobResult(
                job_name=plan_item.job_name,
                namespace=plan_item.namespace,
                yaml_path=plan_item.yaml_path,
                command=plan_item.kubectl_command,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                status=status
            )
        
        except subprocess.TimeoutExpired:
            logger.error(f"[D31_K8S_APPLY] kubectl timeout for {plan_item.job_name}")
            
            return K8sApplyJobResult(
                job_name=plan_item.job_name,
                namespace=plan_item.namespace,
                yaml_path=plan_item.yaml_path,
                command=plan_item.kubectl_command,
                return_code=-1,
                stdout="",
                stderr="kubectl timeout",
                status="FAILED"
            )
        
        except Exception as e:
            logger.error(f"[D31_K8S_APPLY] Error executing kubectl: {e}")
            
            return K8sApplyJobResult(
                job_name=plan_item.job_name,
                namespace=plan_item.namespace,
                yaml_path=plan_item.yaml_path,
                command=plan_item.kubectl_command,
                return_code=-1,
                stdout="",
                stderr=str(e),
                status="FAILED"
            )


def generate_apply_report_text(result: K8sApplyResult) -> str:
    """
    K8s Apply 결과를 텍스트로 변환
    
    Args:
        result: K8sApplyResult
    
    Returns:
        포맷된 텍스트
    """
    lines = []
    
    lines.append("=" * 70)
    lines.append("[D31_K8S_APPLY] KUBERNETES APPLY REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    # 요약
    lines.append("[SUMMARY]")
    lines.append(f"Total Jobs:              {result.total_jobs}")
    lines.append(f"Successful:              {result.successful_jobs}")
    lines.append(f"Failed:                  {result.failed_jobs}")
    lines.append(f"Skipped (dry-run):       {result.skipped_jobs}")
    lines.append("")
    
    # 성공한 Job
    successful_jobs = [r for r in result.job_results if r.status == "SUCCESS"]
    if successful_jobs:
        lines.append("[SUCCESSFUL JOBS]")
        for job_result in successful_jobs:
            lines.append(f"  ✓ {job_result.job_name}")
        lines.append("")
    
    # 실패한 Job
    failed_jobs = [r for r in result.job_results if r.status == "FAILED"]
    if failed_jobs:
        lines.append("[FAILED JOBS]")
        for job_result in failed_jobs:
            lines.append(f"  ✗ {job_result.job_name}")
            if job_result.stderr:
                lines.append(f"    Error: {job_result.stderr[:100]}")
        lines.append("")
    
    # 스킵된 Job
    skipped_jobs = [r for r in result.job_results if r.status == "SKIPPED"]
    if skipped_jobs:
        lines.append("[SKIPPED JOBS (DRY-RUN)]")
        for job_result in skipped_jobs:
            lines.append(f"  ⊘ {job_result.job_name}")
        lines.append("")
    
    # 상세 정보
    if result.job_results:
        lines.append("[JOB DETAILS]")
        for idx, job_result in enumerate(result.job_results, 1):
            lines.append(f"\n[Job {idx}]")
            lines.append(f"  Name:                  {job_result.job_name}")
            lines.append(f"  Namespace:             {job_result.namespace}")
            lines.append(f"  YAML Path:             {job_result.yaml_path}")
            lines.append(f"  Status:                {job_result.status}")
            lines.append(f"  Return Code:           {job_result.return_code}")
            
            if job_result.stdout:
                lines.append(f"  Stdout:                {job_result.stdout[:100]}")
            
            if job_result.stderr:
                lines.append(f"  Stderr:                {job_result.stderr[:100]}")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("[D31_K8S_APPLY] END OF APPLY REPORT")
    lines.append("=" * 70)
    
    return "\n".join(lines)
