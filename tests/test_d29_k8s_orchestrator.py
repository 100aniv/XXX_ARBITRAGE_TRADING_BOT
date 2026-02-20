# -*- coding: utf-8 -*-
"""
D29 Kubernetes Orchestrator Tests

K8s Job 생성 및 매니페스트 검증 테스트.
"""

import pytest
import os
import sys
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch

from arbitrage.k8s_orchestrator import (
    K8sJobSpec,
    K8sOrchestratorConfig,
    K8sTuningJobFactory,
    build_k8s_jobs_from_orchestrator
)


class TestK8sJobSpec:
    """K8sJobSpec 테스트"""
    
    def test_k8s_job_spec_creation(self):
        """K8sJobSpec 생성"""
        spec = K8sJobSpec(
            name="test-job",
            namespace="default",
            image="test:latest",
            command=["python"],
            args=["script.py"],
            env={"KEY": "value"},
            labels={"app": "test"},
            annotations={"desc": "test"}
        )
        
        assert spec.name == "test-job"
        assert spec.namespace == "default"
        assert spec.image == "test:latest"
    
    def test_k8s_job_spec_to_dict(self):
        """K8sJobSpec 딕셔너리 변환"""
        spec = K8sJobSpec(
            name="test-job",
            namespace="default",
            image="test:latest",
            command=["python"],
            args=["script.py"],
            env={"KEY": "value"},
            labels={"app": "test"},
            annotations={"desc": "test"}
        )
        
        spec_dict = spec.to_dict()
        
        assert spec_dict['name'] == "test-job"
        assert spec_dict['namespace'] == "default"
        assert isinstance(spec_dict['env'], dict)


class TestK8sOrchestratorConfig:
    """K8sOrchestratorConfig 테스트"""
    
    def test_k8s_orchestrator_config_creation(self):
        """K8sOrchestratorConfig 생성"""
        config = K8sOrchestratorConfig(
            session_id="session-123",
            k8s_namespace="trading-bots",
            image="arbitrage-lite:latest",
            mode="paper",
            env="docker",
            total_iterations=6,
            workers=2,
            optimizer="bayesian"
        )
        
        assert config.session_id == "session-123"
        assert config.k8s_namespace == "trading-bots"
        assert config.workers == 2


class TestK8sTuningJobFactory:
    """K8sTuningJobFactory 테스트"""
    
    @pytest.fixture
    def k8s_config(self):
        """K8s 설정"""
        return K8sOrchestratorConfig(
            session_id="d29-test-session",
            k8s_namespace="trading-bots",
            image="arbitrage-lite:latest",
            mode="paper",
            env="docker",
            total_iterations=6,
            workers=2,
            optimizer="bayesian"
        )
    
    def test_factory_creation(self, k8s_config):
        """Factory 생성"""
        factory = K8sTuningJobFactory(k8s_config)
        assert factory.config.session_id == "d29-test-session"
    
    def test_create_job_for_worker(self, k8s_config):
        """워커별 Job 생성"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        assert job.name.startswith("arb-tuning-")
        assert "worker-1" in job.name
        assert job.namespace == "trading-bots"
        assert job.image == "arbitrage-lite:latest"
    
    def test_job_name_pattern(self, k8s_config):
        """Job 이름 패턴"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        # 이름 형식: arb-tuning-{session_short}-{worker_id}-{index}
        assert job.name.startswith("arb-tuning-")
        assert "worker-1" in job.name
        assert "0" in job.name
    
    def test_job_labels(self, k8s_config):
        """Job 레이블"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        assert job.labels["app"] == "arbitrage-tuning"
        assert job.labels["session_id"] == "d29-test-session"
        assert job.labels["worker_id"] == "worker-1"
        assert job.labels["component"] == "tuning"
    
    def test_job_env_variables(self, k8s_config):
        """Job 환경 변수"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        assert job.env["APP_ENV"] == "docker"
        assert job.env["REDIS_HOST"] == "arbitrage-redis"
        assert job.env["SESSION_ID"] == "d29-test-session"
        assert job.env["WORKER_ID"] == "worker-1"
    
    def test_job_command_and_args(self, k8s_config):
        """Job 명령 및 인자"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        assert job.command == ["python"]
        assert "scripts/run_d24_tuning_session.py" in job.args
        assert "--iterations" in job.args
        assert "3" in job.args
        assert "--worker-id" in job.args
        assert "worker-1" in job.args
    
    def test_to_yaml_dict(self, k8s_config):
        """K8s YAML 딕셔너리 변환"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        yaml_dict = factory.to_yaml_dict(job)
        
        assert yaml_dict["apiVersion"] == "batch/v1"
        assert yaml_dict["kind"] == "Job"
        assert yaml_dict["metadata"]["name"] == job.name
        assert yaml_dict["metadata"]["namespace"] == "trading-bots"
        assert "spec" in yaml_dict
        assert "template" in yaml_dict["spec"]
    
    def test_yaml_dict_containers(self, k8s_config):
        """YAML 딕셔너리 컨테이너 구조"""
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        yaml_dict = factory.to_yaml_dict(job)
        
        containers = yaml_dict["spec"]["template"]["spec"]["containers"]
        assert len(containers) == 1
        assert containers[0]["image"] == "arbitrage-lite:latest"
        assert containers[0]["command"] == ["python"]
        assert len(containers[0]["env"]) > 0
    
    def test_yaml_dict_with_resources(self, k8s_config):
        """리소스 요청/제한 포함"""
        k8s_config.resources = {
            "requests": {"cpu": "500m", "memory": "512Mi"},
            "limits": {"cpu": "1", "memory": "1Gi"}
        }
        
        factory = K8sTuningJobFactory(k8s_config)
        job = factory.create_job_for_worker("worker-1", 3, 0)
        
        yaml_dict = factory.to_yaml_dict(job)
        
        containers = yaml_dict["spec"]["template"]["spec"]["containers"]
        assert "resources" in containers[0]
        assert "requests" in containers[0]["resources"]
        assert "limits" in containers[0]["resources"]


