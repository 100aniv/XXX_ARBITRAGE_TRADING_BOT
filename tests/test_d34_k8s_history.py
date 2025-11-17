# -*- coding: utf-8 -*-
"""
D34 Kubernetes Events Collection & Health History Persistence Tests

K8s 이벤트 수집 및 건강 상태 히스토리 저장 테스트.
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

from arbitrage.k8s_events import (
    K8sEvent,
    K8sEventSnapshot,
    K8sEventCollector
)
from arbitrage.k8s_history import (
    K8sHealthHistoryRecord,
    K8sHealthHistoryStore
)
from arbitrage.k8s_health import (
    K8sHealthSnapshot,
    K8sJobHealth
)


class TestK8sEventCollector:
    """K8sEventCollector 테스트"""
    
    @pytest.fixture
    def collector(self):
        """이벤트 수집기"""
        return K8sEventCollector(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning,session_id=test-session"
        )
    
    def test_collector_creation(self, collector):
        """수집기 생성"""
        assert collector.namespace == "trading-bots"
        assert collector.label_selector == "app=arbitrage-tuning,session_id=test-session"
    
    def test_collector_with_kubeconfig(self):
        """kubeconfig 지정"""
        collector = K8sEventCollector(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning",
            kubeconfig="/path/to/kubeconfig",
            context="my-cluster"
        )
        
        assert collector.kubeconfig == "/path/to/kubeconfig"
        assert collector.context == "my-cluster"
    
    @patch('arbitrage.k8s_events.subprocess.run')
    def test_load_events_success(self, mock_run, collector):
        """이벤트 로드 성공"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "items": [
                    {
                        "type": "Normal",
                        "reason": "Scheduled",
                        "message": "Successfully assigned pod to node",
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "arb-tuning-worker-1-0",
                            "namespace": "trading-bots",
                            "labels": {"app": "arbitrage-tuning"}
                        },
                        "firstTimestamp": "2025-11-16T10:00:00Z",
                        "lastTimestamp": "2025-11-16T10:00:00Z",
                        "count": 1
                    }
                ]
            })
        )
        
        snapshot = collector.load_events()
        
        assert snapshot.namespace == "trading-bots"
        assert len(snapshot.events) == 1
        assert snapshot.events[0].type == "Normal"
        assert snapshot.events[0].reason == "Scheduled"
        assert len(snapshot.errors) == 0
    
    @patch('arbitrage.k8s_events.subprocess.run')
    def test_load_events_empty(self, mock_run, collector):
        """빈 이벤트 로드"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"items": []})
        )
        
        snapshot = collector.load_events()
        
        assert len(snapshot.events) == 0
        assert len(snapshot.errors) == 0
    
    @patch('arbitrage.k8s_events.subprocess.run')
    def test_load_events_kubectl_missing(self, mock_run, collector):
        """kubectl 없음"""
        mock_run.side_effect = FileNotFoundError("kubectl not found")
        
        snapshot = collector.load_events()
        
        assert len(snapshot.events) == 0
        assert len(snapshot.errors) == 1
        assert "kubectl not found" in snapshot.errors[0]
    
    @patch('arbitrage.k8s_events.subprocess.run')
    def test_load_events_json_error(self, mock_run, collector):
        """JSON 파싱 에러"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid json"
        )
        
        snapshot = collector.load_events()
        
        assert len(snapshot.events) == 0
        assert len(snapshot.errors) == 1
        assert "JSON decode error" in snapshot.errors[0]
    
    @patch('arbitrage.k8s_events.subprocess.run')
    def test_load_events_filtering_by_name(self, mock_run, collector):
        """이름으로 필터링"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "items": [
                    {
                        "type": "Normal",
                        "reason": "Scheduled",
                        "message": "Pod scheduled",
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "arb-tuning-worker-1-0",
                            "namespace": "trading-bots"
                        },
                        "firstTimestamp": "2025-11-16T10:00:00Z",
                        "lastTimestamp": "2025-11-16T10:00:00Z",
                        "count": 1
                    },
                    {
                        "type": "Normal",
                        "reason": "Created",
                        "message": "Pod created",
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "other-pod",
                            "namespace": "trading-bots"
                        },
                        "firstTimestamp": "2025-11-16T10:00:00Z",
                        "lastTimestamp": "2025-11-16T10:00:00Z",
                        "count": 1
                    }
                ]
            })
        )
        
        snapshot = collector.load_events()
        
        # arb-tuning- 접두사만 포함
        assert len(snapshot.events) == 1
        assert snapshot.events[0].involved_name == "arb-tuning-worker-1-0"


class TestK8sEvent:
    """K8sEvent 테스트"""
    
    def test_event_creation(self):
        """이벤트 생성"""
        event = K8sEvent(
            type="Warning",
            reason="BackoffLimitExceeded",
            message="Job has reached the specified backoff limit",
            involved_kind="Job",
            involved_name="test-job",
            involved_namespace="default",
            first_timestamp="2025-11-16T10:00:00Z",
            last_timestamp="2025-11-16T10:05:00Z",
            count=5,
            raw={}
        )
        
        assert event.type == "Warning"
        assert event.reason == "BackoffLimitExceeded"


class TestK8sEventSnapshot:
    """K8sEventSnapshot 테스트"""
    
    def test_snapshot_creation(self):
        """스냅샷 생성"""
        snapshot = K8sEventSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            events=[],
            timestamp="2025-11-16T10:00:00Z",
            errors=[]
        )
        
        assert snapshot.namespace == "trading-bots"
        assert len(snapshot.events) == 0


class TestK8sHealthHistoryStore:
    """K8sHealthHistoryStore 테스트"""
    
    @pytest.fixture
    def temp_file(self):
        """임시 파일"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name
        yield temp_path
        # 정리
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def store(self, temp_file):
        """히스토리 저장소"""
        return K8sHealthHistoryStore(temp_file)
    
    def test_store_creation(self, store):
        """저장소 생성"""
        assert store is not None
    
    def test_append_record(self, store):
        """레코드 추가"""
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[
                K8sJobHealth(
                    job_name="job-1",
                    namespace="trading-bots",
                    phase="SUCCEEDED",
                    succeeded=1,
                    failed=0,
                    active=0,
                    health="OK",
                    reasons=[],
                    labels={}
                )
            ],
            errors=[],
            overall_health="OK",
            timestamp="2025-11-16T10:00:00Z"
        )
        
        record = store.append(snapshot)
        
        assert record.namespace == "trading-bots"
        assert record.overall_health == "OK"
        assert record.jobs_ok == 1
        assert record.jobs_warn == 0
        assert record.jobs_error == 0
    
    def test_append_multiple_records(self, store):
        """여러 레코드 추가"""
        for i in range(3):
            snapshot = K8sHealthSnapshot(
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                jobs_health=[],
                errors=[],
                overall_health="OK",
                timestamp=f"2025-11-16T10:0{i}:00Z"
            )
            store.append(snapshot)
        
        records = store.load_recent(limit=10)
        assert len(records) == 3
    
    def test_load_recent_empty(self, store):
        """빈 히스토리 로드"""
        records = store.load_recent(limit=10)
        assert len(records) == 0
    
    def test_load_recent_limit(self, store):
        """최근 N개 로드"""
        for i in range(10):
            snapshot = K8sHealthSnapshot(
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                jobs_health=[],
                errors=[],
                overall_health="OK",
                timestamp=f"2025-11-16T10:{i:02d}:00Z"
            )
            store.append(snapshot)
        
        records = store.load_recent(limit=5)
        assert len(records) == 5
    
    def test_load_recent_corrupted_line(self, store, temp_file):
        """손상된 라인 스킵"""
        # 정상 레코드 추가
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[],
            errors=[],
            overall_health="OK",
            timestamp="2025-11-16T10:00:00Z"
        )
        store.append(snapshot)
        
        # 손상된 라인 추가
        with open(temp_file, 'a') as f:
            f.write("invalid json line\n")
        
        # 정상 레코드 추가
        store.append(snapshot)
        
        records = store.load_recent(limit=10)
        # 손상된 라인은 스킵되고 정상 레코드 2개만 로드
        assert len(records) == 2
    
    def test_summarize_empty(self, store):
        """빈 요약"""
        summary = store.summarize()
        
        assert summary["total_records"] == 0
        assert summary["ok_count"] == 0
        assert summary["last_overall_health"] is None
    
    def test_summarize_with_records(self, store):
        """레코드가 있는 요약"""
        # OK 레코드 2개
        for i in range(2):
            snapshot = K8sHealthSnapshot(
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                jobs_health=[],
                errors=[],
                overall_health="OK",
                timestamp=f"2025-11-16T10:0{i}:00Z"
            )
            store.append(snapshot)
        
        # WARN 레코드 1개
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=[],
            errors=["some error"],
            overall_health="WARN",
            timestamp="2025-11-16T10:02:00Z"
        )
        store.append(snapshot)
        
        summary = store.summarize()
        
        assert summary["total_records"] == 3
        assert summary["ok_count"] == 2
        assert summary["warn_count"] == 1
        assert summary["error_count"] == 0
        assert summary["last_overall_health"] == "WARN"
    
    def test_summarize_window(self, store):
        """윈도우 기반 요약"""
        # 5개 레코드 추가
        for i in range(5):
            snapshot = K8sHealthSnapshot(
                namespace="trading-bots",
                selector="app=arbitrage-tuning",
                jobs_health=[],
                errors=[],
                overall_health="OK",
                timestamp=f"2025-11-16T10:{i:02d}:00Z"
            )
            store.append(snapshot)
        
        # 최근 2개만 요약
        summary = store.summarize(window=2)
        
        assert summary["total_records"] == 2
    
    def test_record_counts_mixed_health(self, store):
        """혼합 건강 상태 카운트"""
        jobs_health = [
            K8sJobHealth(
                job_name="job-ok-1",
                namespace="trading-bots",
                phase="SUCCEEDED",
                succeeded=1,
                failed=0,
                active=0,
                health="OK",
                reasons=[],
                labels={}
            ),
            K8sJobHealth(
                job_name="job-ok-2",
                namespace="trading-bots",
                phase="RUNNING",
                succeeded=0,
                failed=0,
                active=1,
                health="OK",
                reasons=[],
                labels={}
            ),
            K8sJobHealth(
                job_name="job-warn",
                namespace="trading-bots",
                phase="PENDING",
                succeeded=0,
                failed=0,
                active=0,
                health="WARN",
                reasons=["pending"],
                labels={}
            ),
            K8sJobHealth(
                job_name="job-error",
                namespace="trading-bots",
                phase="FAILED",
                succeeded=0,
                failed=1,
                active=0,
                health="ERROR",
                reasons=["job_failed"],
                labels={}
            )
        ]
        
        snapshot = K8sHealthSnapshot(
            namespace="trading-bots",
            selector="app=arbitrage-tuning",
            jobs_health=jobs_health,
            errors=[],
            overall_health="ERROR",
            timestamp="2025-11-16T10:00:00Z"
        )
        
        record = store.append(snapshot)
        
        assert record.jobs_ok == 2
        assert record.jobs_warn == 1
        assert record.jobs_error == 1


