# -*- coding: utf-8 -*-
"""
D31 Safe Kubernetes Apply Layer Tests

K8s Job Apply 계획 및 실행 테스트.
"""

import pytest
import os
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from arbitrage.k8s_apply import (
    K8sApplyExecutor,
    K8sApplyPlanItem,
    K8sApplyPlan,
    K8sApplyJobResult,
    K8sApplyResult,
    K8sApplyError,
    generate_apply_report_text
)


class TestK8sApplyExecutor:
    """K8sApplyExecutor 테스트"""
    
    @pytest.fixture
    def executor_dry_run(self):
        """Dry-run 모드 Executor"""
        return K8sApplyExecutor(dry_run=True)
    
    @pytest.fixture
    def executor_apply(self):
        """Apply 모드 Executor"""
        return K8sApplyExecutor(dry_run=False)
    
    @pytest.fixture
    def sample_job_yaml(self):
        """샘플 K8s Job YAML"""
        return """
apiVersion: batch/v1
kind: Job
metadata:
  name: arb-tuning-test-worker-1-0
  namespace: trading-bots
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
      restartPolicy: Never
"""
    
    def test_executor_dry_run_creation(self, executor_dry_run):
        """Dry-run Executor 생성"""
        assert executor_dry_run is not None
        assert executor_dry_run.dry_run is True
    
    def test_executor_apply_creation(self, executor_apply):
        """Apply Executor 생성"""
        assert executor_apply is not None
        assert executor_apply.dry_run is False
    
    def test_executor_with_kubeconfig(self):
        """kubeconfig 지정"""
        executor = K8sApplyExecutor(
            dry_run=True,
            kubeconfig="/path/to/kubeconfig",
            context="my-cluster"
        )
        
        assert executor.kubeconfig == "/path/to/kubeconfig"
        assert executor.context == "my-cluster"
    
    def test_build_plan_nonexistent_directory(self, executor_dry_run):
        """존재하지 않는 디렉토리"""
        with pytest.raises(K8sApplyError):
            executor_dry_run.build_plan("/nonexistent/directory")
    
    def test_build_plan_empty_directory(self, executor_dry_run):
        """빈 디렉토리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(K8sApplyError):
                executor_dry_run.build_plan(tmpdir)
    
    def test_build_plan_with_valid_jobs(self, executor_dry_run, sample_job_yaml):
        """유효한 Job이 있는 디렉토리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 샘플 Job YAML 파일 생성
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            # 계획 생성
            plan = executor_dry_run.build_plan(tmpdir)
            
            assert plan.total_jobs == 1
            assert len(plan.jobs) == 1
            assert plan.jobs[0].job_name == "arb-tuning-test-worker-1-0"
            assert plan.jobs[0].namespace == "trading-bots"
    
    def test_build_plan_item_structure(self, executor_dry_run, sample_job_yaml):
        """Apply 계획 항목 구조"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor_dry_run.build_plan(tmpdir)
            plan_item = plan.jobs[0]
            
            assert isinstance(plan_item, K8sApplyPlanItem)
            assert plan_item.job_name == "arb-tuning-test-worker-1-0"
            assert plan_item.namespace == "trading-bots"
            assert plan_item.yaml_path == str(job_file)
            assert plan_item.kubectl_command[0] == "kubectl"
            assert plan_item.kubectl_command[1] == "apply"
    
    def test_execute_plan_dry_run(self, executor_dry_run, sample_job_yaml):
        """Dry-run 모드 실행"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor_dry_run.build_plan(tmpdir)
            result = executor_dry_run.execute_plan(plan)
            
            assert result.total_jobs == 1
            assert result.successful_jobs == 0
            assert result.failed_jobs == 0
            assert result.skipped_jobs == 1
            assert result.job_results[0].status == "SKIPPED"
    
    def test_execute_plan_dry_run_no_subprocess(self, executor_dry_run, sample_job_yaml):
        """Dry-run 모드에서 subprocess 호출 없음"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor_dry_run.build_plan(tmpdir)
            
            # subprocess.run이 호출되지 않도록 mock
            with patch('subprocess.run') as mock_run:
                result = executor_dry_run.execute_plan(plan)
                
                # subprocess.run이 호출되지 않았는지 확인
                mock_run.assert_not_called()
                
                # 결과는 SKIPPED
                assert result.job_results[0].status == "SKIPPED"
    
    def test_execute_plan_apply_mode_success(self, executor_apply, sample_job_yaml):
        """Apply 모드 성공"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor_apply.build_plan(tmpdir)
            
            # subprocess.run mock
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="job.batch/arb-tuning-test-worker-1-0 created",
                    stderr=""
                )
                
                result = executor_apply.execute_plan(plan)
                
                # subprocess.run이 호출되었는지 확인
                mock_run.assert_called_once()
                
                # 결과는 SUCCESS
                assert result.job_results[0].status == "SUCCESS"
                assert result.successful_jobs == 1
                assert result.failed_jobs == 0
    
    def test_execute_plan_apply_mode_failure(self, executor_apply, sample_job_yaml):
        """Apply 모드 실패"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor_apply.build_plan(tmpdir)
            
            # subprocess.run mock (실패)
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="Error: namespace not found"
                )
                
                result = executor_apply.execute_plan(plan)
                
                # 결과는 FAILED
                assert result.job_results[0].status == "FAILED"
                assert result.failed_jobs == 1
                assert result.successful_jobs == 0
    
    def test_execute_plan_with_kubeconfig(self, sample_job_yaml):
        """kubeconfig 옵션 포함"""
        executor = K8sApplyExecutor(
            dry_run=False,
            kubeconfig="/path/to/kubeconfig",
            context="my-cluster"
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(sample_job_yaml)
            
            plan = executor.build_plan(tmpdir)
            
            # kubectl 명령에 kubeconfig와 context 포함
            plan_item = plan.jobs[0]
            assert "--kubeconfig" in plan_item.kubectl_command
            assert "/path/to/kubeconfig" in plan_item.kubectl_command
            assert "--context" in plan_item.kubectl_command
            assert "my-cluster" in plan_item.kubectl_command
    
    def test_execute_plan_multiple_jobs(self, executor_dry_run, sample_job_yaml):
        """여러 Job 실행"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 여러 Job YAML 파일 생성
            for i in range(3):
                job_file = Path(tmpdir) / f"job-{i:02d}-test.yaml"
                with open(job_file, 'w', encoding='utf-8') as f:
                    f.write(sample_job_yaml)
            
            plan = executor_dry_run.build_plan(tmpdir)
            result = executor_dry_run.execute_plan(plan)
            
            assert result.total_jobs == 3
            assert result.skipped_jobs == 3
            assert len(result.job_results) == 3


