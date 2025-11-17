"""
D40: Tuning Session Local Runner

로컬 환경에서 D39 작업 계획(JSONL)을 읽고 D38 튜닝 작업을 순차적으로 실행하는 모듈.
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TuningSessionRunResult:
    """세션 실행 결과"""

    total_jobs: int
    attempted_jobs: int
    success_jobs: int
    error_jobs: int
    skipped_jobs: int
    exit_code: int
    errors: List[str] = field(default_factory=list)


class TuningSessionRunner:
    """로컬 튜닝 세션 실행기"""

    def __init__(
        self,
        jobs_file: str,
        python_executable: str = "python",
        max_jobs: Optional[int] = None,
        stop_on_error: bool = False,
    ):
        """
        로컬 튜닝 세션 실행기 초기화.

        Args:
            jobs_file: D39 plan_tuning_session에서 생성한 JSONL 파일 경로
            python_executable: Python 실행 명령어 (기본값: "python")
            max_jobs: 실행할 최대 작업 수 (None이면 제한 없음)
            stop_on_error: True이면 첫 오류에서 중단
        """
        self.jobs_file = jobs_file
        self.python_executable = python_executable
        self.max_jobs = max_jobs
        self.stop_on_error = stop_on_error

    def load_jobs(self) -> List[Dict[str, Any]]:
        """
        JSONL 파일에서 작업 계획 로드.

        Returns:
            TuningJobPlan 딕셔너리 목록

        Raises:
            FileNotFoundError: 파일이 없는 경우
            ValueError: 파일이 비어있거나 형식이 잘못된 경우
        """
        jobs_path = Path(self.jobs_file)

        if not jobs_path.exists():
            raise FileNotFoundError(f"Jobs file not found: {self.jobs_file}")

        jobs = []
        try:
            with open(jobs_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        job = json.loads(line)
                        jobs.append(job)
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Invalid JSON at line {line_num}: {e}"
                        )

            if not jobs:
                raise ValueError("Jobs file is empty")

            return jobs

        except (FileNotFoundError, ValueError):
            raise
        except Exception as e:
            raise ValueError(f"Error reading jobs file: {e}")

    def _build_cli_args(self, config: Dict[str, Any]) -> List[str]:
        """
        작업 설정에서 D38 CLI 인자 생성.

        Args:
            config: TuningJobPlan의 config 딕셔너리

        Returns:
            CLI 인자 목록
        """
        args = ["--data-file", str(config.get("data_file", ""))]

        # 선택적 매개변수
        optional_fields = [
            ("min_spread_bps", "--min-spread-bps"),
            ("taker_fee_a_bps", "--taker-fee-a-bps"),
            ("taker_fee_b_bps", "--taker-fee-b-bps"),
            ("slippage_bps", "--slippage-bps"),
            ("max_position_usd", "--max-position-usd"),
            ("max_open_trades", "--max-open-trades"),
            ("initial_balance_usd", "--initial-balance-usd"),
            ("stop_on_drawdown_pct", "--stop-on-drawdown-pct"),
        ]

        for field_name, cli_flag in optional_fields:
            if field_name in config and config[field_name] is not None:
                args.extend([cli_flag, str(config[field_name])])

        return args

    def _validate_job(self, job: Dict[str, Any]) -> Optional[str]:
        """
        작업 유효성 검사.

        Args:
            job: TuningJobPlan 딕셔너리

        Returns:
            오류 메시지 (유효하면 None)
        """
        if "job_id" not in job:
            return "Missing job_id"
        if "config" not in job:
            return "Missing config"
        if "output_json" not in job:
            return "Missing output_json"

        config = job.get("config", {})
        if not isinstance(config, dict):
            return "config must be a dictionary"
        if "data_file" not in config or not config["data_file"]:
            return "Missing data_file in config"

        return None

    def run(self) -> TuningSessionRunResult:
        """
        세션 실행.

        Returns:
            TuningSessionRunResult
        """
        # 작업 로드
        try:
            jobs = self.load_jobs()
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load jobs: {e}")
            return TuningSessionRunResult(
                total_jobs=0,
                attempted_jobs=0,
                success_jobs=0,
                error_jobs=1,
                skipped_jobs=0,
                exit_code=2,
                errors=[str(e)],
            )

        total_jobs = len(jobs)
        attempted_jobs = 0
        success_jobs = 0
        error_jobs = 0
        skipped_jobs = 0
        errors = []

        # 작업 실행
        for idx, job in enumerate(jobs):
            # max_jobs 제한 확인
            if self.max_jobs is not None and attempted_jobs >= self.max_jobs:
                skipped_jobs = total_jobs - attempted_jobs
                break

            # 작업 유효성 검사
            validation_error = self._validate_job(job)
            if validation_error:
                logger.error(f"Job {job.get('job_id', 'unknown')}: {validation_error}")
                error_jobs += 1
                errors.append(f"Job {job.get('job_id', 'unknown')}: {validation_error}")
                if self.stop_on_error:
                    skipped_jobs = total_jobs - attempted_jobs - 1
                    break
                continue

            job_id = job["job_id"]
            config = job["config"]
            output_json = job["output_json"]

            logger.info(f"Running job {idx + 1}/{total_jobs}: {job_id}")

            # 출력 디렉토리 생성
            output_path = Path(output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # D38 CLI 인자 생성
            cli_args = self._build_cli_args(config)
            cli_args.extend(["--output-json", output_json])

            # D38 CLI 실행
            cmd = [self.python_executable, "-m", "scripts.run_arbitrage_tuning"] + cli_args

            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5분 타임아웃
                )

                attempted_jobs += 1

                if result.returncode == 0:
                    success_jobs += 1
                    logger.info(f"Job {job_id} completed successfully")
                else:
                    error_jobs += 1
                    error_msg = f"Job {job_id} failed with exit code {result.returncode}"
                    logger.error(error_msg)
                    if result.stderr:
                        logger.error(f"  stderr: {result.stderr[:200]}")
                    errors.append(error_msg)
                    if self.stop_on_error:
                        skipped_jobs = total_jobs - attempted_jobs
                        break

            except subprocess.TimeoutExpired:
                attempted_jobs += 1
                error_jobs += 1
                error_msg = f"Job {job_id} timed out (>300s)"
                logger.error(error_msg)
                errors.append(error_msg)
                if self.stop_on_error:
                    skipped_jobs = total_jobs - attempted_jobs
                    break
            except Exception as e:
                attempted_jobs += 1
                error_jobs += 1
                error_msg = f"Job {job_id} error: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                if self.stop_on_error:
                    skipped_jobs = total_jobs - attempted_jobs
                    break

        # 종료 코드 결정
        if error_jobs == 0 and attempted_jobs > 0:
            exit_code = 0
        elif error_jobs > 0:
            exit_code = 1
        else:
            exit_code = 2

        return TuningSessionRunResult(
            total_jobs=total_jobs,
            attempted_jobs=attempted_jobs,
            success_jobs=success_jobs,
            error_jobs=error_jobs,
            skipped_jobs=skipped_jobs,
            exit_code=exit_code,
            errors=errors,
        )
