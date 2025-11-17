# -*- coding: utf-8 -*-
"""
D41: Kubernetes 기반 Tuning Session Distributed Runner

D39 작업 계획(JSONL)을 K8s Job으로 병렬 실행.
D40 Local Runner의 분산 버전.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

from arbitrage.k8s_utils import K8sClient, K8sJobStatus
from arbitrage.k8s_job_spec_builder import K8sJobSpecBuilder

logger = logging.getLogger(__name__)


@dataclass
class K8sTuningSessionRunResult:
    """K8s 기반 세션 실행 결과 (D40과 동일 포맷)"""

    total_jobs: int
    attempted_jobs: int
    success_jobs: int
    error_jobs: int
    skipped_jobs: int
    exit_code: int
    errors: List[str] = field(default_factory=list)
    job_ids: List[str] = field(default_factory=list)
    pod_logs: Dict[str, str] = field(default_factory=dict)


class K8sTuningSessionRunner:
    """K8s 기반 분산 튜닝 세션 실행기"""

    def __init__(
        self,
        jobs_file: str,
        namespace: str = "default",
        max_parallel: int = 4,
        timeout_per_job: int = 300,
        timeout_session: int = 3600,
        retry_failed: bool = False,
        wait: bool = True,
        k8s_client: Optional[K8sClient] = None,
    ):
        """
        K8s 기반 튜닝 세션 실행기 초기화.

        Args:
            jobs_file: D39 plan_tuning_session에서 생성한 JSONL 파일 경로
            namespace: K8s namespace (기본값: default)
            max_parallel: 동시 실행 Job 수 (기본값: 4)
            timeout_per_job: 각 Job 타임아웃 (초, 기본값: 300)
            timeout_session: 전체 세션 타임아웃 (초, 기본값: 3600)
            retry_failed: 실패 Job 재시도 여부 (기본값: False)
            wait: True면 모든 Job 완료 대기, False면 submit만 (기본값: True)
            k8s_client: K8sClient 인스턴스 (테스트용 mock 주입 가능)
        """
        self.jobs_file = jobs_file
        self.namespace = namespace
        self.max_parallel = max_parallel
        self.timeout_per_job = timeout_per_job
        self.timeout_session = timeout_session
        self.retry_failed = retry_failed
        self.wait = wait
        self.k8s_client = k8s_client or K8sClient(namespace=namespace)
        self.job_spec_builder = K8sJobSpecBuilder(namespace=namespace)

        logger.info(
            f"[D41_K8S_RUNNER] K8sTuningSessionRunner initialized: "
            f"jobs_file={jobs_file}, namespace={namespace}, max_parallel={max_parallel}"
        )

    def load_jobs(self) -> List[Dict[str, Any]]:
        """
        JSONL 파일에서 작업 계획 로드 (D40과 동일).

        Returns:
            작업 dict 리스트
        """
        jobs = []
        jobs_path = Path(self.jobs_file)

        if not jobs_path.exists():
            logger.error(f"[D41_K8S_RUNNER] Jobs file not found: {self.jobs_file}")
            raise FileNotFoundError(f"Jobs file not found: {self.jobs_file}")

        try:
            with open(jobs_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        job = json.loads(line)
                        jobs.append(job)
                    except json.JSONDecodeError as e:
                        logger.error(f"[D41_K8S_RUNNER] JSON parse error at line {line_num}: {e}")
                        raise ValueError(f"Invalid JSON at line {line_num}: {e}")

            logger.info(f"[D41_K8S_RUNNER] Loaded {len(jobs)} jobs from {self.jobs_file}")
            return jobs
        except Exception as e:
            logger.error(f"[D41_K8S_RUNNER] Failed to load jobs: {e}")
            raise

    def _validate_job(self, job: Dict[str, Any]) -> Optional[str]:
        """
        작업 유효성 검사 (D40과 동일).

        Args:
            job: 작업 dict

        Returns:
            오류 메시지 (유효하면 None)
        """
        required_keys = ["job_id", "config"]
        for key in required_keys:
            if key not in job:
                return f"Missing required key: {key}"

        if not isinstance(job["config"], dict):
            return "config must be a dict"

        return None

    def _submit_job(self, job: Dict[str, Any]) -> Optional[str]:
        """
        K8s Job 제출.

        Args:
            job: 작업 dict

        Returns:
            Job ID (성공) 또는 None (실패)
        """
        job_id = job.get("job_id", "unknown")
        config = job.get("config", {})
        output_dir = job.get("output_json_dir", "outputs/tuning")

        try:
            # Job manifest 생성
            manifest = self.job_spec_builder.build_tuning_job(
                job_id=job_id,
                config=config,
                output_dir=output_dir,
                timeout_seconds=self.timeout_per_job,
            )

            # Job 제출
            submitted_job_id = self.k8s_client.create_job(manifest)
            logger.info(f"[D41_K8S_RUNNER] Submitted job: {submitted_job_id}")
            return submitted_job_id
        except Exception as e:
            logger.error(f"[D41_K8S_RUNNER] Failed to submit job {job_id}: {e}")
            return None

    def _wait_for_job(self, job_id: str, timeout: int) -> bool:
        """
        K8s Job 완료 대기.

        Args:
            job_id: Job ID
            timeout: 타임아웃 (초)

        Returns:
            성공 여부
        """
        start_time = time.time()
        poll_interval = 5  # 5초마다 상태 확인

        while time.time() - start_time < timeout:
            try:
                status = self.k8s_client.get_job_status(job_id, self.namespace)

                if status.status == "Succeeded":
                    logger.info(f"[D41_K8S_RUNNER] Job succeeded: {job_id}")
                    return True
                elif status.status == "Failed":
                    logger.error(f"[D41_K8S_RUNNER] Job failed: {job_id}")
                    return False
                elif status.status == "Unknown":
                    logger.warning(f"[D41_K8S_RUNNER] Job status unknown: {job_id}")
                    return False

                logger.debug(f"[D41_K8S_RUNNER] Job {job_id} status: {status.status}")
                time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"[D41_K8S_RUNNER] Error checking job status: {e}")
                return False

        logger.error(f"[D41_K8S_RUNNER] Job timeout: {job_id}")
        return False

    def _collect_results(self, job_id: str) -> Dict[str, Any]:
        """
        Job 결과 수집 (Pod 로그).

        Args:
            job_id: Job ID

        Returns:
            결과 dict
        """
        try:
            logs = self.k8s_client.get_pod_logs(job_id, self.namespace)
            logger.debug(f"[D41_K8S_RUNNER] Collected logs for job {job_id}")
            return {"job_id": job_id, "logs": logs}
        except Exception as e:
            logger.error(f"[D41_K8S_RUNNER] Failed to collect results for {job_id}: {e}")
            return {"job_id": job_id, "logs": f"[ERROR] {e}"}

    def run(self) -> K8sTuningSessionRunResult:
        """
        K8s 기반 병렬 세션 실행.

        Returns:
            K8sTuningSessionRunResult
        """
        logger.info("[D41_K8S_RUNNER] Starting K8s tuning session")

        # 작업 로드
        try:
            jobs = self.load_jobs()
        except Exception as e:
            logger.error(f"[D41_K8S_RUNNER] Failed to load jobs: {e}")
            return K8sTuningSessionRunResult(
                total_jobs=0,
                attempted_jobs=0,
                success_jobs=0,
                error_jobs=0,
                skipped_jobs=0,
                exit_code=2,
                errors=[str(e)],
            )

        total_jobs = len(jobs)
        attempted_jobs = 0
        success_jobs = 0
        error_jobs = 0
        skipped_jobs = 0
        errors = []
        job_ids = []
        pod_logs = {}

        # Job 큐 생성
        job_queue = deque(jobs)
        submitted_jobs = {}  # job_id -> (job_dict, submitted_time)
        completed_jobs = set()

        session_start = time.time()

        while job_queue or submitted_jobs:
            # 세션 타임아웃 확인
            if time.time() - session_start > self.timeout_session:
                logger.error("[D41_K8S_RUNNER] Session timeout")
                errors.append("Session timeout exceeded")
                break

            # 새 Job 제출 (max_parallel 제한)
            while job_queue and len(submitted_jobs) < self.max_parallel:
                job = job_queue.popleft()
                error = self._validate_job(job)

                if error:
                    logger.warning(f"[D41_K8S_RUNNER] Invalid job: {error}")
                    skipped_jobs += 1
                    errors.append(f"Job {job.get('job_id', 'unknown')}: {error}")
                    continue

                job_id = job.get("job_id", "unknown")
                submitted_job_id = self._submit_job(job)

                if submitted_job_id:
                    submitted_jobs[submitted_job_id] = (job, time.time())
                    job_ids.append(submitted_job_id)
                    attempted_jobs += 1
                else:
                    error_jobs += 1
                    errors.append(f"Failed to submit job {job_id}")

            # 완료된 Job 확인
            for submitted_job_id in list(submitted_jobs.keys()):
                if submitted_job_id in completed_jobs:
                    continue

                job_dict, submit_time = submitted_jobs[submitted_job_id]
                elapsed = time.time() - submit_time

                # 상태 확인 (빠른 체크)
                try:
                    status = self.k8s_client.get_job_status(submitted_job_id, self.namespace)
                    if status.status == "Succeeded":
                        # 성공
                        success_jobs += 1
                        results = self._collect_results(submitted_job_id)
                        pod_logs[submitted_job_id] = results.get("logs", "")
                        completed_jobs.add(submitted_job_id)
                        del submitted_jobs[submitted_job_id]
                    elif status.status == "Failed":
                        # 실패
                        error_jobs += 1
                        errors.append(f"Job failed: {submitted_job_id}")
                        completed_jobs.add(submitted_job_id)
                        del submitted_jobs[submitted_job_id]
                    elif elapsed > self.timeout_per_job:
                        # 타임아웃
                        error_jobs += 1
                        errors.append(f"Job timeout: {submitted_job_id}")
                        completed_jobs.add(submitted_job_id)
                        del submitted_jobs[submitted_job_id]
                except Exception as e:
                    logger.error(f"[D41_K8S_RUNNER] Error checking job {submitted_job_id}: {e}")
                    if elapsed > self.timeout_per_job:
                        error_jobs += 1
                        errors.append(f"Job error: {submitted_job_id}")
                        completed_jobs.add(submitted_job_id)
                        del submitted_jobs[submitted_job_id]

            # 대기 (CPU 절약)
            if submitted_jobs:
                time.sleep(1)

            # wait=False면 submit만 하고 종료
            if not self.wait and not job_queue:
                logger.info("[D41_K8S_RUNNER] wait=False, exiting after submit")
                break

        # 결과 계산
        exit_code = 0
        if error_jobs > 0:
            exit_code = 1
        if attempted_jobs == 0 and total_jobs > 0:
            exit_code = 2

        result = K8sTuningSessionRunResult(
            total_jobs=total_jobs,
            attempted_jobs=attempted_jobs,
            success_jobs=success_jobs,
            error_jobs=error_jobs,
            skipped_jobs=skipped_jobs,
            exit_code=exit_code,
            errors=errors,
            job_ids=job_ids,
            pod_logs=pod_logs,
        )

        logger.info(
            f"[D41_K8S_RUNNER] Session complete: "
            f"total={total_jobs}, attempted={attempted_jobs}, "
            f"success={success_jobs}, error={error_jobs}, exit_code={exit_code}"
        )

        return result
