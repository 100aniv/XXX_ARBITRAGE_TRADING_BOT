"""
D40: Tuning Session Local Runner Tests

Tests for:
- TuningSessionRunner.load_jobs()
- TuningSessionRunner.run()
- CLI integration
- Safety and policy compliance
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from arbitrage.tuning_session_runner import (
    TuningSessionRunner,
    TuningSessionRunResult,
)


class TestTuningSessionRunnerLoadJobs:
    """Tests for TuningSessionRunner.load_jobs()"""

    def test_load_jobs_single_job(self, tmp_path):
        """로더가 단일 작업을 로드할 수 있다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {
                "data_file": "data/sample.csv",
                "min_spread_bps": 30.0,
                "taker_fee_a_bps": 5.0,
                "taker_fee_b_bps": 5.0,
                "slippage_bps": 5.0,
                "max_position_usd": 1000.0,
            },
            "output_json": "outputs/job_0001.json",
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))
        jobs = runner.load_jobs()

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job_0001"

    def test_load_jobs_multiple_jobs(self, tmp_path):
        """로더가 여러 작업을 로드할 수 있다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": "job_0001",
                "config": {"data_file": "data/sample.csv", "min_spread_bps": 30.0},
                "output_json": "outputs/job_0001.json",
            },
            {
                "job_id": "job_0002",
                "config": {"data_file": "data/sample.csv", "min_spread_bps": 40.0},
                "output_json": "outputs/job_0002.json",
            },
            {
                "job_id": "job_0003",
                "config": {"data_file": "data/sample.csv", "min_spread_bps": 50.0},
                "output_json": "outputs/job_0003.json",
            },
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))
        jobs = runner.load_jobs()

        assert len(jobs) == 3
        assert jobs[0]["job_id"] == "job_0001"
        assert jobs[1]["job_id"] == "job_0002"
        assert jobs[2]["job_id"] == "job_0003"

    def test_load_jobs_file_not_found(self):
        """파일이 없으면 FileNotFoundError를 발생시킨다."""
        runner = TuningSessionRunner("/nonexistent/jobs.jsonl")
        with pytest.raises(FileNotFoundError):
            runner.load_jobs()

    def test_load_jobs_empty_file(self, tmp_path):
        """빈 파일은 ValueError를 발생시킨다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_file.write_text("")

        runner = TuningSessionRunner(str(jobs_file))
        with pytest.raises(ValueError, match="empty"):
            runner.load_jobs()

    def test_load_jobs_invalid_json(self, tmp_path):
        """잘못된 JSON은 ValueError를 발생시킨다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_file.write_text("{ invalid json }\n")

        runner = TuningSessionRunner(str(jobs_file))
        with pytest.raises(ValueError, match="Invalid JSON"):
            runner.load_jobs()

    def test_load_jobs_skip_empty_lines(self, tmp_path):
        """빈 줄을 건너뛴다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": "outputs/job_0001.json",
        }
        content = json.dumps(job) + "\n\n" + json.dumps(job) + "\n"
        jobs_file.write_text(content)

        runner = TuningSessionRunner(str(jobs_file))
        jobs = runner.load_jobs()

        assert len(jobs) == 2


