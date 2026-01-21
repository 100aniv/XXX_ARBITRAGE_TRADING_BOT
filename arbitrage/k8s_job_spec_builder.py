# -*- coding: utf-8 -*-
"""
D41 K8s Job Spec Builder

D38 tuning job을 K8s Job manifest로 변환.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class K8sJobSpecBuilder:
    """K8s Job manifest 생성기"""

    def __init__(
        self,
        namespace: str = "default",
        image: str = "python:3.11",
        service_account: str = "default",
        image_pull_policy: str = "IfNotPresent",
    ):
        """
        Args:
            namespace: K8s namespace
            image: Docker image
            service_account: K8s service account
            image_pull_policy: Image pull policy
        """
        self.namespace = namespace
        self.image = image
        self.service_account = service_account
        self.image_pull_policy = image_pull_policy
        logger.info(
            f"[D41_JOB_SPEC] K8sJobSpecBuilder initialized: "
            f"namespace={namespace}, image={image}"
        )

    def build_tuning_job(
        self,
        job_id: str,
        config: Dict[str, Any],
        output_dir: str,
        timeout_seconds: int = 300,
    ) -> Dict[str, Any]:
        """
        D38 tuning job을 K8s Job manifest로 변환.

        Args:
            job_id: Job ID (예: sess001_0001)
            config: Tuning config dict (D39에서 생성)
            output_dir: 결과 JSON 출력 디렉토리
            timeout_seconds: Job timeout (초)

        Returns:
            K8s Job manifest dict
        """
        # Job 이름 정규화 (K8s 규칙: lowercase, alphanumeric, hyphen)
        job_name = self._normalize_job_name(job_id)

        # D38 CLI 인자 생성
        cli_args = self._build_cli_args(config, output_dir)

        # K8s Job manifest 생성
        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {
                    "app": "arbitrage-tuning",
                    "job-id": job_id,
                    "created-at": datetime.now(timezone.utc).isoformat(),
                },
                "annotations": {
                    "job-id": job_id,
                    "config": json.dumps(config),
                },
            },
            "spec": {
                "backoffLimit": 0,  # 재시도 없음
                "ttlSecondsAfterFinished": 3600,  # 1시간 후 자동 삭제
                "activeDeadlineSeconds": timeout_seconds,
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "arbitrage-tuning",
                            "job-id": job_id,
                        },
                    },
                    "spec": {
                        "serviceAccountName": self.service_account,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "tuning-runner",
                                "image": self.image,
                                "imagePullPolicy": self.image_pull_policy,
                                "args": cli_args,
                                "env": [
                                    {
                                        "name": "JOB_ID",
                                        "value": job_id,
                                    },
                                    {
                                        "name": "PYTHONUNBUFFERED",
                                        "value": "1",
                                    },
                                ],
                                "resources": {
                                    "requests": {
                                        "cpu": "500m",
                                        "memory": "512Mi",
                                    },
                                    "limits": {
                                        "cpu": "2000m",
                                        "memory": "2Gi",
                                    },
                                },
                            }
                        ],
                    },
                },
            },
        }

        logger.info(f"[D41_JOB_SPEC] Built job manifest: {job_name}")
        return manifest

    def _normalize_job_name(self, job_id: str) -> str:
        """
        Job ID를 K8s 규칙에 맞게 정규화.

        K8s 규칙:
        - lowercase alphanumeric + hyphen
        - 63자 이하
        - 알파벳으로 시작, 알파벳/숫자/hyphen으로 끝남

        Args:
            job_id: 원본 Job ID

        Returns:
            정규화된 Job 이름
        """
        # 소문자로 변환
        normalized = job_id.lower()

        # 알파벳/숫자/hyphen만 유지
        normalized = "".join(c if c.isalnum() or c == "-" else "-" for c in normalized)

        # 연속된 hyphen 제거
        while "--" in normalized:
            normalized = normalized.replace("--", "-")

        # 양쪽 hyphen 제거
        normalized = normalized.strip("-")

        # 길이 제한 (63자)
        if len(normalized) > 63:
            normalized = normalized[:63].rstrip("-")

        # 알파벳으로 시작하지 않으면 prefix 추가
        if normalized and not normalized[0].isalpha():
            normalized = f"job-{normalized}"

        # 최종 길이 확인
        if len(normalized) > 63:
            normalized = normalized[:63].rstrip("-")

        return normalized

    def _build_cli_args(self, config: Dict[str, Any], output_dir: str) -> List[str]:
        """
        D38 CLI 인자 생성.

        Args:
            config: Tuning config dict
            output_dir: 결과 JSON 출력 디렉토리

        Returns:
            CLI args list (shell=False 형식)
        """
        args = [
            "python",
            "-m",
            "scripts.run_arbitrage_tuning",
        ]

        # config를 JSON 문자열로 전달
        args.extend(["--config", json.dumps(config)])

        # 출력 JSON 경로
        output_json = f"{output_dir}/{config.get('job_id', 'result')}.json"
        args.extend(["--output-json", output_json])

        logger.debug(f"[D41_JOB_SPEC] Built CLI args: {args}")
        return args