class TestBuildK8sJobsFromOrchestrator:
    """build_k8s_jobs_from_orchestrator 테스트"""
    
    def test_build_jobs_distribution(self):
        """Job 분배"""
        orch_config = {
            "total_iterations": 6,
            "workers": 2
        }
        
        k8s_config = K8sOrchestratorConfig(
            session_id="d29-test",
            k8s_namespace="trading-bots",
            image="arbitrage-lite:latest",
            mode="paper",
            env="docker",
            total_iterations=6,
            workers=2,
            optimizer="bayesian"
        )
        
        jobs = build_k8s_jobs_from_orchestrator(orch_config, k8s_config)
        
        assert len(jobs) == 2
        
        # 반복 수 합계
        total_iters = sum(
            int(job.args[job.args.index("--iterations") + 1])
            for job in jobs
        )
        assert total_iters == 6
    
    def test_build_jobs_worker_ids(self):
        """워커 ID"""
        orch_config = {
            "total_iterations": 6,
            "workers": 2
        }
        
        k8s_config = K8sOrchestratorConfig(
            session_id="d29-test",
            k8s_namespace="trading-bots",
            image="arbitrage-lite:latest",
            mode="paper",
            env="docker",
            total_iterations=6,
            workers=2,
            optimizer="bayesian"
        )
        
        jobs = build_k8s_jobs_from_orchestrator(orch_config, k8s_config)
        
        worker_ids = [job.labels["worker_id"] for job in jobs]
        assert "worker-1" in worker_ids
        assert "worker-2" in worker_ids


class TestK8sJobGeneratorCLI:
    """K8s Job Generator CLI 테스트"""
    
    def test_gen_k8s_jobs_script_execution(self):
        """gen_d29_k8s_jobs.py 실행"""
        import subprocess
        
        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "k8s_jobs"
            
            cmd = [
                sys.executable,
                "scripts/gen_d29_k8s_jobs.py",
                "--orchestrator-config", "configs/d28_orchestrator/demo_baseline.yaml",
                "--k8s-config", "configs/d29_k8s/orchestrator_k8s_baseline.yaml",
                "--output-dir", str(output_dir)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            
            # 성공 여부
            assert result.returncode == 0, f"stderr: {result.stderr}"
            
            # 파일 생성 확인
            assert output_dir.exists()
            yaml_files = list(output_dir.glob("*.yaml"))
            assert len(yaml_files) > 0
    
    def test_generated_yaml_structure(self):
        """생성된 YAML 구조"""
        import subprocess
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "k8s_jobs"
            
            cmd = [
                sys.executable,
                "scripts/gen_d29_k8s_jobs.py",
                "--orchestrator-config", "configs/d28_orchestrator/demo_baseline.yaml",
                "--k8s-config", "configs/d29_k8s/orchestrator_k8s_baseline.yaml",
                "--output-dir", str(output_dir)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            
            assert result.returncode == 0
            
            # 첫 번째 YAML 파일 로드
            yaml_files = sorted(output_dir.glob("*.yaml"))
            assert len(yaml_files) > 0
            
            with open(yaml_files[0], 'r', encoding='utf-8') as f:
                job_yaml = yaml.safe_load(f)
            
            # 기본 구조 검증
            assert job_yaml["apiVersion"] == "batch/v1"
            assert job_yaml["kind"] == "Job"
            assert "metadata" in job_yaml
            assert "spec" in job_yaml


class TestObservabilityPolicyD29:
    """D29 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_k8s_scripts(self):
        """K8s 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_orchestrator.py",
            "scripts/gen_d29_k8s_jobs.py"
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
