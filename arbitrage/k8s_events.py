# -*- coding: utf-8 -*-
"""
D34 Kubernetes Events Collection (Read-Only)

K8s 이벤트를 수집하고 관리합니다.
"""

import subprocess
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class K8sEvent:
    """K8s 이벤트"""
    type: str                       # Normal, Warning, etc.
    reason: str                     # 이유 (e.g., "BackoffLimitExceeded")
    message: str                    # 메시지
    involved_kind: Optional[str]    # 관련 객체 종류 (Job, Pod, etc.)
    involved_name: Optional[str]    # 관련 객체 이름
    involved_namespace: Optional[str]  # 관련 객체 네임스페이스
    first_timestamp: Optional[str]  # 첫 발생 시간
    last_timestamp: Optional[str]   # 마지막 발생 시간
    count: Optional[int]            # 발생 횟수
    raw: Dict[str, Any] = field(default_factory=dict)  # 원본 이벤트 (디버깅용)


@dataclass
class K8sEventSnapshot:
    """K8s 이벤트 스냅샷"""
    namespace: str                  # K8s 네임스페이스
    selector: str                   # 레이블 선택자
    events: List[K8sEvent]          # 이벤트 목록
    timestamp: str                  # 스냅샷 타임스탬프
    errors: List[str]               # 수집 중 발생한 에러


class K8sEventCollector:
    """K8s 이벤트 수집기"""
    
    def __init__(
        self,
        namespace: str,
        label_selector: str,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ):
        """
        K8s 이벤트 수집기 초기화
        
        Args:
            namespace: K8s 네임스페이스 (예: 'trading-bots')
            label_selector: 레이블 선택자 (예: 'app=arbitrage-tuning,session_id=...')
            kubeconfig: kubeconfig 파일 경로 (선택)
            context: K8s 컨텍스트 (선택)
        """
        self.namespace = namespace
        self.label_selector = label_selector
        self.kubeconfig = kubeconfig
        self.context = context
    
    def load_events(self) -> K8sEventSnapshot:
        """
        K8s 이벤트 수집
        
        Returns:
            K8sEventSnapshot: 이벤트 스냅샷
        """
        logger.info(f"[D34_K8S_EVENTS] Loading events: namespace={self.namespace}, selector={self.label_selector}")
        
        events = []
        errors = []
        
        try:
            # kubectl get events 실행
            events_data = self._load_events_json()
            
            # 이벤트 필터링 및 파싱
            events = self._parse_events(events_data)
            logger.info(f"[D34_K8S_EVENTS] Loaded {len(events)} events")
        
        except FileNotFoundError as e:
            error_msg = f"kubectl not found: {e}"
            logger.error(f"[D34_K8S_EVENTS] {error_msg}")
            errors.append(error_msg)
        
        except json.JSONDecodeError as e:
            error_msg = f"JSON decode error: {e}"
            logger.error(f"[D34_K8S_EVENTS] {error_msg}")
            errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(f"[D34_K8S_EVENTS] {error_msg}")
            errors.append(error_msg)
        
        return K8sEventSnapshot(
            namespace=self.namespace,
            selector=self.label_selector,
            events=events,
            timestamp=datetime.now(timezone.utc).isoformat(),
            errors=errors
        )
    
    def _load_events_json(self) -> Dict[str, Any]:
        """
        kubectl get events JSON 로드
        
        Returns:
            이벤트 JSON 데이터
        
        Raises:
            FileNotFoundError: kubectl을 찾을 수 없음
            json.JSONDecodeError: JSON 파싱 실패
        """
        cmd = ["kubectl", "get", "events", "-o", "json", "-n", self.namespace]
        
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        
        if self.context:
            cmd.extend(["--context", self.context])
        
        logger.info(f"[D34_K8S_EVENTS] Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"kubectl failed: {result.stderr}")
        
        return json.loads(result.stdout)
    
    def _parse_events(self, events_data: Dict[str, Any]) -> List[K8sEvent]:
        """
        이벤트 JSON 파싱
        
        Args:
            events_data: kubectl get events JSON 데이터
        
        Returns:
            K8sEvent 목록
        """
        events = []
        items = events_data.get("items", [])
        
        for item in items:
            # 필터링: 레이블 선택자 또는 이름 접두사 매칭
            if not self._matches_selector(item):
                continue
            
            event = K8sEvent(
                type=item.get("type", ""),
                reason=item.get("reason", ""),
                message=item.get("message", ""),
                involved_kind=item.get("involvedObject", {}).get("kind"),
                involved_name=item.get("involvedObject", {}).get("name"),
                involved_namespace=item.get("involvedObject", {}).get("namespace"),
                first_timestamp=item.get("firstTimestamp"),
                last_timestamp=item.get("lastTimestamp"),
                count=item.get("count"),
                raw=item
            )
            events.append(event)
        
        return events
    
    def _matches_selector(self, item: Dict[str, Any]) -> bool:
        """
        이벤트가 선택자와 매칭되는지 확인
        
        Args:
            item: 이벤트 항목
        
        Returns:
            매칭 여부
        """
        # 관련 객체 이름 확인
        involved_name = item.get("involvedObject", {}).get("name", "")
        
        # 이름 접두사 매칭 (예: "arb-tuning-")
        if involved_name.startswith("arb-tuning-"):
            return True
        
        # 레이블 선택자 파싱 (간단한 구현)
        # 예: "app=arbitrage-tuning,session_id=..."
        selector_parts = self.label_selector.split(",")
        
        for part in selector_parts:
            if "=" not in part:
                continue
            
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            # 관련 객체의 레이블 확인
            labels = item.get("involvedObject", {}).get("labels", {})
            if labels.get(key) == value:
                return True
        
        return False