class TestK8sApplyJobResult:
    """K8sApplyJobResult 테스트"""
    
    def test_job_result_creation(self):
        """Job 결과 생성"""
        result = K8sApplyJobResult(
            job_name="test-job",
            namespace="default",
            yaml_path="/path/to/job.yaml",
            command=["kubectl", "apply", "-f", "/path/to/job.yaml"],
            return_code=0,
            stdout="job created",
            stderr="",
            status="SUCCESS"
        )
        
        assert result.job_name == "test-job"
        assert result.status == "SUCCESS"
        assert result.return_code == 0


class TestK8sApplyResult:
    """K8sApplyResult 테스트"""
    
    def test_apply_result_creation(self):
        """Apply 결과 생성"""
        job_result = K8sApplyJobResult(
            job_name="test-job",
            namespace="default",
            yaml_path="/path/to/job.yaml",
            command=["kubectl", "apply", "-f", "/path/to/job.yaml"],
            return_code=0,
            stdout="job created",
            stderr="",
            status="SUCCESS"
        )
        
        result = K8sApplyResult(
            total_jobs=1,
            successful_jobs=1,
            failed_jobs=0,
            skipped_jobs=0,
            job_results=[job_result]
        )
        
        assert result.total_jobs == 1
        assert result.successful_jobs == 1


class TestApplyReportText:
    """Apply 보고서 텍스트 생성 테스트"""
    
    def test_generate_apply_report_text(self):
        """Apply 보고서 텍스트 생성"""
        job_result = K8sApplyJobResult(
            job_name="test-job",
            namespace="default",
            yaml_path="/path/to/job.yaml",
            command=["kubectl", "apply", "-f", "/path/to/job.yaml"],
            return_code=0,
            stdout="job created",
            stderr="",
            status="SUCCESS"
        )
        
        result = K8sApplyResult(
            total_jobs=1,
            successful_jobs=1,
            failed_jobs=0,
            skipped_jobs=0,
            job_results=[job_result]
        )
        
        text = generate_apply_report_text(result)
        
        assert "[D31_K8S_APPLY] KUBERNETES APPLY REPORT" in text
        assert "Total Jobs:" in text
        assert "Successful:" in text
        assert "test-job" in text


class TestObservabilityPolicyD31:
    """D31 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_apply_scripts(self):
        """Apply 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_apply.py",
            "scripts/apply_k8s_jobs.py"
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


class TestDefaultSafety:
    """기본 안전 모드 테스트"""
    
    def test_executor_default_dry_run(self):
        """기본값은 dry-run"""
        executor = K8sApplyExecutor()
        assert executor.dry_run is True
    
    def test_cli_default_dry_run(self):
        """CLI 기본값은 dry-run"""
        # CLI 스크립트에서 --apply 플래그가 없으면 dry-run
        # 이는 argparse에서 action="store_true"이므로 기본값은 False
        import subprocess
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 샘플 YAML 파일 생성
            job_yaml = """
apiVersion: batch/v1
kind: Job
metadata:
  name: test-job
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
      restartPolicy: Never
"""
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(job_yaml)
            
            # CLI 실행 (--apply 없음)
            result = subprocess.run(
                [
                    "python",
                    "scripts/apply_k8s_jobs.py",
                    "--jobs-dir", tmpdir
                ],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            
            # 출력에 "DRY-RUN" 또는 "SKIPPED"가 포함되어야 함
            assert "DRY-RUN" in result.stderr or "SKIPPED" in result.stdout
