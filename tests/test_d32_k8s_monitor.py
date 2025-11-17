# -*- coding: utf-8 -*-
"""
D32 Kubernetes Job/Pod Monitoring & Log Collection Tests

K8s Job/Pod 모니터링 및 로그 수집 테스트.
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock

from arbitrage.k8s_monitor import (
    K8sJobMonitor,
    K8sPodLog,
    K8sJobStatus,
    K8sMonitorSnapshot,
    generate_monitor_report_text
)


class TestK8sJobMonitor:
    """K8sJobMonitor 테스트"""
    
    @pytest.fixture
    def monitor(self):
        """모니터 인스턴스"""
        return K8sJobMonitor(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning,session_id=test-session"
        )
    
    @pytest.fixture
    def sample_jobs_json(self):
        """샘플 Job JSON"""
        return {
            "apiVersion": "batch/v1",
            "items": [
                {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "metadata": {
                        "name": "arb-tuning-test-worker-1-0",
                        "namespace": "trading-bots",
                        "labels": {
                            "app": "arbitrage-tuning",
                            "session_id": "test-session",
                            "worker_id": "worker-1"
                        }
                    },
                    "spec": {
                        "completions": 1,
                        "parallelism": 1
                    },
                    "status": {
                        "succeeded": 1,
                        "startTime": "2025-11-16T10:00:00Z",
                        "completionTime": "2025-11-16T10:05:00Z"
                    }
                }
            ]
        }
    
    @pytest.fixture
    def sample_pods_json(self):
        """샘플 Pod JSON"""
        return {
            "apiVersion": "v1",
            "items": [
                {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "metadata": {
                        "name": "arb-tuning-test-worker-1-0-abc123",
                        "namespace": "trading-bots",
                        "labels": {
                            "app": "arbitrage-tuning",
                            "session_id": "test-session"
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "tuning-container",
                                "image": "test:latest"
                            }
                        ]
                    },
                    "status": {
                        "phase": "Succeeded"
                    }
                }
            ]
        }
    
    def test_monitor_creation(self, monitor):
        """Monitor 생성"""
        assert monitor is not None
        assert monitor.namespace == "trading-bots"
        assert monitor.label_selector == "app=arbitrage-tuning,session_id=test-session"
        assert monitor.max_log_lines == 100
    
    def test_monitor_with_kubeconfig(self):
        """kubeconfig 지정"""
        monitor = K8sJobMonitor(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            kubeconfig="/path/to/kubeconfig",
            context="my-cluster",
            max_log_lines=50
        )
        
        assert monitor.kubeconfig == "/path/to/kubeconfig"
        assert monitor.context == "my-cluster"
        assert monitor.max_log_lines == 50
    
    def test_load_snapshot_no_kubectl(self, monitor):
        """kubectl 없을 때"""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("kubectl not found")
            
            snapshot = monitor.load_snapshot()
            
            assert snapshot.namespace == "trading-bots"
            assert len(snapshot.jobs) == 0
            assert len(snapshot.pods_logs) == 0
            assert len(snapshot.errors) > 0
    
    def test_load_jobs_success(self, monitor, sample_jobs_json):
        """Job 로드 성공"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_jobs_json),
                stderr=""
            )
            
            jobs = monitor._load_jobs()
            
            assert len(jobs) == 1
            assert jobs[0].job_name == "arb-tuning-test-worker-1-0"
            assert jobs[0].namespace == "trading-bots"
            assert jobs[0].phase == "SUCCEEDED"
            assert jobs[0].succeeded == 1
    
    def test_load_jobs_kubectl_failure(self, monitor):
        """Job 로드 실패 (kubectl 에러)"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: namespace not found"
            )
            
            jobs = monitor._load_jobs()
            
            assert len(jobs) == 0
    
    def test_load_jobs_json_decode_error(self, monitor):
        """Job 로드 실패 (JSON 파싱 에러)"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="invalid json",
                stderr=""
            )
            
            from arbitrage.k8s_monitor import K8sMonitorError
            with pytest.raises(K8sMonitorError):
                monitor._load_jobs()
    
    def test_load_jobs_timeout(self, monitor):
        """Job 로드 실패 (타임아웃)"""
        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("kubectl", 10)
            
            from arbitrage.k8s_monitor import K8sMonitorError
            with pytest.raises(K8sMonitorError):
                monitor._load_jobs()
    
    def test_load_pod_logs_success(self, monitor, sample_pods_json):
        """Pod 로그 로드 성공"""
        with patch('subprocess.run') as mock_run:
            # get pods 호출
            get_pods_result = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_pods_json),
                stderr=""
            )
            
            # logs 호출
            logs_result = MagicMock(
                returncode=0,
                stdout="log line 1\nlog line 2\nlog line 3",
                stderr=""
            )
            
            mock_run.side_effect = [get_pods_result, logs_result]
            
            pods_logs = monitor._load_pod_logs()
            
            assert len(pods_logs) == 1
            assert pods_logs[0].pod_name == "arb-tuning-test-worker-1-0-abc123"
            assert pods_logs[0].container_name == "tuning-container"
            assert len(pods_logs[0].lines) == 3
    
    def test_load_pod_logs_no_logs(self, monitor, sample_pods_json):
        """Pod 로그 없음"""
        with patch('subprocess.run') as mock_run:
            # get pods 호출
            get_pods_result = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_pods_json),
                stderr=""
            )
            
            # logs 호출 (실패)
            logs_result = MagicMock(
                returncode=1,
                stdout="",
                stderr="No logs available"
            )
            
            mock_run.side_effect = [get_pods_result, logs_result]
            
            pods_logs = monitor._load_pod_logs()
            
            assert len(pods_logs) == 1
            assert pods_logs[0].lines == []
    
    def test_parse_job_item_succeeded(self, monitor):
        """Job 항목 파싱 (성공)"""
        item = {
            "metadata": {
                "name": "test-job",
                "namespace": "trading-bots",
                "labels": {"app": "test"}
            },
            "spec": {
                "completions": 1
            },
            "status": {
                "succeeded": 1,
                "startTime": "2025-11-16T10:00:00Z",
                "completionTime": "2025-11-16T10:05:00Z"
            }
        }
        
        job_status = monitor._parse_job_item(item)
        
        assert job_status.job_name == "test-job"
        assert job_status.phase == "SUCCEEDED"
        assert job_status.succeeded == 1
    
    def test_parse_job_item_failed(self, monitor):
        """Job 항목 파싱 (실패)"""
        item = {
            "metadata": {
                "name": "test-job",
                "namespace": "trading-bots",
                "labels": {}
            },
            "spec": {},
            "status": {
                "failed": 1,
                "startTime": "2025-11-16T10:00:00Z"
            }
        }
        
        job_status = monitor._parse_job_item(item)
        
        assert job_status.phase == "FAILED"
        assert job_status.failed == 1
    
    def test_parse_job_item_running(self, monitor):
        """Job 항목 파싱 (실행 중)"""
        item = {
            "metadata": {
                "name": "test-job",
                "namespace": "trading-bots",
                "labels": {}
            },
            "spec": {},
            "status": {
                "active": 1,
                "startTime": "2025-11-16T10:00:00Z"
            }
        }
        
        job_status = monitor._parse_job_item(item)
        
        assert job_status.phase == "RUNNING"
        assert job_status.active == 1
    
    def test_determine_job_phase_pending(self, monitor):
        """Job 단계 결정 (대기 중)"""
        status = {}
        
        phase = monitor._determine_job_phase(status)
        
        assert phase == "PENDING"
    
    def test_fetch_pod_log_success(self, monitor):
        """Pod 로그 수집 성공"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="log line 1\nlog line 2",
                stderr=""
            )
            
            pod_log = monitor._fetch_pod_log(
                "test-pod",
                "trading-bots",
                "test-container"
            )
            
            assert pod_log is not None
            assert pod_log.pod_name == "test-pod"
            assert len(pod_log.lines) == 2
    
    def test_fetch_pod_log_failure(self, monitor):
        """Pod 로그 수집 실패"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Pod not found"
            )
            
            pod_log = monitor._fetch_pod_log(
                "test-pod",
                "trading-bots",
                "test-container"
            )
            
            assert pod_log is not None
            assert pod_log.lines == []


