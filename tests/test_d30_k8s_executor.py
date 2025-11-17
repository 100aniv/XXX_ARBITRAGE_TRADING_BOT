# -*- coding: utf-8 -*-
"""
D30 Kubernetes Executor Tests

K8s Job 검증 및 실행 계획 생성 테스트.
"""

import pytest
import os
import yaml
import tempfile
from pathlib import Path

from arbitrage.k8s_executor import (
    K8sJobValidator,
    K8sExecutionPlanner,
    K8sValidationError,
    K8sJobValidation,
    generate_execution_plan_text
)


class TestK8sJobValidator:
    """K8sJobValidator 테스트"""
    
    @pytest.fixture
    def validator(self):
        """Validator 인스턴스"""
        return K8sJobValidator(strict_mode=False)
    
    @pytest.fixture
    def valid_job_yaml(self):
        """유효한 K8s Job YAML"""
        return """
apiVersion: batch/v1
kind: Job
metadata:
  name: arb-tuning-test-worker-1-0
  namespace: trading-bots
  labels:
    app: arbitrage-tuning
    session_id: test-session
    worker_id: worker-1
    component: tuning
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app: arbitrage-tuning
    spec:
      containers:
      - name: tuning-job
        image: arbitrage-lite:latest
        command:
        - python
        args:
        - scripts/run_d24_tuning_session.py
        env:
        - name: SESSION_ID
          value: test-session
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
      restartPolicy: Never
"""
    
    def test_validator_creation(self, validator):
        """Validator 생성"""
        assert validator is not None
        assert validator.strict_mode is False
    
    def test_validator_strict_mode(self):
        """엄격한 모드"""
        validator = K8sJobValidator(strict_mode=True)
        assert validator.strict_mode is True
    
    def test_validate_valid_job(self, validator, valid_job_yaml):
        """유효한 Job 검증"""
        validation = validator.validate_job_yaml(valid_job_yaml, "test-job.yaml")
        
        assert validation.valid is True
        assert validation.job_name == "arb-tuning-test-worker-1-0"
        assert validation.namespace == "trading-bots"
        assert len(validation.errors) == 0
    
    def test_validate_invalid_yaml(self, validator):
        """잘못된 YAML 검증"""
        invalid_yaml = "invalid: yaml: content: ["
        
        validation = validator.validate_job_yaml(invalid_yaml, "invalid.yaml")
        
        assert validation.valid is False
        assert len(validation.errors) > 0
    
    def test_validate_empty_yaml(self, validator):
        """빈 YAML 검증"""
        empty_yaml = ""
        
        validation = validator.validate_job_yaml(empty_yaml, "empty.yaml")
        
        assert validation.valid is False
        assert len(validation.errors) > 0
    
    def test_validate_missing_apiversion(self, validator):
        """apiVersion 누락"""
        yaml_content = """
kind: Job
metadata:
  name: test-job
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        assert validation.valid is False
        assert any("apiVersion" in e for e in validation.errors)
    
    def test_validate_missing_kind(self, validator):
        """kind 누락"""
        yaml_content = """
apiVersion: batch/v1
metadata:
  name: test-job
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        assert validation.valid is False
        assert any("kind" in e for e in validation.errors)
    
    def test_validate_missing_metadata(self, validator):
        """metadata 누락"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        assert validation.valid is False
        assert any("metadata" in e for e in validation.errors)
    
    def test_validate_missing_spec(self, validator):
        """spec 누락"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
metadata:
  name: test-job
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        assert validation.valid is False
        assert any("spec" in e for e in validation.errors)
    
    def test_validate_missing_containers(self, validator):
        """containers 누락"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
metadata:
  name: test-job
spec:
  template:
    spec:
      restartPolicy: Never
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        assert validation.valid is False
        assert any("containers" in e for e in validation.errors)
    
    def test_validate_invalid_image(self, validator):
        """이미지 형식 검증"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
metadata:
  name: test-job
