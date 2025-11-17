#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Long-Run Stability Testing Framework (PHASE D12 + D14)
======================================================

24h~72h 장시간 운영 안정성 테스트 및 모니터링.

특징:
- 주기적 스냅샷 저장 (메모리, CPU, WS, Redis, 루프 지연 등)
- 체크포인트 기반 상태 추적
- JSON 형식 로그 저장
- D14: 거래/리스크 이벤트 히스토리 (JSONL)
- D14: 드리프트 추적 (메모리, WS, Redis)
- 비블로킹 통합 (run_live.py에 선택적)
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class StabilityCheckpoint:
    """안정성 체크포인트"""
    timestamp: str                      # ISO 8601 형식
    loop_count: int                     # 루프 카운트
    
    # 시스템 리소스
    cpu_pct: float = 0.0               # CPU 사용률 (%)
    rss_mb: float = 0.0                # 메모리 (MB)
    open_files: int = 0                # 열린 파일 수
    num_threads: int = 0               # 스레드 수
    
    # 네트워크 상태
    ws_lag_ms: float = 0.0             # WebSocket 지연 (ms)
    ws_freshness_ok: bool = True       # WebSocket 신선도 OK
    redis_heartbeat_age_ms: float = 0.0  # Redis heartbeat 나이 (ms)
    redis_ok: bool = True              # Redis 상태 OK
    
    # 루프 성능
    loop_latency_ms: float = 0.0       # 루프 지연 (ms)
    loop_latency_p95_ms: float = 0.0   # 루프 지연 P95 (ms)
    
    # 거래 상태
    num_live_trades: int = 0           # 실거래 수
    num_paper_trades: int = 0          # 모의거래 수
    num_open_positions: int = 0        # 열린 포지션 수
    total_exposure_krw: float = 0.0    # 총 노출도 (KRW)
    
    # 손절매 상태
    stoploss_triggers: int = 0         # 손절매 발동 수
    
    # 워치독 상태
    watchdog_healthy: bool = True      # 워치독 상태 OK
    watchdog_alerts: int = 0           # 워치독 경고 수
    watchdog_consecutive_errors: int = 0  # 연속 에러 수
    
    # 안전 검증
    safety_rejections: int = 0         # 안전 검증 거부 수
    
    # 상태 요약
    is_stable: bool = True             # 전체 안정 상태


