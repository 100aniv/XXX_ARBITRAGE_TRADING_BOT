"""
D40: Local Tuning Session Runner CLI

D39 작업 계획(JSONL)을 읽고 D38 튜닝 작업을 순차적으로 실행하는 CLI.

Usage:
    python -m scripts.run_tuning_session_local \
      --jobs-file outputs/tuning/session001_jobs.jsonl

    python -m scripts.run_tuning_session_local \
      --jobs-file outputs/tuning/session001_jobs.jsonl \
      --max-jobs 10 \
      --stop-on-error

Exit codes:
    0: 모든 작업 성공
    1: 일부 작업 실패
    2: 파일 오류 또는 런타임 오류
"""

import argparse
import logging
import sys
from pathlib import Path

from arbitrage.tuning_session_runner import TuningSessionRunner

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def format_summary(result) -> str:
    """결과를 인간 친화적 형식으로 포맷팅."""
    lines = []
    lines.append("=" * 70)
    lines.append("[D40_SESSION] LOCAL TUNING SESSION SUMMARY")
    lines.append("=" * 70)
    lines.append("")

    lines.append(f"Total Jobs:     {result.total_jobs}")
    lines.append(f"Attempted:      {result.attempted_jobs}")
    lines.append(f"Success:        {result.success_jobs}")
    lines.append(f"Errors:         {result.error_jobs}")
    lines.append(f"Skipped:        {result.skipped_jobs}")
    lines.append("")

    if result.exit_code == 0:
        status = "✅ ALL JOBS SUCCEEDED"
    elif result.exit_code == 1:
        status = "⚠️  SOME JOBS FAILED"
    else:
        status = "❌ FATAL ERROR"

    lines.append(f"Exit Code:      {result.exit_code}  ({status})")

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for error in result.errors[:10]:  # 최대 10개 오류만 표시
            lines.append(f"  - {error}")
        if len(result.errors) > 10:
            lines.append(f"  ... and {len(result.errors) - 10} more")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main():
    """메인 진입점."""
    parser = argparse.ArgumentParser(
        description="Run D39 tuning session jobs locally (D38 multi-job executor)."
    )

    parser.add_argument(
        "--jobs-file",
        required=True,
        help="JSONL file of TuningJobPlan (from plan_tuning_session.py)",
    )
    parser.add_argument(
        "--python-executable",
        default="python",
        help="Python executable command (default: python)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        help="Maximum number of jobs to execute",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop execution on first job failure",
    )

    args = parser.parse_args()

    try:
        # 작업 파일 존재 확인
        jobs_path = Path(args.jobs_file)
        if not jobs_path.exists():
            print(f"[D40_SESSION] ERROR: Jobs file not found: {args.jobs_file}", file=sys.stderr)
            return 1

        # 세션 실행기 생성
        runner = TuningSessionRunner(
            jobs_file=args.jobs_file,
            python_executable=args.python_executable,
            max_jobs=args.max_jobs,
            stop_on_error=args.stop_on_error,
        )

        # 세션 실행
        logger.info(f"Starting tuning session from: {args.jobs_file}")
        result = runner.run()

        # 결과 출력
        print(format_summary(result))

        return result.exit_code

    except Exception as e:
        print(f"[D40_SESSION] FATAL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