class TestObservabilityPolicyD34:
    """D34 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_d34_scripts(self):
        """D34 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_events.py",
            "arbitrage/k8s_history.py",
            "scripts/record_k8s_health.py",
            "scripts/show_k8s_health_history.py"
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


class TestReadOnlyBehaviorD34:
    """D34 Read-only 동작 테스트"""
    
    def test_event_collector_no_modifications(self):
        """이벤트 수집기는 수정 작업 없음"""
        collector = K8sEventCollector(
            namespace="trading-bots",
            label_selector="app=arbitrage-tuning"
        )
        
        # 공개 메서드 확인
        public_methods = [m for m in dir(collector) if not m.startswith('_')]
        
        # 파괴적 메서드가 없어야 함
        destructive_methods = ['delete', 'remove', 'destroy', 'kill', 'scale', 'patch', 'apply']
        
        for method in public_methods:
            for destructive in destructive_methods:
                assert destructive not in method.lower(), \
                    f"Found potentially destructive method: {method}"
    
    def test_history_store_no_modifications(self):
        """히스토리 저장소는 수정 작업 없음"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name
        
        try:
            store = K8sHealthHistoryStore(temp_path)
            
            # 공개 메서드 확인
            public_methods = [m for m in dir(store) if not m.startswith('_')]
            
            # 파괴적 메서드가 없어야 함
            destructive_methods = ['delete', 'remove', 'destroy', 'kill', 'scale', 'patch', 'apply']
            
            for method in public_methods:
                for destructive in destructive_methods:
                    assert destructive not in method.lower(), \
                        f"Found potentially destructive method: {method}"
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestCLIIntegration:
    """CLI 통합 테스트"""
    
    @patch('scripts.record_k8s_health.K8sJobMonitor')
    @patch('scripts.record_k8s_health.K8sHealthEvaluator')
    @patch('scripts.record_k8s_health.K8sHealthHistoryStore')
    def test_record_k8s_health_exit_code_ok(self, mock_store_class, mock_eval_class, mock_monitor_class):
        """record_k8s_health.py 종료 코드: OK"""
        from scripts.record_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("OK", strict=False) == 0
        assert _determine_exit_code("OK", strict=True) == 0
    
    @patch('scripts.record_k8s_health.K8sJobMonitor')
    @patch('scripts.record_k8s_health.K8sHealthEvaluator')
    @patch('scripts.record_k8s_health.K8sHealthHistoryStore')
    def test_record_k8s_health_exit_code_warn(self, mock_store_class, mock_eval_class, mock_monitor_class):
        """record_k8s_health.py 종료 코드: WARN"""
        from scripts.record_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("WARN", strict=False) == 0
        assert _determine_exit_code("WARN", strict=True) == 1
    
    @patch('scripts.record_k8s_health.K8sJobMonitor')
    @patch('scripts.record_k8s_health.K8sHealthEvaluator')
    @patch('scripts.record_k8s_health.K8sHealthHistoryStore')
    def test_record_k8s_health_exit_code_error(self, mock_store_class, mock_eval_class, mock_monitor_class):
        """record_k8s_health.py 종료 코드: ERROR"""
        from scripts.record_k8s_health import _determine_exit_code
        
        assert _determine_exit_code("ERROR", strict=False) == 2
        assert _determine_exit_code("ERROR", strict=True) == 2
