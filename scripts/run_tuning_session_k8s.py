#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D41: Kubernetes 기반 Tuning Session Distributed Runner CLI

D39 작업 계획(JSONL)을 K8s Job으로 병렬 실행.

주의:
- 이 스크립트는 실제 Kubernetes 클러스터가 구성되어 있을 때만 의미가 있습니다.
- 개인 로컬 Docker 환경에서는 선택적 기능입니다.
- 테스트 환경에서는 dry_run=True로 실행됩니다.
"""

import argparse
import logging
import sys
from pathlib import Path

from arbitrage.k8s_tuning_session_runner import K8sTuningSessionRunner

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def format_summary(result) -> str:
    """
    세션 실행 결과를 인간 친화적 형식으로 포맷 (D40과 동일).

    Args:
        result: K8sTuningSessionRunResult

    Returns:
        포맷된 요약 문자열
    """
    lines = [
        "=" * 70,
        "[D41_K8S_SESSION] KUBERNETES TUNING SESSION SUMMARY",
        "=" * 70,
        "",
        f"Total Jobs:     {result.total_jobs}",
        f"Attempted:      {result.attempted_jobs}",
        f"Success:        {result.success_jobs}",
        f"Errors:         {result.error_jobs}",
        f"Skipped:        {result.skipped_jobs}",
        "",
        f"Exit Code:      {result.exit_code}  ",
    ]

    # Exit code 설명
    if result.exit_code == 0:
        lines[-1] += "(✅ ALL JOBS SUCCEEDED)"
    elif result.exit_code == 1:
        lines[-1] += "(⚠️  SOME JOBS FAILED)"
    else:
        lines[-1] += "(❌ FILE/RUNTIME ERROR)"

    # 오류 메시지
    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for error in result.errors[:10]:  # 최대 10개만 표시
            lines.append(f"  - {error}")
        if len(result.errors) > 10:
            lines.append(f"  ... and {len(result.errors) - 10} more errors")

    # Job ID 목록
    if result.job_ids:
        lines.append("")
        lines.append(f"Submitted Jobs ({len(result.job_ids)}):")
        for job_id in result.job_ids[:5]:  # 최대 5개만 표시
            lines.append(f"  - {job_id}")
        if len(result.job_ids) > 5:
            lines.append(f"  ... and {len(result.job_ids) - 5} more jobs")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        description="D41: Kubernetes 기반 Tuning Session Distributed Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 모든 작업 실행 (기본값: 4개 동시)
  python -m scripts.run_tuning_session_k8s --jobs-file outputs/tuning/session001_jobs.jsonl

  # 최대 8개 동시 실행
  python -m scripts.run_tuning_session_k8s --jobs-file outputs/tuning/session001_jobs.jsonl --max-parallel 8

  # 실패 Job 재시도
  python -m scripts.run_tuning_session_k8s --jobs-file outputs/tuning/session001_jobs.jsonl --retry-failed

  # submit만 하고 대기하지 않음
  python -m scripts.run_tuning_session_k8s --jobs-file outputs/tuning/session001_jobs.jsonl --no-wait

Note:
  이 스크립트는 실제 Kubernetes 클러스터가 구성되어 있을 때만 의미가 있습니다.
  개인 로컬 Docker 환경에서는 선택적 기능입니다.
        """,
    )

    parser.add_argument(
        "--jobs-file",
        required=True,
        help="D39 plan_tuning_session에서 생성한 JSONL 파일 경로",
    )

    parser.add_argument(
        "--namespace",
        default="default",
        help="Kubernetes namespace (기본값: default)",
    )

    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="동시 실행 Job 수 (기본값: 4)",
    )

    parser.add_argument(
        "--timeout-per-job",
        type=int,
        default=300,
        help="각 Job 타임아웃 (초, 기본값: 300)",
    )

    parser.add_argument(
        "--timeout-session",
        type=int,
        default=3600,
        help="전체 세션 타임아웃 (초, 기본값: 3600)",
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="실패 Job 재시도 여부",
    )

    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="submit만 하고 완료 대기하지 않음",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 K8s API 호출 없이 시뮬레이션 (테스트용)",
    )

    args = parser.parse_args()

    # 입력 파일 확인
    jobs_file = Path(args.jobs_file)
    if not jobs_file.exists():
        logger.error(f"Jobs file not found: {args.jobs_file}")
        return 2

    # 경고 메시지
    logger.warning(
        "[D41_K8S_SESSION] This is an optional K8s feature. "
        "Only use if you have a Kubernetes cluster configured."
    )

    if args.dry_run:
        logger.info("[D41_K8S_SESSION] Running in DRY_RUN mode (no actual K8s API calls)")

    try:
        # Runner 생성
        runner = K8sTuningSessionRunner(
            jobs_file=str(args.jobs_file),
            namespace=args.namespace,
            max_parallel=args.max_parallel,
            timeout_per_job=args.timeout_per_job,
            timeout_session=args.timeout_session,
            retry_failed=args.retry_failed,
            wait=not args.no_wait,
        )

        # 세션 실행
        result = runner.run()

        # 결과 출력
        print(format_summary(result))

        # 종료 코드 반환
        return result.exit_code

    except Exception as e:
        logger.error(f"[D41_K8S_SESSION] Unexpected error: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
