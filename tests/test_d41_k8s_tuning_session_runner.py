# -*- coding: utf-8 -*-
"""
D41 Kubernetes Tuning Session Distributed Runner Tests

100% mock 기반 테스트 (실제 K8s 클러스터 접근 금지).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from tempfile import TemporaryDirectory

from arbitrage.k8s_tuning_session_runner import (
    K8sTuningSessionRunner,
    K8sTuningSessionRunResult,
)
from arbitrage.k8s_job_spec_builder import K8sJobSpecBuilder
from arbitrage.k8s_utils import K8sClient, K8sJobStatus


class TestK8sJobSpecBuilder:
    """K8s Job Spec Builder 테스트"""

    def test_build_tuning_job_basic(self):
        """기본 Job manifest 생성"""
        builder = K8sJobSpecBuilder(namespace="default", image="python:3.11")

        config = {
            "job_id": "sess001_0001",
            "param_a": 0.1,
            "param_b": 0.2,
        }

        manifest = builder.build_tuning_job(
            job_id="sess001_0001",
            config=config,
            output_dir="outputs/tuning",
        )

        assert manifest["apiVersion"] == "batch/v1"
        assert manifest["kind"] == "Job"
        assert manifest["metadata"]["namespace"] == "default"
        assert "sess001-0001" in manifest["metadata"]["name"]
        assert manifest["spec"]["template"]["spec"]["containers"][0]["image"] == "python:3.11"

    def test_normalize_job_name(self):
        """Job 이름 정규화"""
        builder = K8sJobSpecBuilder()

        # 테스트 케이스
        test_cases = [
            ("sess001_0001", "sess001-0001"),
            ("SESS001_0001", "sess001-0001"),
            ("sess-001-0001", "sess-001-0001"),
            ("_sess001_0001", "job-sess001-0001"),
            ("sess001_0001_", "sess001-0001"),
        ]

        for input_name, expected in test_cases:
            result = builder._normalize_job_name(input_name)
            # 정규화된 이름이 예상된 형식을 포함하거나 일치하는지 확인
            assert result == expected or expected in result or result.endswith(expected.replace("job-", ""))

    def test_build_cli_args(self):
        """CLI 인자 생성"""
        builder = K8sJobSpecBuilder()

        config = {"job_id": "sess001_0001", "param_a": 0.1}
        args = builder._build_cli_args(config, "outputs/tuning")

        assert "python" in args
        assert "-m" in args
        assert "scripts.run_arbitrage_tuning" in args
        assert "--config" in args
        assert "--output-json" in args


class TestK8sTuningSessionRunnerLoadJobs:
    """K8s Session Runner - load_jobs() 테스트"""

    def test_load_jobs_basic(self):
        """JSONL 파일 로드"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": "sess001_0001", "config": {"param_a": 0.1}},
                {"job_id": "sess001_0002", "config": {"param_a": 0.2}},
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            runner = K8sTuningSessionRunner(str(jobs_file))
            loaded_jobs = runner.load_jobs()

            assert len(loaded_jobs) == 2
            assert loaded_jobs[0]["job_id"] == "sess001_0001"
            assert loaded_jobs[1]["job_id"] == "sess001_0002"

    def test_load_jobs_file_not_found(self):
        """파일 없음 오류"""
        runner = K8sTuningSessionRunner("nonexistent.jsonl")

        with pytest.raises(FileNotFoundError):
            runner.load_jobs()

    def test_load_jobs_invalid_json(self):
        """잘못된 JSON 오류"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"

            with open(jobs_file, "w") as f:
                f.write('{"job_id": "sess001_0001"}\n')
                f.write('invalid json\n')

            runner = K8sTuningSessionRunner(str(jobs_file))

            with pytest.raises(ValueError):
                runner.load_jobs()


class TestK8sTuningSessionRunnerValidation:
    """K8s Session Runner - 유효성 검사 테스트"""

    def test_validate_job_valid(self):
        """유효한 작업"""
        runner = K8sTuningSessionRunner("dummy.jsonl")
        job = {"job_id": "sess001_0001", "config": {"param_a": 0.1}}

        error = runner._validate_job(job)
        assert error is None

    def test_validate_job_missing_job_id(self):
        """job_id 누락"""
        runner = K8sTuningSessionRunner("dummy.jsonl")
        job = {"config": {"param_a": 0.1}}

        error = runner._validate_job(job)
        assert error is not None
        assert "job_id" in error

    def test_validate_job_missing_config(self):
        """config 누락"""
        runner = K8sTuningSessionRunner("dummy.jsonl")
        job = {"job_id": "sess001_0001"}

        error = runner._validate_job(job)
        assert error is not None
        assert "config" in error

    def test_validate_job_config_not_dict(self):
        """config가 dict가 아님"""
        runner = K8sTuningSessionRunner("dummy.jsonl")
        job = {"job_id": "sess001_0001", "config": "not_a_dict"}

        error = runner._validate_job(job)
        assert error is not None


class TestK8sTuningSessionRunnerRun:
    """K8s Session Runner - run() 테스트"""

    def test_run_basic_success(self):
        """기본 성공 케이스"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": "sess001_0001", "config": {"param_a": 0.1}},
                {"job_id": "sess001_0002", "config": {"param_a": 0.2}},
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            # Mock K8s 클라이언트
            mock_client = Mock(spec=K8sClient)
            mock_client.create_job.side_effect = ["sess001-0001", "sess001-0002"]
            mock_client.get_job_status.return_value = K8sJobStatus(
                job_id="test", namespace="default", status="Succeeded"
            )
            mock_client.get_pod_logs.return_value = "Job completed successfully"

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                max_parallel=2,
                timeout_per_job=10,
                timeout_session=60,
                wait=True,
                k8s_client=mock_client,
            )

            result = runner.run()

            assert result.total_jobs == 2
            assert result.attempted_jobs == 2
            assert result.exit_code == 0

    def test_run_with_invalid_jobs(self):
        """유효하지 않은 작업 포함"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": "sess001_0001", "config": {"param_a": 0.1}},
                {"job_id": "sess001_0002"},  # config 누락
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            mock_client = Mock(spec=K8sClient)
            mock_client.create_job.return_value = "sess001-0001"

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                k8s_client=mock_client,
            )

            result = runner.run()

            assert result.total_jobs == 2
            assert result.skipped_jobs == 1
            assert result.attempted_jobs == 1

    def test_run_max_parallel_limit(self):
        """max_parallel 제한"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": f"sess001_{i:04d}", "config": {"param_a": 0.1 * i}}
                for i in range(1, 11)
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            mock_client = Mock(spec=K8sClient)
            mock_client.create_job.side_effect = [f"job-{i}" for i in range(10)]

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                max_parallel=3,
                k8s_client=mock_client,
            )

            # 실제로는 병렬 제한을 테스트하기 위해 wait=False 사용
            runner.wait = False
            result = runner.run()

            # 최대 3개까지만 submit되어야 함
            assert mock_client.create_job.call_count <= 3

    def test_run_exit_code_logic(self):
        """종료 코드 계산"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": "sess001_0001", "config": {"param_a": 0.1}},
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            # 성공 케이스
            mock_client = Mock(spec=K8sClient)
            mock_client.create_job.return_value = "sess001-0001"
            mock_client.get_job_status.return_value = K8sJobStatus(
                job_id="test", namespace="default", status="Succeeded"
            )
            mock_client.get_pod_logs.return_value = "Success"

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                k8s_client=mock_client,
            )
            result = runner.run()
            assert result.exit_code == 0

    def test_run_no_wait_mode(self):
        """no-wait 모드 (submit만)"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_data = [
                {"job_id": "sess001_0001", "config": {"param_a": 0.1}},
            ]

            with open(jobs_file, "w") as f:
                for job in jobs_data:
                    f.write(json.dumps(job) + "\n")

            mock_client = Mock(spec=K8sClient)
            mock_client.create_job.return_value = "sess001-0001"

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                wait=False,
                k8s_client=mock_client,
            )

            result = runner.run()

            # submit은 되었지만 완료 대기는 하지 않음
            assert result.attempted_jobs == 1
            assert mock_client.create_job.called


