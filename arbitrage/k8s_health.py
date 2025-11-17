# -*- coding: utf-8 -*-
"""
D33 Kubernetes Health Evaluation & CI-friendly Alert Layer (Read-Only)

K8s Job/Pod 상태를 기반으로 건강 상태를 평가하고 CI/CD 친화적인 종료 코드를 제공합니다.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from datetime import datetime

from .k8s_monitor import K8sMonitorSnapshot, K8sJobStatus

logger = logging.getLogger(__name__)

# 건강 상태 레벨
HealthLevel = Literal["OK", "WARN", "ERROR"]


class K8sHealthError(Exception):
    """K8s 건강 평가 에러"""
    pass


@dataclass
class K8sJobHealth:
    """Job 건강 상태"""
    job_name: str
    namespace: str
    phase: str
    succeeded: Optional[int]
    failed: Optional[int]
    active: Optional[int]
    health: HealthLevel
    reasons: List[str]
    labels: Dict[str, str]


@dataclass
class K8sHealthSnapshot:
    """K8s 건강 상태 스냅샷"""
    namespace: str
    selector: str
    jobs_health: List[K8sJobHealth]
    errors: List[str]
    overall_health: HealthLevel
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class K8sHealthEvaluator:
    """K8s 건강 상태 평가기"""
    
    def __init__(
        self,
        warn_on_pending: bool = True,
        treat_unknown_as_error: bool = True,
    ):
        """
        초기화
        
        Args:
            warn_on_pending: True면 PENDING 상태를 WARN으로 분류
            treat_unknown_as_error: True면 UNKNOWN 상태를 ERROR로 분류
        """
        self.warn_on_pending = warn_on_pending
        self.treat_unknown_as_error = treat_unknown_as_error
        
        logger.info(
            f"[D33_K8S_HEALTH] K8sHealthEvaluator initialized: "
            f"warn_on_pending={warn_on_pending}, "
            f"treat_unknown_as_error={treat_unknown_as_error}"
        )
    
    def evaluate(self, snapshot: K8sMonitorSnapshot) -> K8sHealthSnapshot:
        """
        모니터링 스냅샷을 기반으로 건강 상태 평가
        
        Args:
            snapshot: K8sMonitorSnapshot
        
        Returns:
            K8sHealthSnapshot
        """
        logger.info(
            f"[D33_K8S_HEALTH] Evaluating health for {len(snapshot.jobs)} jobs"
        )
        
        # 각 Job의 건강 상태 평가
        jobs_health = []
        for job_status in snapshot.jobs:
            job_health = self._evaluate_job(job_status)
            jobs_health.append(job_health)
            logger.debug(
                f"[D33_K8S_HEALTH] Job {job_status.job_name}: "
                f"phase={job_status.phase}, health={job_health.health}, "
                f"reasons={job_health.reasons}"
            )
        
        # 전체 건강 상태 계산
        overall_health = self._compute_overall_health(jobs_health, snapshot.errors)
        
        logger.info(
            f"[D33_K8S_HEALTH] Overall health: {overall_health} "
            f"(jobs={len(jobs_health)}, errors={len(snapshot.errors)})"
        )
        
        return K8sHealthSnapshot(
            namespace=snapshot.namespace,
            selector=snapshot.selector,
            jobs_health=jobs_health,
            errors=snapshot.errors,
            overall_health=overall_health,
            timestamp=snapshot.timestamp
        )
    
    def _evaluate_job(self, job_status: K8sJobStatus) -> K8sJobHealth:
        """
        개별 Job의 건강 상태 평가
        
        Args:
            job_status: K8sJobStatus
        
        Returns:
            K8sJobHealth
        """
        phase = job_status.phase
        reasons = []
        health: HealthLevel = "OK"
        
        # Phase 기반 건강 상태 결정
        if phase == "FAILED":
            health = "ERROR"
            reasons.append("job_failed")
        
        elif phase == "UNKNOWN":
            if self.treat_unknown_as_error:
                health = "ERROR"
                reasons.append("unknown_phase")
            else:
                health = "WARN"
                reasons.append("unknown_phase")
        
        elif phase == "PENDING":
            if self.warn_on_pending:
                health = "WARN"
                reasons.append("pending")
            else:
                health = "OK"
        
        elif phase == "RUNNING":
            health = "OK"
        
        elif phase == "SUCCEEDED":
            health = "OK"
        
        else:
            # 예상치 못한 phase
            health = "WARN"
            reasons.append("unexpected_phase")
        
        return K8sJobHealth(
            job_name=job_status.job_name,
            namespace=job_status.namespace,
            phase=phase,
            succeeded=job_status.succeeded,
            failed=job_status.failed,
            active=job_status.active,
            health=health,
            reasons=reasons,
            labels=job_status.labels
        )
    
    def _compute_overall_health(
        self,
        jobs_health: List[K8sJobHealth],
        errors: List[str]
    ) -> HealthLevel:
        """
        전체 건강 상태 계산
        
        Args:
            jobs_health: Job 건강 상태 목록
            errors: 에러 목록
        
        Returns:
            HealthLevel
        """
        # ERROR가 있으면 전체 ERROR
        for job_health in jobs_health:
            if job_health.health == "ERROR":
                return "ERROR"
        
        # WARN이 있거나 에러가 있으면 전체 WARN
        has_warn = any(jh.health == "WARN" for jh in jobs_health)
        has_errors = len(errors) > 0
        
        if has_warn or has_errors:
            return "WARN"
        
        # 모두 OK
        return "OK"


def generate_health_report_text(health: K8sHealthSnapshot) -> str:
    """
    건강 상태 스냅샷을 텍스트 보고서로 변환
    
    Args:
        health: K8sHealthSnapshot
    
    Returns:
        포맷된 텍스트 보고서
    """
    lines = []
    
    # 헤더
    lines.append("=" * 80)
    lines.append("[D33_K8S_HEALTH] KUBERNETES HEALTH EVALUATION SNAPSHOT")
    lines.append("=" * 80)
    lines.append("")
    
    # 헤더 정보
    lines.append("[HEADER]")
    lines.append(f"Namespace:               {health.namespace}")
    lines.append(f"Label Selector:          {health.selector}")
    lines.append(f"Timestamp:               {health.timestamp}")
    lines.append(f"Overall Health:          {health.overall_health}")
    lines.append("")
    
    # Job 건강 상태
    lines.append("[JOBS]")
    if health.jobs_health:
        for job_health in health.jobs_health:
            lines.append("")
            lines.append(f"  Job: {job_health.job_name}")
            lines.append(f"    Namespace:           {job_health.namespace}")
            lines.append(f"    Phase:               {job_health.phase}")
            lines.append(f"    Health:              {job_health.health}")
            lines.append(f"    Succeeded:           {job_health.succeeded}")
            lines.append(f"    Failed:              {job_health.failed}")
            lines.append(f"    Active:              {job_health.active}")
            
            if job_health.reasons:
                lines.append(f"    Reasons:             {', '.join(job_health.reasons)}")
            
            if job_health.labels:
                lines.append(f"    Labels:")
                for key, value in job_health.labels.items():
                    lines.append(f"      {key}: {value}")
    else:
        lines.append("  (No jobs)")
    
    lines.append("")
    
    # 에러
    if health.errors:
        lines.append("[ERRORS]")
        for error in health.errors:
            lines.append(f"  - {error}")
        lines.append("")
    
    # 푸터
    lines.append("=" * 80)
    lines.append("[D33_K8S_HEALTH] END OF HEALTH SNAPSHOT")
    lines.append("=" * 80)
    
    return "\n".join(lines)
