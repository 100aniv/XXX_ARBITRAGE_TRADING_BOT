# -*- coding: utf-8 -*-
"""
D34 Kubernetes Health History Persistence (File-based, Read-Only)

건강 상태 스냅샷을 파일 기반 저장소에 저장합니다.
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from arbitrage.k8s_health import K8sHealthSnapshot, HealthLevel

logger = logging.getLogger(__name__)


@dataclass
class K8sHealthHistoryRecord:
    """건강 상태 히스토리 레코드"""
    timestamp: str                  # 레코드 타임스탬프
    namespace: str                  # K8s 네임스페이스
    selector: str                   # 레이블 선택자
    overall_health: HealthLevel     # 전체 건강 상태
    jobs_ok: int                    # OK 상태 Job 수
    jobs_warn: int                  # WARN 상태 Job 수
    jobs_error: int                 # ERROR 상태 Job 수
    raw_snapshot: Optional[Dict[str, Any]] = None  # 원본 스냅샷 (선택)


class K8sHealthHistoryStore:
    """건강 상태 히스토리 저장소"""
    
    def __init__(self, path: str):
        """
        건강 상태 히스토리 저장소 초기화
        
        Args:
            path: 히스토리 파일 경로 (예: 'outputs/k8s_health_history.jsonl')
        """
        self.path = path
        logger.info(f"[D34_K8S_HISTORY] Initialized history store: {path}")
    
    def append(self, snapshot: K8sHealthSnapshot) -> K8sHealthHistoryRecord:
        """
        건강 상태 스냅샷을 히스토리에 추가
        
        Args:
            snapshot: K8sHealthSnapshot
        
        Returns:
            K8sHealthHistoryRecord
        """
        # 건강 상태별 Job 수 계산
        jobs_ok = sum(1 for jh in snapshot.jobs_health if jh.health == "OK")
        jobs_warn = sum(1 for jh in snapshot.jobs_health if jh.health == "WARN")
        jobs_error = sum(1 for jh in snapshot.jobs_health if jh.health == "ERROR")
        
        record = K8sHealthHistoryRecord(
            timestamp=snapshot.timestamp,
            namespace=snapshot.namespace,
            selector=snapshot.selector,
            overall_health=snapshot.overall_health,
            jobs_ok=jobs_ok,
            jobs_warn=jobs_warn,
            jobs_error=jobs_error,
            raw_snapshot=None  # 저장소 크기 절약
        )
        
        # 파일에 JSON 라인 추가
        self._write_record(record)
        
        logger.info(
            f"[D34_K8S_HISTORY] Appended record: "
            f"health={record.overall_health}, "
            f"ok={record.jobs_ok}, warn={record.jobs_warn}, error={record.jobs_error}"
        )
        
        return record
    
    def load_recent(self, limit: int = 50) -> List[K8sHealthHistoryRecord]:
        """
        최근 N개 레코드 로드
        
        Args:
            limit: 로드할 최대 레코드 수
        
        Returns:
            K8sHealthHistoryRecord 목록 (오래된 것부터 최신 순)
        """
        if not os.path.exists(self.path):
            logger.info(f"[D34_K8S_HISTORY] History file not found: {self.path}")
            return []
        
        records = []
        
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        record = K8sHealthHistoryRecord(
                            timestamp=data.get("timestamp", ""),
                            namespace=data.get("namespace", ""),
                            selector=data.get("selector", ""),
                            overall_health=data.get("overall_health", "OK"),
                            jobs_ok=data.get("jobs_ok", 0),
                            jobs_warn=data.get("jobs_warn", 0),
                            jobs_error=data.get("jobs_error", 0),
                            raw_snapshot=data.get("raw_snapshot")
                        )
                        records.append(record)
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"[D34_K8S_HISTORY] Skipping corrupted line: {e}")
                        continue
        
        except IOError as e:
            logger.error(f"[D34_K8S_HISTORY] Error reading history file: {e}")
            return []
        
        # 최근 limit개만 반환
        return records[-limit:] if records else []
    
    def summarize(self, window: Optional[int] = None) -> Dict[str, Any]:
        """
        히스토리 요약
        
        Args:
            window: 고려할 최근 레코드 수 (None이면 전체)
        
        Returns:
            요약 정보 (JSON 호환)
        """
        records = self.load_recent(limit=window or 10000)
        
        if not records:
            return {
                "total_records": 0,
                "ok_count": 0,
                "warn_count": 0,
                "error_count": 0,
                "last_overall_health": None,
                "last_timestamp": None
            }
        
        # 건강 상태별 카운트
        ok_count = sum(1 for r in records if r.overall_health == "OK")
        warn_count = sum(1 for r in records if r.overall_health == "WARN")
        error_count = sum(1 for r in records if r.overall_health == "ERROR")
        
        last_record = records[-1]
        
        return {
            "total_records": len(records),
            "ok_count": ok_count,
            "warn_count": warn_count,
            "error_count": error_count,
            "last_overall_health": last_record.overall_health,
            "last_timestamp": last_record.timestamp,
            "last_jobs_ok": last_record.jobs_ok,
            "last_jobs_warn": last_record.jobs_warn,
            "last_jobs_error": last_record.jobs_error
        }
    
    def _write_record(self, record: K8sHealthHistoryRecord) -> None:
        """
        레코드를 파일에 JSON 라인으로 작성
        
        Args:
            record: K8sHealthHistoryRecord
        """
        # 디렉토리 생성 (필요시)
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"[D34_K8S_HISTORY] Created directory: {directory}")
        
        # JSON 라인 작성
        with open(self.path, 'a', encoding='utf-8') as f:
            line = json.dumps(asdict(record), ensure_ascii=False)
            f.write(line + '\n')