class LongRunTester:
    """장시간 운영 안정성 테스터"""
    
    def __init__(
        self,
        enabled: bool = True,
        interval_loops: int = 50,
        snapshot_path: str = "logs/stability"
    ):
        """
        Args:
            enabled: 테스터 활성화 여부
            interval_loops: 스냅샷 저장 간격 (루프 수)
            snapshot_path: 스냅샷 저장 경로
        """
        self.enabled = enabled
        self.interval_loops = interval_loops
        self.snapshot_path = Path(snapshot_path)
        self.loop_count = 0
        self.checkpoints: List[StabilityCheckpoint] = []
        self.last_snapshot_loop = 0
        
        # 루프 지연 히스토리 (P95 계산용)
        self.loop_latency_history: List[float] = []
        self.max_history_size = 100
        
        # D14: 드리프트 추적
        self.memory_history: List[float] = []
        self.ws_lag_history: List[float] = []
        self.redis_age_history: List[float] = []
        self.event_log_file: Optional[Path] = None
        
        if self.enabled:
            self.snapshot_path.mkdir(parents=True, exist_ok=True)
            # D14: 이벤트 로그 파일 초기화
            timestamp = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('.', '-')
            self.event_log_file = self.snapshot_path / f"longrun_events_{timestamp}.jsonl"
            logger.info(f"[LongRunTester] Enabled (interval={interval_loops} loops, path={snapshot_path})")
        else:
            logger.info("[LongRunTester] Disabled")
    
    def record_loop(self, loop_latency_ms: float) -> None:
        """루프 기록"""
        self.loop_count += 1
        
        # 루프 지연 히스토리 업데이트
        self.loop_latency_history.append(loop_latency_ms)
        if len(self.loop_latency_history) > self.max_history_size:
            self.loop_latency_history.pop(0)
    
    def get_loop_latency_p95(self) -> float:
        """루프 지연 P95 계산"""
        if not self.loop_latency_history:
            return 0.0
        
        sorted_latencies = sorted(self.loop_latency_history)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    def take_checkpoint(self, metrics: Dict[str, Any]) -> Optional[StabilityCheckpoint]:
        """
        체크포인트 생성
        
        Args:
            metrics: MetricsCollector.get_all_metrics() 결과
        
        Returns:
            StabilityCheckpoint 또는 None
        """
        if not self.enabled:
            return None
        
        # 스냅샷 간격 확인
        if self.loop_count - self.last_snapshot_loop < self.interval_loops:
            return None
        
        self.last_snapshot_loop = self.loop_count
        
        # 체크포인트 생성
        checkpoint = StabilityCheckpoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            loop_count=self.loop_count,
            
            # 시스템 리소스
            cpu_pct=metrics.get("cpu_pct", 0.0),
            rss_mb=metrics.get("rss_mb", 0.0),
            open_files=metrics.get("open_files", 0),
            num_threads=metrics.get("num_threads", 0),
            
            # 네트워크 상태
            ws_lag_ms=metrics.get("ws_lag_ms", 0.0),
            ws_freshness_ok=metrics.get("ws_lag_ms", 0.0) < 5000.0,
            redis_heartbeat_age_ms=metrics.get("redis_heartbeat_age_ms", 0.0),
            redis_ok=metrics.get("redis_heartbeat_age_ms", 0.0) < 30000.0,
            
            # 루프 성능
            loop_latency_ms=metrics.get("loop_latency_ms", 0.0),
            loop_latency_p95_ms=self.get_loop_latency_p95(),
            
            # 거래 상태
            num_live_trades=metrics.get("num_live_trades_today", 0),
            num_paper_trades=metrics.get("num_paper_trades_today", 0),
            num_open_positions=metrics.get("num_open_positions", 0),
            total_exposure_krw=metrics.get("total_exposure_krw", 0.0),
            
            # 손절매 상태
            stoploss_triggers=metrics.get("stoploss_triggers", 0),
            
            # 워치독 상태
            watchdog_healthy=metrics.get("watchdog_healthy", True),
            watchdog_alerts=metrics.get("watchdog_alerts", 0),
            watchdog_consecutive_errors=metrics.get("watchdog_consecutive_errors", 0),
            
            # 안전 검증
            safety_rejections=metrics.get("safety_rejections_count", 0),
        )
        
        # 안정성 판단
        checkpoint.is_stable = (
            checkpoint.ws_freshness_ok and
            checkpoint.redis_ok and
            checkpoint.watchdog_healthy and
            checkpoint.loop_latency_ms < 5000.0
        )
        
        self.checkpoints.append(checkpoint)
        
        # 스냅샷 저장
        self._save_snapshot(checkpoint)
        
        return checkpoint
    
    def _save_snapshot(self, checkpoint: StabilityCheckpoint) -> None:
        """스냅샷을 JSON 파일로 저장"""
        try:
            # 파일명: snapshot_<timestamp>.json
            timestamp_str = checkpoint.timestamp.replace(":", "-").replace(".", "-")
            filename = f"snapshot_{timestamp_str}.json"
            filepath = self.snapshot_path / filename
            
            # JSON 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(checkpoint), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"[LongRunTester] Snapshot saved: {filename}")
        
        except Exception as e:
            logger.error(f"[LongRunTester] Failed to save snapshot: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """현재 요약 정보"""
        if not self.checkpoints:
            return {
                'total_checkpoints': 0,
                'total_loops': self.loop_count,
                'stable_checkpoints': 0,
                'stability_rate': 0.0
            }
        
        stable_count = sum(1 for cp in self.checkpoints if cp.is_stable)
        
        return {
            'total_checkpoints': len(self.checkpoints),
            'total_loops': self.loop_count,
            'stable_checkpoints': stable_count,
            'stability_rate': stable_count / len(self.checkpoints) * 100.0,
            'latest_checkpoint': asdict(self.checkpoints[-1])
        }
    
    def get_stats_for_metrics(self) -> Dict[str, Any]:
        """메트릭 시스템에 통합할 통계"""
        if not self.checkpoints:
            return {
                'longrun_checkpoints': 0,
                'longrun_stability_rate': 0.0
            }
        
        stable_count = sum(1 for cp in self.checkpoints if cp.is_stable)
        
        return {
            'longrun_checkpoints': len(self.checkpoints),
            'longrun_stability_rate': stable_count / len(self.checkpoints) * 100.0
        }
    
    # ========== D14: 드리프트 추적 및 이벤트 로깅 ==========
    
    def record_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        거래/리스크 이벤트 기록 (JSONL 형식)
        
        Args:
            event_type: 이벤트 유형 (trade, risk_block, rebalance, failclosed 등)
            event_data: 이벤트 데이터
        """
        if not self.enabled or not self.event_log_file:
            return
        
        try:
            event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'loop_count': self.loop_count,
                'event_type': event_type,
                'data': event_data
            }
            
            with open(self.event_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        
        except Exception as e:
            logger.error(f"[LongRunTester] Failed to record event: {e}")
    
    def update_drift_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        드리프트 메트릭 업데이트
        
        Args:
            metrics: 메트릭 딕셔너리
        """
        if not self.enabled:
            return
        
        # 히스토리 업데이트 (최대 1000개 유지)
        self.memory_history.append(metrics.get('rss_mb', 0.0))
        self.ws_lag_history.append(metrics.get('ws_lag_ms', 0.0))
        self.redis_age_history.append(metrics.get('redis_heartbeat_age_ms', 0.0))
        
        max_size = 1000
        if len(self.memory_history) > max_size:
            self.memory_history.pop(0)
        if len(self.ws_lag_history) > max_size:
            self.ws_lag_history.pop(0)
        if len(self.redis_age_history) > max_size:
            self.redis_age_history.pop(0)
    
    def get_drift_rate(self, metric_name: str) -> float:
        """
        드리프트 비율 계산 (d/dt)
        
        Args:
            metric_name: 메트릭 이름 (memory, ws_lag, redis_age)
        
        Returns:
            드리프트 비율 (단위/루프)
        """
        if metric_name == 'memory':
            history = self.memory_history
        elif metric_name == 'ws_lag':
            history = self.ws_lag_history
        elif metric_name == 'redis_age':
            history = self.redis_age_history
        else:
            return 0.0
        
        if len(history) < 10:
            return 0.0
        
        # 최근 10개 평균 vs 이전 10개 평균
        recent_avg = sum(history[-10:]) / 10
        older_avg = sum(history[-20:-10]) / 10
        
        if older_avg == 0:
            return 0.0
        
        return (recent_avg - older_avg) / older_avg
    
    def check_latency_degradation(self, threshold_hours: float = 2.0) -> bool:
        """
        루프 지연 악화 감지 (2시간 이상)
        
        Args:
            threshold_hours: 임계값 (시간)
        
        Returns:
            악화 감지 여부
        """
        if len(self.loop_latency_history) < 100:
            return False
        
        # 최근 50개 vs 이전 50개 비교
        recent_avg = sum(self.loop_latency_history[-50:]) / 50
        older_avg = sum(self.loop_latency_history[-100:-50]) / 50
        
        # 50% 이상 악화 감지
        return recent_avg > older_avg * 1.5
