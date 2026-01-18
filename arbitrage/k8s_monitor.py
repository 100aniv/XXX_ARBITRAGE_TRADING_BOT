# -*- coding: utf-8 -*-
"""
D32 Kubernetes Job/Pod Monitoring & Log Collection (Read-Only)

K8s 클러스터의 Job/Pod 상태 모니터링 및 로그 수집.
실제 kubectl get/logs 호출로 정보 수집 (수정 작업 없음).
"""

import logging
import subprocess
import json
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


JobPhase = Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"]


class K8sMonitorError(Exception):
    """K8s Monitor 에러"""
    pass


@dataclass
class K8sPodLog:
    """K8s Pod 로그"""
    pod_name: str
    namespace: str
    container_name: str
    lines: List[str]


@dataclass
class K8sJobStatus:
    """K8s Job 상태"""
    job_name: str
    namespace: str
    labels: Dict[str, str]
    completions: Optional[int]
    succeeded: Optional[int]
    failed: Optional[int]
    active: Optional[int]
    phase: JobPhase
    start_time: Optional[str]
    completion_time: Optional[str]


@dataclass
class K8sMonitorSnapshot:
    """K8s 모니터링 스냅샷"""
    namespace: str
    selector: str
    jobs: List[K8sJobStatus]
    pods_logs: List[K8sPodLog]
    timestamp: str
    errors: List[str] = field(default_factory=list)