class TestK8sPodLog:
    """K8sPodLog 테스트"""
    
    def test_pod_log_creation(self):
        """Pod 로그 생성"""
        pod_log = K8sPodLog(
            pod_name="test-pod",
            namespace="default",
            container_name="test-container",
            lines=["line 1", "line 2"]
        )
        
        assert pod_log.pod_name == "test-pod"
        assert len(pod_log.lines) == 2


class TestK8sJobStatus:
    """K8sJobStatus 테스트"""
    
    def test_job_status_creation(self):
        """Job 상태 생성"""
        job_status = K8sJobStatus(
            job_name="test-job",
            namespace="default",
            labels={"app": "test"},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        assert job_status.job_name == "test-job"
        assert job_status.phase == "SUCCEEDED"


class TestK8sMonitorSnapshot:
    """K8sMonitorSnapshot 테스트"""
    
    def test_snapshot_creation(self):
        """스냅샷 생성"""
        snapshot = K8sMonitorSnapshot(
            namespace="default",
            selector="app=test",
            jobs=[],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z"
        )
        
        assert snapshot.namespace == "default"
        assert len(snapshot.jobs) == 0
        assert len(snapshot.errors) == 0


class TestMonitorReportText:
    """모니터 보고서 텍스트 생성 테스트"""
    
    def test_generate_monitor_report_text_empty(self):
        """빈 스냅샷 보고서"""
        snapshot = K8sMonitorSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs=[],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z"
        )
        
        text = generate_monitor_report_text(snapshot)
        
        assert "[D32_K8S_MONITOR] KUBERNETES JOB/POD MONITORING SNAPSHOT" in text
        assert "Namespace:" in text
        assert "Label Selector:" in text
    
    def test_generate_monitor_report_text_with_jobs(self):
        """Job이 있는 스냅샷 보고서"""
        job_status = K8sJobStatus(
            job_name="test-job",
            namespace="trading-bots",
            labels={"app": "test"},
            completions=1,
            succeeded=1,
            failed=0,
            active=0,
            phase="SUCCEEDED",
            start_time="2025-11-16T10:00:00Z",
            completion_time="2025-11-16T10:05:00Z"
        )
        
        snapshot = K8sMonitorSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs=[job_status],
            pods_logs=[],
            timestamp="2025-11-16T10:00:00Z"
        )
        
        text = generate_monitor_report_text(snapshot)
        
        assert "test-job" in text
        assert "SUCCEEDED" in text


