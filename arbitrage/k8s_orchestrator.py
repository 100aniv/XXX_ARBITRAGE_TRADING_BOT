# -*- coding: utf-8 -*-
"""
D29 Kubernetes Orchestrator Integration

Tuning Orchestrator(D28)를 Kubernetes Job 기반으로 확장.
Job 매니페스트 생성 (실제 K8s 조작 없음).
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class K8sJobSpec:
    """Kubernetes Job 스펙"""
    name: str
    namespace: str
    image: str
    command: List[str]
    args: List[str]
    env: Dict[str, str]
    labels: Dict[str, str]
    annotations: Dict[str, str]
    restart_policy: str = "Never"
    backoff_limit: int = 0
    resources: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class K8sOrchestratorConfig:
    """Kubernetes Orchestrator 설정"""
    session_id: str
    k8s_namespace: str
    image: str
    mode: str                                   # paper, shadow, live
    env: str                                    # docker, local, stage, prod
    total_iterations: int
    workers: int
    optimizer: str                              # grid, random, bayesian
    config_path: str = "configs/d23_tuning/advanced_baseline.yaml"
    extra_env: Dict[str, str] = field(default_factory=dict)
    resources: Optional[Dict[str, Any]] = None


class K8sTuningJobFactory:
    """Kubernetes Tuning Job 생성기"""
    
    def __init__(self, config: K8sOrchestratorConfig):
        """
        Args:
            config: K8sOrchestratorConfig
        """
        self.config = config
        logger.info(f"[D29_K8S] K8sTuningJobFactory initialized: session={config.session_id}, workers={config.workers}")
    
    def create_job_for_worker(
        self,
        worker_id: str,
        iterations: int,
        index: int
    ) -> K8sJobSpec:
        """
        워커별 K8s Job 스펙 생성
        
        Args:
            worker_id: 워커 ID (예: worker-1)
            iterations: 이 워커가 실행할 반복 수
            index: Job 인덱스 (0부터 시작)
        
        Returns:
            K8sJobSpec
        """
        # Job 이름: arb-tuning-{session_short}-{worker_id}-{index}
        session_short = self.config.session_id[:8]
        job_name = f"arb-tuning-{session_short}-{worker_id}-{index}"
        
        # 기본 labels
        labels = {
            "app": "arbitrage-tuning",
            "session_id": self.config.session_id,
            "worker_id": worker_id,
            "component": "tuning",
            "mode": self.config.mode,
            "env": self.config.env
        }
        
        # 기본 annotations
        annotations = {
            "description": f"Arbitrage tuning job for {worker_id}",
            "created_at": datetime.now().isoformat()
        }
        
        # 환경 변수
        env = {
            "APP_ENV": self.config.env,
            "REDIS_HOST": "arbitrage-redis",
            "REDIS_PORT": "6379",
            "SESSION_ID": self.config.session_id,
            "WORKER_ID": worker_id,
            "MODE": self.config.mode
        }
        
        # extra_env 병합
        if self.config.extra_env:
            env.update(self.config.extra_env)
        
        # Command와 Args
        command = ["python"]
        args = [
            "scripts/run_d24_tuning_session.py",
            "--config", self.config.config_path,
            "--iterations", str(iterations),
            "--mode", self.config.mode,
            "--env", self.config.env,
            "--optimizer", self.config.optimizer,
            "--session-id", self.config.session_id,
            "--worker-id", worker_id,
            "--output-csv", f"outputs/d29_k8s_session_{worker_id}.csv"
        ]
        
        job_spec = K8sJobSpec(
            name=job_name,
            namespace=self.config.k8s_namespace,
            image=self.config.image,
            command=command,
            args=args,
            env=env,
            labels=labels,
            annotations=annotations,
            restart_policy="Never",
            backoff_limit=0,
            resources=self.config.resources
        )
        
        logger.info(f"[D29_K8S] Created job spec: {job_name} ({iterations} iterations)")
        
        return job_spec
    
    def to_yaml_dict(self, job: K8sJobSpec) -> Dict[str, Any]:
        """
        K8s Job 리소스 딕셔너리로 변환
        
        Args:
            job: K8sJobSpec
        
        Returns:
            K8s Job 리소스 딕셔너리
        """
        # 환경 변수를 K8s 형식으로 변환
        env_list = [
            {"name": key, "value": value}
            for key, value in job.env.items()
        ]
        
        # 리소스 요청/제한
        resources_dict = {}
        if job.resources:
            if "requests" in job.resources:
                resources_dict["requests"] = job.resources["requests"]
            if "limits" in job.resources:
                resources_dict["limits"] = job.resources["limits"]
        
        # K8s Job 매니페스트
        k8s_job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job.name,
                "namespace": job.namespace,
                "labels": job.labels,
                "annotations": job.annotations
            },
            "spec": {
                "backoffLimit": job.backoff_limit,
                "template": {
                    "metadata": {
                        "labels": job.labels
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": job.name,
                                "image": job.image,
                                "command": job.command,
                                "args": job.args,
                                "env": env_list
                            }
                        ],
                        "restartPolicy": job.restart_policy
                    }
                }
            }
        }
        
        # 리소스 추가 (있으면)
        if resources_dict:
            k8s_job["spec"]["template"]["spec"]["containers"][0]["resources"] = resources_dict
        
        return k8s_job


def build_k8s_jobs_from_orchestrator(
    orch_config: Dict[str, Any],
    k8s_config: K8sOrchestratorConfig
) -> List[K8sJobSpec]:
    """
    Orchestrator 설정에서 K8s Job 스펙 리스트 생성
    
    Args:
        orch_config: OrchestratorConfig 딕셔너리
        k8s_config: K8sOrchestratorConfig
    
    Returns:
        K8sJobSpec 리스트
    """
    logger.info("[D29_K8S] Building K8s jobs from orchestrator config...")
    
    # Job 분배 계산 (D28 plan_jobs 로직과 동일)
    total_iterations = orch_config.get("total_iterations", k8s_config.total_iterations)
    workers = orch_config.get("workers", k8s_config.workers)
    
    iterations_per_worker = total_iterations // workers
    remainder = total_iterations % workers
    
    factory = K8sTuningJobFactory(k8s_config)
    jobs = []
    
    for worker_idx in range(workers):
        # 처음 remainder개 워커는 +1 iteration
        iterations = iterations_per_worker + (1 if worker_idx < remainder else 0)
        worker_id = f"worker-{worker_idx + 1}"
        
        job_spec = factory.create_job_for_worker(worker_id, iterations, worker_idx)
        jobs.append(job_spec)
    
    logger.info(f"[D29_K8S] Generated {len(jobs)} K8s Job specs")
    
    return jobs