class K8sJobMonitor:
    """K8s Job/Pod 모니터링"""
    
    def __init__(
        self,
        namespace: str,
        label_selector: str,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        max_log_lines: int = 100
    ):
        """
        Args:
            namespace: K8s 네임스페이스 (예: 'trading-bots')
            label_selector: 레이블 선택자 (예: 'app=arbitrage-tuning,session_id=...')
            kubeconfig: kubeconfig 파일 경로
            context: K8s 컨텍스트
            max_log_lines: Pod당 최대 로그 라인 수
        """
        self.namespace = namespace
        self.label_selector = label_selector
        self.kubeconfig = kubeconfig
        self.context = context
        self.max_log_lines = max_log_lines
        
        logger.info(f"[D32_K8S_MONITOR] K8sJobMonitor initialized: namespace={namespace}, selector={label_selector}")
    
    def load_snapshot(self) -> K8sMonitorSnapshot:
        """
        K8s Job/Pod 상태 스냅샷 로드
        
        Returns:
            K8sMonitorSnapshot
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        errors = []
        
        logger.info(f"[D32_K8S_MONITOR] Loading snapshot: namespace={self.namespace}, selector={self.label_selector}")
        
        # Job 상태 로드
        jobs = []
        try:
            jobs = self._load_jobs()
            logger.info(f"[D32_K8S_MONITOR] Loaded {len(jobs)} jobs")
        except Exception as e:
            logger.warning(f"[D32_K8S_MONITOR] Error loading jobs: {e}")
            errors.append(f"Failed to load jobs: {str(e)}")
        
        # Pod 로그 로드
        pods_logs = []
        try:
            pods_logs = self._load_pod_logs()
            logger.info(f"[D32_K8S_MONITOR] Loaded logs from {len(pods_logs)} pods")
        except Exception as e:
            logger.warning(f"[D32_K8S_MONITOR] Error loading pod logs: {e}")
            errors.append(f"Failed to load pod logs: {str(e)}")
        
        snapshot = K8sMonitorSnapshot(
            namespace=self.namespace,
            selector=self.label_selector,
            jobs=jobs,
            pods_logs=pods_logs,
            timestamp=timestamp,
            errors=errors
        )
        
        logger.info(f"[D32_K8S_MONITOR] Snapshot loaded: {len(jobs)} jobs, {len(pods_logs)} pods, {len(errors)} errors")
        
        return snapshot
    
    def _load_jobs(self) -> List[K8sJobStatus]:
        """K8s Job 상태 로드"""
        try:
            # kubectl get jobs 명령 실행
            command = [
                "kubectl", "get", "jobs",
                "-o", "json",
                "-n", self.namespace,
                "-l", self.label_selector
            ]
            
            if self.kubeconfig:
                command.extend(["--kubeconfig", self.kubeconfig])
            
            if self.context:
                command.extend(["--context", self.context])
            
            logger.info(f"[D32_K8S_MONITOR] Executing: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"[D32_K8S_MONITOR] kubectl get jobs failed: {result.stderr}")
                return []
            
            # JSON 파싱
            data = json.loads(result.stdout)
            jobs = []
            
            for item in data.get("items", []):
                try:
                    job_status = self._parse_job_item(item)
                    jobs.append(job_status)
                except Exception as e:
                    logger.warning(f"[D32_K8S_MONITOR] Error parsing job item: {e}")
            
            return jobs
        
        except subprocess.TimeoutExpired:
            logger.error(f"[D32_K8S_MONITOR] kubectl timeout")
            raise K8sMonitorError("kubectl timeout")
        except FileNotFoundError:
            logger.error(f"[D32_K8S_MONITOR] kubectl not found")
            raise K8sMonitorError("kubectl not found")
        except json.JSONDecodeError as e:
            logger.error(f"[D32_K8S_MONITOR] JSON decode error: {e}")
            raise K8sMonitorError(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"[D32_K8S_MONITOR] Error loading jobs: {e}")
            raise K8sMonitorError(f"Error loading jobs: {e}")
    
    def _load_pod_logs(self) -> List[K8sPodLog]:
        """K8s Pod 로그 로드"""
        try:
            # kubectl get pods 명령 실행
            command = [
                "kubectl", "get", "pods",
                "-o", "json",
                "-n", self.namespace,
                "-l", self.label_selector
            ]
            
            if self.kubeconfig:
                command.extend(["--kubeconfig", self.kubeconfig])
            
            if self.context:
                command.extend(["--context", self.context])
            
            logger.info(f"[D32_K8S_MONITOR] Executing: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"[D32_K8S_MONITOR] kubectl get pods failed: {result.stderr}")
                return []
            
            # JSON 파싱
            data = json.loads(result.stdout)
            pods_logs = []
            
            for item in data.get("items", []):
                try:
                    pod_name = item.get("metadata", {}).get("name")
                    pod_namespace = item.get("metadata", {}).get("namespace", self.namespace)
                    
                    if not pod_name:
                        continue
                    
                    # 각 컨테이너의 로그 수집
                    containers = item.get("spec", {}).get("containers", [])
                    for container in containers:
                        container_name = container.get("name", "unknown")
                        
                        try:
                            pod_log = self._fetch_pod_log(
                                pod_name,
                                pod_namespace,
                                container_name
                            )
                            if pod_log:
                                pods_logs.append(pod_log)
                        except Exception as e:
                            logger.warning(f"[D32_K8S_MONITOR] Error fetching logs for {pod_name}/{container_name}: {e}")
                
                except Exception as e:
                    logger.warning(f"[D32_K8S_MONITOR] Error parsing pod item: {e}")
            
            return pods_logs
        
        except subprocess.TimeoutExpired:
            logger.error(f"[D32_K8S_MONITOR] kubectl timeout")
            raise K8sMonitorError("kubectl timeout")
        except FileNotFoundError:
            logger.error(f"[D32_K8S_MONITOR] kubectl not found")
            raise K8sMonitorError("kubectl not found")
        except json.JSONDecodeError as e:
            logger.error(f"[D32_K8S_MONITOR] JSON decode error: {e}")
            raise K8sMonitorError(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"[D32_K8S_MONITOR] Error loading pod logs: {e}")
            raise K8sMonitorError(f"Error loading pod logs: {e}")
    
    def _fetch_pod_log(
        self,
        pod_name: str,
        namespace: str,
        container_name: str
    ) -> Optional[K8sPodLog]:
        """Pod 로그 수집"""
        try:
            # kubectl logs 명령 실행
            command = [
                "kubectl", "logs",
                pod_name,
                "-n", namespace,
                "-c", container_name,
                f"--tail={self.max_log_lines}"
            ]
            
            if self.kubeconfig:
                command.extend(["--kubeconfig", self.kubeconfig])
            
            if self.context:
                command.extend(["--context", self.context])
            
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.debug(f"[D32_K8S_MONITOR] kubectl logs failed for {pod_name}: {result.stderr}")
                # 로그가 없을 수 있으므로 빈 로그로 반환
                return K8sPodLog(
                    pod_name=pod_name,
                    namespace=namespace,
                    container_name=container_name,
                    lines=[]
                )
            
            # 로그 라인 분할
            lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            return K8sPodLog(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                lines=lines
            )
        
        except subprocess.TimeoutExpired:
            logger.warning(f"[D32_K8S_MONITOR] kubectl logs timeout for {pod_name}")
            return None
        except Exception as e:
            logger.warning(f"[D32_K8S_MONITOR] Error fetching logs for {pod_name}: {e}")
            return None
    
    def _parse_job_item(self, item: Dict) -> K8sJobStatus:
        """Job JSON 항목 파싱"""
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        
        job_name = metadata.get("name", "unknown")
        namespace = metadata.get("namespace", self.namespace)
        labels = metadata.get("labels", {})
        
        # Job 단계 결정
        phase = self._determine_job_phase(status)
        
        # 시간 정보
        start_time = status.get("startTime")
        completion_time = status.get("completionTime")
        
        # 완료 정보
        completions = spec.get("completions")
        succeeded = status.get("succeeded")
        failed = status.get("failed")
        active = status.get("active")
        
        return K8sJobStatus(
            job_name=job_name,
            namespace=namespace,
            labels=labels,
            completions=completions,
            succeeded=succeeded,
            failed=failed,
            active=active,
            phase=phase,
            start_time=start_time,
            completion_time=completion_time
        )
    
    def _determine_job_phase(self, status: Dict) -> JobPhase:
        """Job 단계 결정"""
        # Job 상태 판단
        if status.get("succeeded"):
            return "SUCCEEDED"
        elif status.get("failed"):
            return "FAILED"
        elif status.get("active"):
            return "RUNNING"
        elif status.get("conditions"):
            # conditions 확인
            for condition in status.get("conditions", []):
                if condition.get("type") == "Complete" and condition.get("status") == "True":
                    return "SUCCEEDED"
                elif condition.get("type") == "Failed" and condition.get("status") == "True":
                    return "FAILED"
        
        # 기본값
        if status.get("startTime"):
            return "RUNNING"
        else:
            return "PENDING"


def generate_monitor_report_text(snapshot: K8sMonitorSnapshot) -> str:
    """
    K8s 모니터링 스냅샷을 텍스트로 변환
    
    Args:
        snapshot: K8sMonitorSnapshot
    
    Returns:
        포맷된 텍스트
    """
    lines = []
    
    lines.append("=" * 80)
    lines.append("[D32_K8S_MONITOR] KUBERNETES JOB/POD MONITORING SNAPSHOT")
    lines.append("=" * 80)
    lines.append("")
    
    # 헤더
    lines.append("[HEADER]")
    lines.append(f"Namespace:               {snapshot.namespace}")
    lines.append(f"Label Selector:          {snapshot.selector}")
    lines.append(f"Timestamp:               {snapshot.timestamp}")
    lines.append("")
    
    # Job 상태
    if snapshot.jobs:
        lines.append("[JOB STATUS]")
        for job in snapshot.jobs:
            lines.append(f"\n  Job: {job.job_name}")
            lines.append(f"    Namespace:           {job.namespace}")
            lines.append(f"    Phase:               {job.phase}")
            lines.append(f"    Completions:         {job.completions}")
            lines.append(f"    Succeeded:           {job.succeeded}")
            lines.append(f"    Failed:              {job.failed}")
            lines.append(f"    Active:              {job.active}")
            lines.append(f"    Start Time:          {job.start_time}")
            lines.append(f"    Completion Time:     {job.completion_time}")
            
            if job.labels:
                lines.append(f"    Labels:")
                for key, value in job.labels.items():
                    lines.append(f"      {key}: {value}")
        lines.append("")
    else:
        lines.append("[JOB STATUS]")
        lines.append("  (No jobs found)")
        lines.append("")
    
    # Pod 로그
    if snapshot.pods_logs:
        lines.append("[POD LOGS]")
        for pod_log in snapshot.pods_logs:
            lines.append(f"\n  Pod: {pod_log.pod_name} / Container: {pod_log.container_name}")
            lines.append(f"    Namespace:           {pod_log.namespace}")
            
            if pod_log.lines:
                lines.append(f"    Log Lines ({len(pod_log.lines)}):")
                for log_line in pod_log.lines[-10:]:  # 마지막 10줄만 표시
                    lines.append(f"      {log_line}")
            else:
                lines.append(f"    (No logs)")
        lines.append("")
    else:
        lines.append("[POD LOGS]")
        lines.append("  (No pods found)")
        lines.append("")
    
    # 에러
    if snapshot.errors:
        lines.append("[ERRORS]")
        for error in snapshot.errors:
            lines.append(f"  ✗ {error}")
        lines.append("")
    
    lines.append("=" * 80)
    lines.append("[D32_K8S_MONITOR] END OF SNAPSHOT")
    lines.append("=" * 80)
    
    return "\n".join(lines)