spec:
  template:
    spec:
      containers:
      - name: test
        image: invalid-image-no-tag
      restartPolicy: Never
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        # 경고는 있지만 유효함
        assert any("tag" in w.lower() for w in validation.warnings)
    
    def test_validate_job_name_pattern(self, validator):
        """Job 이름 패턴 검증"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
metadata:
  name: invalid-job-name
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
      restartPolicy: Never
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        # 경고는 있지만 유효함
        assert any("규칙" in w for w in validation.warnings)
    
    def test_validate_missing_resources(self, validator):
        """리소스 미설정 검증"""
        yaml_content = """
apiVersion: batch/v1
kind: Job
metadata:
  name: arb-tuning-test-job
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
      restartPolicy: Never
"""
        validation = validator.validate_job_yaml(yaml_content)
        
        # 경고는 있지만 유효함
        assert any("resources" in w for w in validation.warnings)


class TestK8sExecutionPlanner:
    """K8sExecutionPlanner 테스트"""
    
    @pytest.fixture
    def planner(self):
        """Planner 인스턴스"""
        validator = K8sJobValidator(strict_mode=False)
        return K8sExecutionPlanner(validator)
    
    def test_planner_creation(self, planner):
        """Planner 생성"""
        assert planner is not None
    
    def test_plan_from_nonexistent_directory(self, planner):
        """존재하지 않는 디렉토리"""
        plan = planner.plan_from_directory("/nonexistent/directory")
        
        assert plan.total_jobs == 0
        assert plan.valid_jobs == 0
        assert len(plan.errors) > 0
    
    def test_plan_from_empty_directory(self, planner):
        """빈 디렉토리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = planner.plan_from_directory(tmpdir)
            
            assert plan.total_jobs == 0
            assert plan.valid_jobs == 0
            assert len(plan.errors) > 0
    
    def test_plan_from_directory_with_valid_jobs(self, planner):
        """유효한 Job이 있는 디렉토리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 유효한 Job YAML 파일 생성
            job_yaml = """
apiVersion: batch/v1
kind: Job
metadata:
  name: arb-tuning-test-worker-1-0
  namespace: trading-bots
  labels:
    app: arbitrage-tuning
    session_id: test-session
    worker_id: worker-1
    component: tuning
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app: arbitrage-tuning
    spec:
      containers:
      - name: tuning-job
        image: arbitrage-lite:latest
        command:
        - python
        args:
        - scripts/run_d24_tuning_session.py
        env:
        - name: SESSION_ID
          value: test-session
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
      restartPolicy: Never
"""
            
            # 파일 저장
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(job_yaml)
            
            # 계획 생성
            plan = planner.plan_from_directory(tmpdir)
            
            assert plan.total_jobs == 1
            assert plan.valid_jobs == 1
            assert plan.invalid_jobs == 0
            assert len(plan.errors) == 0
    
    def test_plan_summary_structure(self, planner):
        """계획 요약 구조"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_yaml = """
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
            
            job_file = Path(tmpdir) / "job-00-test.yaml"
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(job_yaml)
            
            plan = planner.plan_from_directory(tmpdir)
            
            assert "total_jobs" in plan.summary
            assert "valid_jobs" in plan.summary
            assert "invalid_jobs" in plan.summary
            assert "job_names" in plan.summary
            assert "namespaces" in plan.summary


class TestExecutionPlanText:
    """실행 계획 텍스트 생성 테스트"""
    
    def test_generate_execution_plan_text(self):
        """실행 계획 텍스트 생성"""
        from arbitrage.k8s_executor import K8sExecutionPlan
        
        plan = K8sExecutionPlan(
            total_jobs=2,
            valid_jobs=2,
            invalid_jobs=0,
            jobs=[],
            errors=[],
            warnings=[],
            summary={
                "total_jobs": 2,
                "valid_jobs": 2,
                "invalid_jobs": 0,
                "job_names": ["job-1", "job-2"],
                "namespaces": ["trading-bots"],
                "invalid_job_names": []
            }
        )
        
        text = generate_execution_plan_text(plan)
        
        assert "[D30_K8S_EXEC] KUBERNETES EXECUTION PLAN" in text
        assert "Total Jobs:" in text
        assert "Valid Jobs:" in text
        assert "2" in text


class TestObservabilityPolicyD30:
    """D30 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_executor_scripts(self):
        """Executor 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/k8s_executor.py",
            "scripts/validate_k8s_jobs.py"
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