class TestObservabilityPolicyD32:
    """D32 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_monitor_scripts(self):
        """모니터 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_monitor.py",
            "scripts/watch_k8s_jobs.py"
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


class TestReadOnlyBehavior:
    """Read-only 동작 테스트"""
    
    def test_monitor_only_uses_get_and_logs(self):
        """Monitor는 get과 logs만 사용"""
        monitor = K8sJobMonitor(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning"
        )
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"items": []}),
                stderr=""
            )
            
            # _load_jobs 호출
            monitor._load_jobs()
            
            # kubectl 명령 확인
            call_args = mock_run.call_args[0][0]
            
            # "get" 명령이어야 함
            assert "get" in call_args
            # "apply", "delete", "patch" 등이 없어야 함
            assert "apply" not in call_args
            assert "delete" not in call_args
            assert "patch" not in call_args
            assert "scale" not in call_args
    
    def test_no_destructive_operations(self):
        """파괴적 작업 없음"""
        monitor = K8sJobMonitor(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning"
        )
        
        # Monitor의 모든 공개 메서드 확인
        public_methods = [m for m in dir(monitor) if not m.startswith('_')]
        
        # 파괴적 메서드가 없어야 함
        destructive_methods = ['delete', 'remove', 'destroy', 'kill', 'scale', 'patch']
        
        for method in public_methods:
            for destructive in destructive_methods:
                assert destructive not in method.lower(), \
                    f"Found potentially destructive method: {method}"