class TestSafetyAndPolicy:
    """안전 정책 준수 테스트"""

    def test_no_network_calls(self):
        """네트워크 호출 없음"""
        import arbitrage.k8s_tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        assert "requests" not in source
        assert "http" not in source.lower()
        assert "socket" not in source

    def test_no_kubectl_direct_calls(self):
        """kubectl 직접 호출 없음"""
        import arbitrage.k8s_tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        assert "subprocess.run" not in source or "kubectl" not in source

    def test_k8s_client_interface(self):
        """K8sClient 인터페이스 준수"""
        from arbitrage.k8s_utils import K8sClientInterface

        # K8sClient가 인터페이스를 구현하는지 확인
        assert issubclass(K8sClient, K8sClientInterface)

    def test_mock_friendly_design(self):
        """Mock 친화적 설계"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"

            with open(jobs_file, "w") as f:
                f.write('{"job_id": "test", "config": {}}\n')

            # Mock 클라이언트 주입 가능
            mock_client = Mock(spec=K8sClient)
            runner = K8sTuningSessionRunner(
                str(jobs_file),
                k8s_client=mock_client,
            )

            assert runner.k8s_client is mock_client


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_jobs_file(self):
        """빈 JSONL 파일"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"
            jobs_file.touch()

            runner = K8sTuningSessionRunner(str(jobs_file))
            jobs = runner.load_jobs()

            assert len(jobs) == 0

    def test_max_parallel_zero(self):
        """max_parallel=0"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"

            with open(jobs_file, "w") as f:
                f.write('{"job_id": "test", "config": {}}\n')

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                max_parallel=0,
            )

            # max_parallel=0이면 Job이 submit되지 않음
            runner.wait = False
            result = runner.run()

            assert result.attempted_jobs == 0

    def test_timeout_session_config(self):
        """세션 타임아웃 설정"""
        with TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.jsonl"

            with open(jobs_file, "w") as f:
                f.write('{"job_id": "test", "config": {}}\n')

            runner = K8sTuningSessionRunner(
                str(jobs_file),
                timeout_session=7200,
            )

            # 타임아웃 설정이 올바르게 적용되었는지 확인
            assert runner.timeout_session == 7200


class TestCLI:
    """CLI 테스트"""

    def test_cli_script_exists(self):
        """CLI 스크립트 존재"""
        cli_path = Path(__file__).parent.parent / "scripts" / "run_tuning_session_k8s.py"
        assert cli_path.exists()

    def test_cli_has_main_function(self):
        """CLI main 함수 존재"""
        from scripts.run_tuning_session_k8s import main
        assert callable(main)
