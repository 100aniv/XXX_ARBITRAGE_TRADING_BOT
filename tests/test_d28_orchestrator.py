# -*- coding: utf-8 -*-
"""
D28 Tuning Orchestrator Tests

Orchestrator 기능 및 Job 관리 테스트.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from arbitrage.tuning_orchestrator import (
    TuningOrchestrator,
    OrchestratorConfig,
    TuningJob,
    JobStatus
)
from arbitrage.state_manager import StateManager


class TestJobStatus:
    """JobStatus Enum 테스트"""
    
    def test_job_status_values(self):
        """JobStatus 값"""
        assert JobStatus.PENDING.value == "PENDING"
        assert JobStatus.RUNNING.value == "RUNNING"
        assert JobStatus.SUCCESS.value == "SUCCESS"
        assert JobStatus.FAILED.value == "FAILED"
        assert JobStatus.CANCELLED.value == "CANCELLED"


class TestTuningJob:
    """TuningJob 테스트"""
    
    def test_tuning_job_creation(self):
        """TuningJob 생성"""
        job = TuningJob(
            job_id="job-1",
            session_id="session-123",
            worker_id="worker-1",
            iterations=3,
            mode="paper",
            env="docker",
            optimizer="bayesian",
            config_path="configs/d23_tuning/advanced_baseline.yaml"
        )
        
        assert job.job_id == "job-1"
        assert job.session_id == "session-123"
        assert job.worker_id == "worker-1"
        assert job.iterations == 3
        assert job.status == JobStatus.PENDING
    
    def test_tuning_job_to_dict(self):
        """TuningJob 딕셔너리 변환"""
        job = TuningJob(
            job_id="job-1",
            session_id="session-123",
            worker_id="worker-1",
            iterations=3,
            mode="paper",
            env="docker",
            optimizer="bayesian",
            config_path="configs/d23_tuning/advanced_baseline.yaml"
        )
        
        job_dict = job.to_dict()
        
        assert job_dict['job_id'] == "job-1"
        assert job_dict['iterations'] == 3
        assert isinstance(job_dict['status'], JobStatus)


class TestOrchestratorConfig:
    """OrchestratorConfig 테스트"""
    
    def test_orchestrator_config_creation(self):
        """OrchestratorConfig 생성"""
        config = OrchestratorConfig(
            session_id="session-123",
            total_iterations=10,
            workers=3,
            mode="paper",
            env="docker"
        )
        
        assert config.session_id == "session-123"
        assert config.total_iterations == 10
        assert config.workers == 3


class TestTuningOrchestrator:
    """TuningOrchestrator 테스트"""
    
    @pytest.fixture
    def orchestrator_config(self):
        """Orchestrator 설정"""
        return OrchestratorConfig(
            session_id="session-123",
            total_iterations=10,
            workers=3,
            mode="paper",
            env="docker",
            optimizer="bayesian",
            config_path="configs/d23_tuning/advanced_baseline.yaml"
        )
    
    def test_orchestrator_creation(self, orchestrator_config):
        """Orchestrator 생성"""
        with patch('arbitrage.tuning_orchestrator.StateManager'):
            orchestrator = TuningOrchestrator(orchestrator_config)
            
            assert orchestrator.config.session_id == "session-123"
            assert orchestrator.config.workers == 3
    
    def test_plan_jobs_distribution(self, orchestrator_config):
        """Job 분배 계획"""
        with patch('arbitrage.tuning_orchestrator.StateManager'):
            orchestrator = TuningOrchestrator(orchestrator_config)
            jobs = orchestrator.plan_jobs()
            
            # 3개 워커, 10개 반복 -> 4, 3, 3
            assert len(jobs) == 3
            
            total_iterations = sum(j.iterations for j in jobs)
            assert total_iterations == 10
            
            # 최소/최대 차이가 1 이내
            iterations_list = [j.iterations for j in jobs]
            assert max(iterations_list) - min(iterations_list) <= 1
    
    def test_plan_jobs_worker_ids(self, orchestrator_config):
        """Job 워커 ID 생성"""
        with patch('arbitrage.tuning_orchestrator.StateManager'):
            orchestrator = TuningOrchestrator(orchestrator_config)
            jobs = orchestrator.plan_jobs()
            
            worker_ids = [j.worker_id for j in jobs]
            
            assert "worker-1" in worker_ids
            assert "worker-2" in worker_ids
            assert "worker-3" in worker_ids
    
    def test_plan_jobs_session_id(self, orchestrator_config):
        """Job 세션 ID"""
        with patch('arbitrage.tuning_orchestrator.StateManager'):
            orchestrator = TuningOrchestrator(orchestrator_config)
            jobs = orchestrator.plan_jobs()
            
            for job in jobs:
                assert job.session_id == "session-123"
    
    def test_get_summary(self, orchestrator_config):
        """Orchestrator 요약"""
        with patch('arbitrage.tuning_orchestrator.StateManager'):
            orchestrator = TuningOrchestrator(orchestrator_config)
            orchestrator.plan_jobs()
            
            # 모든 job을 SUCCESS로 완료 처리
            for job in orchestrator.jobs:
                job.status = JobStatus.SUCCESS
                orchestrator.completed_jobs.append(job)
            
            summary = orchestrator.get_summary()
            
            assert summary['session_id'] == "session-123"
            assert summary['total_jobs'] == 3
            assert summary['success_jobs'] == 3
            assert summary['failed_jobs'] == 0
            assert summary['total_iterations'] == 10


class TestJobPersistence:
    """Job 상태 저장 테스트"""
    
    def test_persist_job(self):
        """Job 상태 저장"""
        mock_state_manager = MagicMock()
        
        config = OrchestratorConfig(
            session_id="session-123",
            total_iterations=5,
            workers=1,
            env="docker"
        )
        
        orchestrator = TuningOrchestrator(config, state_manager=mock_state_manager)
        
        job = TuningJob(
            job_id="job-1",
            session_id="session-123",
            worker_id="worker-1",
            iterations=5,
            mode="paper",
            env="docker",
            optimizer="bayesian",
            config_path="configs/d23_tuning/advanced_baseline.yaml",
            status=JobStatus.SUCCESS
        )
        
        orchestrator._persist_job(job)
        
        # StateManager 호출 확인
        mock_state_manager._get_key.assert_called()
        mock_state_manager._set_redis_or_memory.assert_called_once()


class TestObservabilityPolicyD28:
    """D28 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_orchestrator_scripts(self):
        """Orchestrator 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/tuning_orchestrator.py",
            "scripts/run_d28_orchestrator.py"
        ]
        
        forbidden_patterns = [
            "예상 출력",
            "expected output",
            "sample output",
            "샘플 결과"
        ]
        
        for script_path in scripts:
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                script_path
            )
            
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                for pattern in forbidden_patterns:
                    assert pattern not in source.lower(), \
                        f"Found forbidden pattern '{pattern}' in {script_path}"
