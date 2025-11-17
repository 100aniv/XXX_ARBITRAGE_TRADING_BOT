# -*- coding: utf-8 -*-
"""
D41 K8s Utilities

K8s API 클라이언트 래퍼 및 유틸리티 함수.
실제 K8s 클러스터 의존성을 최소화하고 테스트 가능하게 설계.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class K8sJobStatus:
    """K8s Job 상태"""
    job_id: str
    namespace: str
    status: str  # Pending, Running, Succeeded, Failed
    pod_name: Optional[str] = None
    message: Optional[str] = None
    start_time: Optional[str] = None
    completion_time: Optional[str] = None


class K8sClientInterface(ABC):
    """K8s 클라이언트 인터페이스 (테스트 가능성을 위한 추상 클래스)"""

    @abstractmethod
    def create_job(self, manifest: Dict[str, Any]) -> str:
        """
        K8s Job 생성.

        Args:
            manifest: K8s Job manifest dict

        Returns:
            Job ID (job name)
        """
        pass

    @abstractmethod
    def get_job_status(self, job_id: str, namespace: str = "default") -> K8sJobStatus:
        """
        K8s Job 상태 조회.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            K8sJobStatus
        """
        pass

    @abstractmethod
    def get_pod_logs(self, job_id: str, namespace: str = "default") -> str:
        """
        K8s Pod 로그 수집.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            Pod 로그 (stdout)
        """
        pass

    @abstractmethod
    def delete_job(self, job_id: str, namespace: str = "default") -> bool:
        """
        K8s Job 삭제.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            성공 여부
        """
        pass


class K8sClient(K8sClientInterface):
    """
    K8s 클라이언트 구현 (실제 클러스터 또는 mock).

    주의: 실제 클러스터 접근은 kubernetes 패키지 필요.
    테스트에서는 mock.patch로 완전히 대체 가능.
    """

    def __init__(self, namespace: str = "default", dry_run: bool = False):
        """
        Args:
            namespace: 기본 K8s namespace
            dry_run: True면 실제 API 호출 없음 (테스트용)
        """
        self.namespace = namespace
        self.dry_run = dry_run
        self._client = None
        logger.info(f"[D41_K8S_UTILS] K8sClient initialized: namespace={namespace}, dry_run={dry_run}")

    def _get_client(self):
        """K8s API 클라이언트 (lazy load)"""
        if self.dry_run:
            return None
        if self._client is None:
            try:
                from kubernetes import client, config
                config.load_incluster_config()
                self._client = client.BatchV1Api()
            except Exception as e:
                logger.warning(f"[D41_K8S_UTILS] Failed to load K8s client: {e}")
                return None
        return self._client

    def create_job(self, manifest: Dict[str, Any]) -> str:
        """
        K8s Job 생성.

        Args:
            manifest: K8s Job manifest dict

        Returns:
            Job ID (job name)
        """
        job_name = manifest.get("metadata", {}).get("name", "unknown")
        namespace = manifest.get("metadata", {}).get("namespace", self.namespace)

        if self.dry_run:
            logger.info(f"[D41_K8S_UTILS] DRY_RUN: create_job {job_name} in {namespace}")
            return job_name

        try:
            api = self._get_client()
            if api is None:
                logger.warning(f"[D41_K8S_UTILS] K8s client not available, skipping job creation")
                return job_name

            from kubernetes.client import V1Job
            job_obj = V1Job(**manifest)
            api.create_namespaced_job(namespace, job_obj)
            logger.info(f"[D41_K8S_UTILS] Created job: {job_name} in {namespace}")
            return job_name
        except Exception as e:
            logger.error(f"[D41_K8S_UTILS] Failed to create job: {e}")
            raise

    def get_job_status(self, job_id: str, namespace: str = "default") -> K8sJobStatus:
        """
        K8s Job 상태 조회.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            K8sJobStatus
        """
        if self.dry_run:
            logger.debug(f"[D41_K8S_UTILS] DRY_RUN: get_job_status {job_id}")
            return K8sJobStatus(job_id=job_id, namespace=namespace, status="Succeeded")

        try:
            api = self._get_client()
            if api is None:
                logger.warning(f"[D41_K8S_UTILS] K8s client not available, returning Unknown status")
                return K8sJobStatus(job_id=job_id, namespace=namespace, status="Unknown")

            job = api.read_namespaced_job(job_id, namespace)
            status = job.status

            # 상태 판정
            if status.succeeded and status.succeeded > 0:
                job_status = "Succeeded"
            elif status.failed and status.failed > 0:
                job_status = "Failed"
            elif status.active and status.active > 0:
                job_status = "Running"
            else:
                job_status = "Pending"

            return K8sJobStatus(
                job_id=job_id,
                namespace=namespace,
                status=job_status,
                message=str(status.conditions) if status.conditions else None,
                start_time=str(status.start_time) if status.start_time else None,
                completion_time=str(status.completion_time) if status.completion_time else None,
            )
        except Exception as e:
            logger.error(f"[D41_K8S_UTILS] Failed to get job status: {e}")
            return K8sJobStatus(job_id=job_id, namespace=namespace, status="Unknown", message=str(e))

    def get_pod_logs(self, job_id: str, namespace: str = "default") -> str:
        """
        K8s Pod 로그 수집.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            Pod 로그 (stdout)
        """
        if self.dry_run:
            logger.debug(f"[D41_K8S_UTILS] DRY_RUN: get_pod_logs {job_id}")
            return "[DRY_RUN] No logs available"

        try:
            api = self._get_client()
            if api is None:
                logger.warning(f"[D41_K8S_UTILS] K8s client not available, returning empty logs")
                return ""

            from kubernetes import client
            v1 = client.CoreV1Api()

            # Job에 연결된 Pod 찾기
            pods = v1.list_namespaced_pod(namespace, label_selector=f"job-name={job_id}")
            if not pods.items:
                logger.warning(f"[D41_K8S_UTILS] No pods found for job {job_id}")
                return ""

            pod_name = pods.items[0].metadata.name
            logs = v1.read_namespaced_pod_log(pod_name, namespace)
            logger.debug(f"[D41_K8S_UTILS] Retrieved logs for pod {pod_name}")
            return logs
        except Exception as e:
            logger.error(f"[D41_K8S_UTILS] Failed to get pod logs: {e}")
            return f"[ERROR] Failed to retrieve logs: {e}"

    def delete_job(self, job_id: str, namespace: str = "default") -> bool:
        """
        K8s Job 삭제.

        Args:
            job_id: Job 이름
            namespace: K8s namespace

        Returns:
            성공 여부
        """
        if self.dry_run:
            logger.info(f"[D41_K8S_UTILS] DRY_RUN: delete_job {job_id}")
            return True

        try:
            api = self._get_client()
            if api is None:
                logger.warning(f"[D41_K8S_UTILS] K8s client not available, skipping job deletion")
                return False

            api.delete_namespaced_job(job_id, namespace, propagation_policy="Background")
            logger.info(f"[D41_K8S_UTILS] Deleted job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"[D41_K8S_UTILS] Failed to delete job: {e}")
            return False