class TestTuningSessionRunnerValidation:
    """Tests for TuningSessionRunner job validation"""

    def test_validate_job_valid(self, tmp_path):
        """유효한 작업은 검증을 통과한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": "outputs/job_0001.json",
        }
        assert runner._validate_job(job) is None

    def test_validate_job_missing_job_id(self, tmp_path):
        """job_id가 없으면 오류를 반환한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        job = {
            "config": {"data_file": "data/sample.csv"},
            "output_json": "outputs/job_0001.json",
        }
        assert runner._validate_job(job) is not None

    def test_validate_job_missing_config(self, tmp_path):
        """config가 없으면 오류를 반환한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        job = {
            "job_id": "job_0001",
            "output_json": "outputs/job_0001.json",
        }
        assert runner._validate_job(job) is not None

    def test_validate_job_missing_output_json(self, tmp_path):
        """output_json이 없으면 오류를 반환한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
        }
        assert runner._validate_job(job) is not None

    def test_validate_job_missing_data_file(self, tmp_path):
        """data_file이 없으면 오류를 반환한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        job = {
            "job_id": "job_0001",
            "config": {},
            "output_json": "outputs/job_0001.json",
        }
        assert runner._validate_job(job) is not None


class TestTuningSessionRunnerRun:
    """Tests for TuningSessionRunner.run()"""

    def test_run_single_job_success(self, tmp_path):
        """단일 작업이 성공하면 exit_code=0을 반환한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {
                "data_file": "data/sample.csv",
                "min_spread_bps": 30.0,
                "taker_fee_a_bps": 5.0,
                "taker_fee_b_bps": 5.0,
                "slippage_bps": 5.0,
                "max_position_usd": 1000.0,
            },
            "output_json": str(tmp_path / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        assert result.total_jobs == 1
        assert result.attempted_jobs == 1
        assert result.success_jobs == 1
        assert result.error_jobs == 0
        assert result.skipped_jobs == 0
        assert result.exit_code == 0

    def test_run_multiple_jobs_all_success(self, tmp_path):
        """모든 작업이 성공하면 exit_code=0을 반환한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": f"job_{i:04d}",
                "config": {"data_file": "data/sample.csv", "min_spread_bps": 30.0},
                "output_json": str(tmp_path / f"job_{i:04d}.json"),
            }
            for i in range(1, 4)
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        assert result.total_jobs == 3
        assert result.attempted_jobs == 3
        assert result.success_jobs == 3
        assert result.error_jobs == 0
        assert result.exit_code == 0

    def test_run_job_failure(self, tmp_path):
        """작업이 실패하면 exit_code=1을 반환한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": str(tmp_path / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Error")
            result = runner.run()

        assert result.total_jobs == 1
        assert result.attempted_jobs == 1
        assert result.success_jobs == 0
        assert result.error_jobs == 1
        assert result.exit_code == 1

    def test_run_max_jobs_limit(self, tmp_path):
        """max_jobs 제한을 준수한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": f"job_{i:04d}",
                "config": {"data_file": "data/sample.csv"},
                "output_json": str(tmp_path / f"job_{i:04d}.json"),
            }
            for i in range(1, 6)
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file), max_jobs=3)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        assert result.total_jobs == 5
        assert result.attempted_jobs == 3
        assert result.skipped_jobs == 2

    def test_run_stop_on_error_true(self, tmp_path):
        """stop_on_error=True이면 첫 오류에서 중단한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": f"job_{i:04d}",
                "config": {"data_file": "data/sample.csv"},
                "output_json": str(tmp_path / f"job_{i:04d}.json"),
            }
            for i in range(1, 4)
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file), stop_on_error=True)

        with patch("subprocess.run") as mock_run:
            # 첫 번째 작업 성공, 두 번째 작업 실패
            mock_run.side_effect = [
                MagicMock(returncode=0, stderr=""),
                MagicMock(returncode=1, stderr="Error"),
            ]
            result = runner.run()

        assert result.total_jobs == 3
        assert result.attempted_jobs == 2
        assert result.success_jobs == 1
        assert result.error_jobs == 1
        assert result.skipped_jobs == 1

    def test_run_stop_on_error_false(self, tmp_path):
        """stop_on_error=False이면 모든 작업을 시도한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": f"job_{i:04d}",
                "config": {"data_file": "data/sample.csv"},
                "output_json": str(tmp_path / f"job_{i:04d}.json"),
            }
            for i in range(1, 4)
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file), stop_on_error=False)

        with patch("subprocess.run") as mock_run:
            # 성공, 실패, 성공
            mock_run.side_effect = [
                MagicMock(returncode=0, stderr=""),
                MagicMock(returncode=1, stderr="Error"),
                MagicMock(returncode=0, stderr=""),
            ]
            result = runner.run()

        assert result.total_jobs == 3
        assert result.attempted_jobs == 3
        assert result.success_jobs == 2
        assert result.error_jobs == 1
        assert result.skipped_jobs == 0

    def test_run_invalid_job_skipped(self, tmp_path):
        """유효하지 않은 작업은 건너뛴다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_data = [
            {
                "job_id": "job_0001",
                "config": {"data_file": "data/sample.csv"},
                "output_json": str(tmp_path / "job_0001.json"),
            },
            {
                "job_id": "job_0002",
                "config": {},  # 유효하지 않음
                "output_json": str(tmp_path / "job_0002.json"),
            },
        ]
        with open(jobs_file, "w") as f:
            for job in jobs_data:
                f.write(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        assert result.total_jobs == 2
        assert result.attempted_jobs == 1
        assert result.error_jobs == 1

    def test_run_timeout(self, tmp_path):
        """타임아웃은 오류로 처리된다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": str(tmp_path / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)
            result = runner.run()

        assert result.attempted_jobs == 1
        assert result.error_jobs == 1
        assert result.exit_code == 1

    def test_run_nonexistent_jobs_file(self):
        """존재하지 않는 파일은 exit_code=2를 반환한다."""
        runner = TuningSessionRunner("/nonexistent/jobs.jsonl")
        result = runner.run()

        assert result.exit_code == 2
        assert result.error_jobs == 1

    def test_run_empty_jobs_file(self, tmp_path):
        """빈 파일은 exit_code=2를 반환한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        jobs_file.write_text("")

        runner = TuningSessionRunner(str(jobs_file))
        result = runner.run()

        assert result.exit_code == 2


class TestBuildCliArgs:
    """Tests for CLI argument building"""

    def test_build_cli_args_minimal(self, tmp_path):
        """최소 인자를 생성한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        config = {"data_file": "data/sample.csv"}
        args = runner._build_cli_args(config)

        assert "--data-file" in args
        assert "data/sample.csv" in args

    def test_build_cli_args_all_fields(self, tmp_path):
        """모든 필드를 포함한다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        config = {
            "data_file": "data/sample.csv",
            "min_spread_bps": 30.0,
            "taker_fee_a_bps": 5.0,
            "taker_fee_b_bps": 5.0,
            "slippage_bps": 5.0,
            "max_position_usd": 1000.0,
            "max_open_trades": 2,
            "initial_balance_usd": 20000.0,
        }
        args = runner._build_cli_args(config)

        assert "--data-file" in args
        assert "--min-spread-bps" in args
        assert "--taker-fee-a-bps" in args
        assert "--taker-fee-b-bps" in args
        assert "--slippage-bps" in args
        assert "--max-position-usd" in args
        assert "--max-open-trades" in args
        assert "--initial-balance-usd" in args

    def test_build_cli_args_skip_none(self, tmp_path):
        """None 값은 건너뛴다."""
        runner = TuningSessionRunner(str(tmp_path / "dummy.jsonl"))
        config = {
            "data_file": "data/sample.csv",
            "min_spread_bps": 30.0,
            "taker_fee_a_bps": None,
            "slippage_bps": 5.0,
        }
        args = runner._build_cli_args(config)

        assert "--taker-fee-a-bps" not in args


class TestSafetyAndPolicy:
    """Tests for safety and policy compliance"""

    def test_no_network_calls(self):
        """네트워크 호출이 없다."""
        import arbitrage.tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        assert "requests" not in source
        assert "http" not in source.lower()
        assert "socket" not in source

    def test_no_kubectl_calls(self):
        """kubectl 호출이 없다."""
        import arbitrage.tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        assert "kubectl" not in source

    def test_no_k8s_integration(self):
        """K8s 통합이 없다."""
        import arbitrage.tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        assert "k8s_" not in source

    def test_subprocess_no_shell(self):
        """subprocess.run에서 shell=True를 사용하지 않는다."""
        import arbitrage.tuning_session_runner as runner_module

        source = open(runner_module.__file__, encoding="utf-8").read()
        # shell=True가 없는지 확인
        assert "shell=True" not in source


class TestEdgeCases:
    """Tests for edge cases"""

    def test_run_max_jobs_zero(self, tmp_path):
        """max_jobs=0이면 작업을 실행하지 않는다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": str(tmp_path / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file), max_jobs=0)
        result = runner.run()

        assert result.attempted_jobs == 0
        assert result.skipped_jobs == 1

    def test_run_creates_output_directory(self, tmp_path):
        """출력 디렉토리를 자동으로 생성한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        output_dir = tmp_path / "nested" / "output"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": str(output_dir / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(str(jobs_file))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        # 디렉토리가 생성되었는지 확인
        assert output_dir.exists()

    def test_run_python_executable_custom(self, tmp_path):
        """커스텀 Python 실행 파일을 사용한다."""
        jobs_file = tmp_path / "jobs.jsonl"
        job = {
            "job_id": "job_0001",
            "config": {"data_file": "data/sample.csv"},
            "output_json": str(tmp_path / "job_0001.json"),
        }
        jobs_file.write_text(json.dumps(job) + "\n")

        runner = TuningSessionRunner(
            str(jobs_file),
            python_executable="python3",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.run()

        # subprocess.run이 호출되었는지 확인
        assert mock_run.called
        # 첫 번째 호출의 첫 번째 인자 확인
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "python3"
