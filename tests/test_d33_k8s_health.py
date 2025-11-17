# -*- coding: utf-8 -*-
"""
D33 Kubernetes Health Evaluation & CI-friendly Alert Layer Tests

K8s 건강 상태 평가 및 CI 친화적 종료 코드 테스트.
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock

from arbitrage.k8s_health import (
    K8sHealthEvaluator,
    K8sJobHealth,
    K8sHealthSnapshot,
    generate_health_report_text,
    HealthLevel
)
from arbitrage.k8s_monitor import (
    K8sMonitorSnapshot,
    K8sJobStatus
)


class TestK8sHealthEvaluator:
    """K8sHealthEvaluator 테스트"""
    
    @pytest.fixture
    def evaluator(self):
        """평가기 인스턴스"""
        return K8sHealthEvaluator(
            warn_on_pending=True,
            treat_unknown_as_error=True
        )
    
    @pytest.fixture
    def sample_snapshot_empty(self):
        """빈 스냅샷"""
        return K8sMonitorSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs=[],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=[]
        )
    
    def test_evaluator_creation(self, evaluator):
        """평가기 생성"""
        assert evaluator is not None
        assert evaluator.warn_on_pending is True
        assert evaluator.treat_unknown_as_error is True
    
    def test_evaluator_with_options(self):
        """평가기 옵션"""
        evaluator = K8sHealthEvaluator(
            warn_on_pending=False,
            treat_unknown_as_error=False
        )
        
        assert evaluator.warn_on_pending is False
        assert evaluator.treat_unknown_as_error is False
    
    def test_evaluate_empty_snapshot(self, evaluator, sample_snapshot_empty):
        """빈 스냅샷 평가"""
        health = evaluator.evaluate(sample_snapshot_empty)
        
        assert health.namespace == "trading-bots"
        assert len(health.jobs_health) == 0
        assert health.overall_health == "OK"
    
    def test_job_phase_succeeded(self, evaluator):
        """Job 단계: SUCCEEDED"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "OK"
        assert len(job_health.reasons) == 0
    
    def test_job_phase_running(self, evaluator):
        """Job 단계: RUNNING"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=1,
            phase="RUNNING",
            start_time="2025-11-16T10:00:00Z",
            completion_time=None
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "OK"
        assert len(job_health.reasons) == 0
    
    def test_job_phase_failed(self, evaluator):
        """Job 단계: FAILED"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=1,
            active=0,
            phase="FAILED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "ERROR"
        assert "job_failed" in job_health.reasons
    
    def test_job_phase_pending_warn(self, evaluator):
        """Job 단계: PENDING (warn_on_pending=True)"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=0,
            phase="PENDING",
            start_time=None,
            completion_time=None
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "WARN"
        assert "pending" in job_health.reasons
    
    def test_job_phase_pending_ok(self):
        """Job 단계: PENDING (warn_on_pending=False)"""
        evaluator = K8sHealthEvaluator(warn_on_pending=False)
        
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=0,
            phase="PENDING",
            start_time=None,
            completion_time=None
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "OK"
    
    def test_job_phase_unknown_error(self, evaluator):
        """Job 단계: UNKNOWN (treat_unknown_as_error=True)"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=0,
            phase="UNKNOWN",
            start_time="2025-11-16T10:00:00Z",
            completion_time=None
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "ERROR"
        assert "unknown_phase" in job_health.reasons
    
    def test_job_phase_unknown_warn(self):
        """Job 단계: UNKNOWN (treat_unknown_as_error=False)"""
        evaluator = K8sHealthEvaluator(treat_unknown_as_error=False)
        
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=0,
            phase="UNKNOWN",
            start_time="2025-11-16T10:00:00Z",
            completion_time=None
        )
        
        job_health = evaluator._evaluate_job(job)
        
        assert job_health.health == "WARN"
        assert "unknown_phase" in job_health.reasons
    
    def test_overall_health_all_ok(self, evaluator, sample_snapshot_empty):
        """전체 건강: 모두 OK"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        snapshot = K8sMonitorSnapshot(
            namespace="default",
            selector="app=test",
            jobs=[job],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=[]
        )
        
        health = evaluator.evaluate(snapshot)
        
        assert health.overall_health == "OK"
    
    def test_overall_health_with_warn(self, evaluator):
        """전체 건강: WARN 포함"""
        job_ok = K8sJobStatus(
            job_name="job-ok",
            namespace="default",
            labels={},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        job_warn = K8sJobStatus(
            job_name="job-warn",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=0,
            active=0,
            phase="PENDING",
            start_time=None,
            completion_time=None
        )
        
        snapshot = K8sMonitorSnapshot(
            namespace="default",
            selector="app=test",
            jobs=[job_ok, job_warn],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=[]
        )
        
        health = evaluator.evaluate(snapshot)
        
        assert health.overall_health == "WARN"
    
    def test_overall_health_with_error(self, evaluator):
        """전체 건강: ERROR 포함"""
        job_ok = K8sJobStatus(
            job_name="job-ok",
            namespace="default",
            labels={},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        job_error = K8sJobStatus(
            job_name="job-error",
            namespace="default",
            labels={},
            completions=1,
            succeeded=0,
            failed=1,
            active=0,
            phase="FAILED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        snapshot = K8sMonitorSnapshot(
            namespace="default",
            selector="app=test",
            jobs=[job_ok, job_error],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=[]
        )
        
        health = evaluator.evaluate(snapshot)
        
        assert health.overall_health == "ERROR"
    
    def test_overall_health_with_monitor_errors(self, evaluator):
        """전체 건강: 모니터링 에러 포함"""
        job = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        snapshot = K8sMonitorSnapshot(
            namespace="default",
            selector="app=test",
            jobs=[job],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=["kubectl not found", "Network error"]
        )
        
        health = evaluator.evaluate(snapshot)
        
        # Job은 OK이지만 에러가 있으므로 전체는 WARN
        assert health.overall_health == "WARN"
        assert len(health.errors) == 2


class TestK8sJobHealth:
    """K8sJobHealth 테스트"""
    
    def test_job_health_creation(self):
        """Job 건강 상태 생성"""
        job_health = K8sJobHealth(
            job_name="test-job",
            namespace="default",
            phase="SUCCEEDED",
            succeeded=1,
            failed=0,
            active=0,
            health="OK",
            reasons=[],
            labels={"app": "test"}
        )
        
        assert job_health.job_name == "test-job"
        assert job_health.health == "OK"


class TestK8sHealthSnapshot:
    """K8sHealthSnapshot 테스트"""
    
    def test_health_snapshot_creation(self):
        """건강 상태 스냅샷 생성"""
        snapshot = K8sHealthSnapshot(
            namespace="default",
            selector="app=test",
            jobs_health=[],
            errors=[],
            overall_health="OK"
        )
        
        assert snapshot.namespace == "default"
        assert snapshot.overall_health == "OK"


class TestHealthReportText:
    """건강 상태 보고서 텍스트 생성 테스트"""
    
    def test_generate_health_report_text_empty(self):
        """빈 건강 상태 보고서"""
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[],
            errors=[],
            overall_health="OK",
            timestamp="2025-11-16T10:00:00Z"
        )
        
        text = generate_health_report_text(snapshot)
        
        assert "[D33_K8S_HEALTH] KUBERNETES HEALTH EVALUATION SNAPSHOT" in text
        assert "Overall Health:" in text
        assert "OK" in text
    
    def test_generate_health_report_text_with_jobs(self):
        """Job이 있는 건강 상태 보고서"""
        job_health = K8sJobHealth(
            job_name="test-job",
            namespace="trading-bots",
            phase="SUCCEEDED",
            succeeded=1,
            failed=0,
            active=0,
            health="OK",
            reasons=[],
            labels={"app": "test"}
        )
        
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[job_health],
            errors=[],
            overall_health="OK",
            timestamp="2025-11-16T10:00:00Z"
        )
        
        text = generate_health_report_text(snapshot)
        
        assert "test-job" in text
        assert "SUCCEEDED" in text
        assert "OK" in text
    
    def test_generate_health_report_text_with_errors(self):
        """에러가 있는 건강 상태 보고서"""
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[],
            errors=["kubectl not found", "Network error"],
            overall_health="WARN",
            timestamp="2025-11-16T10:00:00Z"
        )
        
        text = generate_health_report_text(snapshot)
        
        assert "[ERRORS]" in text
        assert "kubectl not found" in text
        assert "Network error" in text


class TestObservabilityPolicyD33:
    """D33 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_health_scripts(self):
        """건강 평가 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_health.py",
            "scripts/check_k8s_health.py"
        ]
        
        forbidden_patterns = [
            "예상 출력",
            "expected output",
            "sample output",
            "샘플 결과",
            "샘플 PnL",
            "win_rate",
            "pnl=",
            "trades_total="
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


class TestReadOnlyBehaviorD33:
    """D33 Read-only 동작 테스트"""
    
    def test_health_evaluator_no_modifications(self):
        """건강 평가기는 수정 작업 없음"""
        evaluator = K8sHealthEvaluator()
        
        # 평가기의 모든 공개 메서드 확인
        public_methods = [m for m in dir(evaluator) if not m.startswith('_')]
        
        # 파괴적 메서드가 없어야 함
        destructive_methods = ['delete', 'remove', 'destroy', 'kill', 'scale', 'patch', 'apply']
        
        for method in public_methods:
            for destructive in destructive_methods:
                assert destructive not in method.lower(), \
                    f"Found potentially destructive method: {method}"


class TestExitCodes:
    """종료 코드 테스트"""
    
    def test_exit_code_ok(self):
        """종료 코드: OK"""
        from scripts.check_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("OK", strict=False) == 0
        assert _determine_exit_code("OK", strict=True) == 0
    
    def test_exit_code_warn_not_strict(self):
        """종료 코드: WARN (strict=False)"""
        from scripts.check_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("WARN", strict=False) == 0
    
    def test_exit_code_warn_strict(self):
        """종료 코드: WARN (strict=True)"""
        from scripts.check_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("WARN", strict=True) == 1
    
    def test_exit_code_error(self):
        """종료 코드: ERROR"""
        from scripts.check_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("ERROR", strict=False) == 2
        assert _determine_exit_code("ERROR", strict=True) == 2
