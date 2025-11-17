# -*- coding: utf-8 -*-
"""
D28 Tuning Orchestrator

분산 / 병렬 튜닝 세션을 관리하는 Orchestrator.
여러 워커 프로세스로 run_d24_tuning_session.py를 실행/관리.
"""

import logging
import os
import subprocess
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from arbitrage.state_manager import StateManager

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job 상태"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TuningJob:
    """튜닝 Job"""
    job_id: str
    session_id: str
    worker_id: str
    iterations: int
    mode: str                           # "paper" | "shadow" | "live"
    env: str                            # "docker" | "local"
    optimizer: str                      # "bayesian" | "grid" | "random"
    config_path: str
    output_csv: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    return_code: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class OrchestratorConfig:
    """Orchestrator 설정"""
    session_id: str
    total_iterations: int
    workers: int
    mode: str = "paper"
    env: str = "docker"
    optimizer: str = "bayesian"
    config_path: str = "configs/d23_tuning/advanced_baseline.yaml"
    base_output_csv: str = "outputs/d28_tuning_session"


class TuningOrchestrator:
    """분산 튜닝 세션 관리"""
    
    def __init__(
        self,
        config: OrchestratorConfig,
        state_manager: Optional[StateManager] = None
    ):
        """
        Args:
            config: Orchestrator 설정
            state_manager: StateManager (기본: 자동 생성)
        """
        self.config = config
        self.jobs: List[TuningJob] = []
        self.completed_jobs: List[TuningJob] = []
        
        # StateManager 초기화
        if state_manager:
            self.state_manager = state_manager
        else:
            namespace = f"orchestrator:{config.env}"
            self.state_manager = StateManager(
                redis_host=os.getenv("REDIS_HOST", "localhost"),
                redis_port=int(os.getenv("REDIS_PORT", "6379")),
                redis_db=0,
                namespace=namespace,
                enabled=True,
                key_prefix="arbitrage"
            )
        
        logger.info(f"[D28_ORCH] Orchestrator initialized: session={config.session_id}, workers={config.workers}")
    
    def plan_jobs(self) -> List[TuningJob]:
        """
        총 반복을 워커로 분할하여 Job 계획
        
        Returns:
            TuningJob 리스트
        """
        self.jobs = []
        
        # 반복을 워커로 분할 (round-robin 방식)
        iterations_per_worker = self.config.total_iterations // self.config.workers
        remainder = self.config.total_iterations % self.config.workers
        
        for worker_idx in range(self.config.workers):
            # 처음 remainder개 워커는 +1 iteration
            iterations = iterations_per_worker + (1 if worker_idx < remainder else 0)
            
            worker_id = f"worker-{worker_idx + 1}"
            job_id = str(uuid.uuid4())
            
            output_csv = None
            if self.config.base_output_csv:
                output_csv = f"{self.config.base_output_csv}_{worker_id}.csv"
            
            job = TuningJob(
                job_id=job_id,
                session_id=self.config.session_id,
                worker_id=worker_id,
                iterations=iterations,
                mode=self.config.mode,
                env=self.config.env,
                optimizer=self.config.optimizer,
                config_path=self.config.config_path,
                output_csv=output_csv,
                status=JobStatus.PENDING
            )
            
            self.jobs.append(job)
            logger.info(f"[D28_ORCH] Planned job: {worker_id} with {iterations} iterations")
        
        return self.jobs
    
    def run_all(self) -> bool:
        """
        모든 Job을 순차 실행
        
        Returns:
            성공 여부
        """
        if not self.jobs:
            logger.warning("[D28_ORCH] No jobs planned. Call plan_jobs() first.")
            return False
        
        logger.info(f"[D28_ORCH] Starting orchestration: {len(self.jobs)} jobs")
        
        success_count = 0
        failed_count = 0
        
        for job in self.jobs:
            try:
                completed_job = self._run_single_job(job)
                self.completed_jobs.append(completed_job)
                
                if completed_job.status == JobStatus.SUCCESS:
                    success_count += 1
                else:
                    failed_count += 1
            
            except Exception as e:
                logger.error(f"[D28_ORCH] Job {job.job_id} failed with exception: {e}")
                job.status = JobStatus.FAILED
                job.finished_at = datetime.now().isoformat()
                self.completed_jobs.append(job)
                failed_count += 1
        
        logger.info(f"[D28_ORCH] Orchestration completed: {success_count} success, {failed_count} failed")
        
        return failed_count == 0
    
    def _run_single_job(self, job: TuningJob) -> TuningJob:
        """
        단일 Job 실행 (subprocess)
        
        Args:
            job: TuningJob
        
        Returns:
            완료된 TuningJob
        """
        logger.info(f"[D28_ORCH] Starting job: {job.job_id} ({job.worker_id})")
        
        # Job 상태 업데이트: PENDING -> RUNNING
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now().isoformat()
        self._persist_job(job)
        
        # subprocess 명령 구성
        cmd = [
            "python",
            "scripts/run_d24_tuning_session.py",
            "--config", job.config_path,
            "--iterations", str(job.iterations),
            "--mode", job.mode,
            "--env", job.env,
            "--optimizer", job.optimizer,
            "--session-id", job.session_id,
            "--worker-id", job.worker_id
        ]
        
        if job.output_csv:
            cmd.extend(["--output-csv", job.output_csv])
        
        try:
            # subprocess 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1시간 타임아웃
            )
            
            job.return_code = result.returncode
            job.finished_at = datetime.now().isoformat()
            
            if result.returncode == 0:
                job.status = JobStatus.SUCCESS
                logger.info(f"[D28_ORCH] Job {job.job_id} finished: status=SUCCESS, return_code=0")
            else:
                job.status = JobStatus.FAILED
                logger.error(f"[D28_ORCH] Job {job.job_id} finished: status=FAILED, return_code={result.returncode}")
                logger.error(f"[D28_ORCH] stderr: {result.stderr[:500]}")
        
        except subprocess.TimeoutExpired:
            job.status = JobStatus.FAILED
            job.return_code = -1
            job.finished_at = datetime.now().isoformat()
            logger.error(f"[D28_ORCH] Job {job.job_id} timeout")
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.return_code = -1
            job.finished_at = datetime.now().isoformat()
            logger.error(f"[D28_ORCH] Job {job.job_id} error: {e}")
        
        # Job 상태 저장
        self._persist_job(job)
        
        return job
    
    def _persist_job(self, job: TuningJob) -> None:
        """Job 상태를 StateManager에 저장"""
        try:
            key = self.state_manager._get_key(
                "session", self.config.session_id, "job", job.job_id
            )
            
            job_data = job.to_dict()
            job_data['status'] = job.status.value  # Enum을 문자열로
            
            self.state_manager._set_redis_or_memory(key, job_data)
            logger.debug(f"[D28_ORCH] Job persisted: {job.job_id}")
        
        except Exception as e:
            logger.warning(f"[D28_ORCH] Failed to persist job: {e}")
    
    def get_job_statuses(self) -> List[TuningJob]:
        """
        StateManager에서 현재 Job 상태 조회
        
        Returns:
            TuningJob 리스트
        """
        try:
            jobs = []
            
            if self.state_manager._redis_connected and self.state_manager._redis:
                try:
                    # 패턴: orchestrator:{env}:arbitrage:session:{session_id}:job:*
                    pattern = self.state_manager._get_key(
                        "session", self.config.session_id, "job", "*"
                    )
                    keys = self.state_manager._redis.keys(pattern)
                    
                    for key in keys:
                        data = self.state_manager._redis.hgetall(key)
                        if data:
                            # status를 JobStatus enum으로 변환
                            if 'status' in data:
                                data['status'] = JobStatus(data['status'])
                            job = TuningJob(**data)
                            jobs.append(job)
                
                except Exception as e:
                    logger.warning(f"[D28_ORCH] Failed to scan Redis: {e}")
            else:
                # in-memory fallback
                for key, value in self.state_manager._in_memory_store.items():
                    if f"session:{self.config.session_id}:job:" in key:
                        if isinstance(value, dict):
                            if 'status' in value and isinstance(value['status'], str):
                                value['status'] = JobStatus(value['status'])
                            job = TuningJob(**value)
                            jobs.append(job)
            
            return jobs
        
        except Exception as e:
            logger.error(f"[D28_ORCH] Failed to get job statuses: {e}")
            return []
    
    def get_summary(self) -> Dict:
        """
        Orchestrator 실행 요약
        
        Returns:
            요약 딕셔너리
        """
        total_jobs = len(self.completed_jobs)
        success_jobs = len([j for j in self.completed_jobs if j.status == JobStatus.SUCCESS])
        failed_jobs = len([j for j in self.completed_jobs if j.status == JobStatus.FAILED])
        
        total_iterations = sum(j.iterations for j in self.completed_jobs)
        
        return {
            "session_id": self.config.session_id,
            "total_jobs": total_jobs,
            "success_jobs": success_jobs,
            "failed_jobs": failed_jobs,
            "total_iterations": total_iterations,
            "workers": self.config.workers,
            "mode": self.config.mode,
            "env": self.config.env,
            "optimizer": self.config.optimizer
        }
