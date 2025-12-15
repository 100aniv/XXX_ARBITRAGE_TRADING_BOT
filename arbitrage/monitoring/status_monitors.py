# -*- coding: utf-8 -*-
"""
D27 Real-time Monitoring & Health Status

Live/Paper/Tuning 상태를 실시간으로 모니터링하는 모듈.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from arbitrage.state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class LiveStatusSnapshot:
    """Live/Paper 상태 스냅샷"""
    mode: str                           # "live" | "paper" | "shadow"
    env: str                            # "docker" | "local"
    live_enabled: bool
    live_armed: bool
    last_heartbeat: Optional[datetime]
    trades_total: Optional[int]
    trades_today: Optional[int]
    safety_violations_total: Optional[int]
    circuit_breaker_triggers_total: Optional[int]
    total_balance: Optional[float]
    available_balance: Optional[float]
    total_position_value: Optional[float]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class TuningStatusSnapshot:
    """튜닝 세션 상태 스냅샷"""
    session_id: str
    total_iterations: int
    completed_iterations: int
    workers: List[str]
    metrics_keys: List[str]
    last_update: Optional[datetime]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def progress_pct(self) -> float:
        """진행률 (%)"""
        if self.total_iterations == 0:
            return 0.0
        return (self.completed_iterations / self.total_iterations) * 100


class LiveStatusMonitor:
    """Live/Paper 상태 모니터"""
    
    def __init__(
        self,
        mode: str = "paper",
        env: str = "docker",
        state_manager: Optional[StateManager] = None
    ):
        """
        Args:
            mode: 모드 (live, paper, shadow)
            env: 환경 (docker, local)
            state_manager: StateManager (기본: 자동 생성)
        """
        self.mode = mode
        self.env = env
        
        # StateManager 초기화
        if state_manager:
            self.state_manager = state_manager
        else:
            namespace = f"{mode}:{env}"
            self.state_manager = StateManager(
                redis_host=os.getenv("REDIS_HOST", "localhost"),
                redis_port=int(os.getenv("REDIS_PORT", "6379")),
                redis_db=0,
                namespace=namespace,
                enabled=True,
                key_prefix="arbitrage"
            )
    
    def load_snapshot(self) -> LiveStatusSnapshot:
        """
        현재 Live/Paper 상태 스냅샷 로드
        
        Returns:
            LiveStatusSnapshot
        """
        try:
            # 포트폴리오 상태
            portfolio_state = self.state_manager.get_portfolio_state()
            total_balance = None
            available_balance = None
            total_position_value = None
            
            if portfolio_state:
                try:
                    total_balance = float(portfolio_state.get('total_balance', 0))
                    available_balance = float(portfolio_state.get('available_balance', 0))
                    total_position_value = float(portfolio_state.get('total_position_value', 0))
                except (ValueError, TypeError):
                    pass
            
            # 통계
            trades_total = int(self.state_manager.get_stat("trades_total") or 0)
            trades_today = int(self.state_manager.get_stat("trades_today") or 0)
            safety_violations_total = int(self.state_manager.get_stat("safety_violations_total") or 0)
            circuit_breaker_triggers = int(self.state_manager.get_stat("circuit_breaker_triggers_total") or 0)
            
            # 하트비트
            heartbeat_str = self.state_manager.get_heartbeat("trader")
            last_heartbeat = None
            if heartbeat_str:
                try:
                    last_heartbeat = datetime.fromisoformat(heartbeat_str)
                except (ValueError, TypeError):
                    pass
            
            # Live 상태 (D19/D20에서 설정)
            live_enabled = bool(self.state_manager.get_stat("live_enabled") or False)
            live_armed = bool(self.state_manager.get_stat("live_armed") or False)
            
            return LiveStatusSnapshot(
                mode=self.mode,
                env=self.env,
                live_enabled=live_enabled,
                live_armed=live_armed,
                last_heartbeat=last_heartbeat,
                trades_total=trades_total,
                trades_today=trades_today,
                safety_violations_total=safety_violations_total,
                circuit_breaker_triggers_total=circuit_breaker_triggers,
                total_balance=total_balance,
                available_balance=available_balance,
                total_position_value=total_position_value
            )
        
        except Exception as e:
            logger.error(f"Failed to load Live status snapshot: {e}")
            # 빈 스냅샷 반환
            return LiveStatusSnapshot(
                mode=self.mode,
                env=self.env,
                live_enabled=False,
                live_armed=False,
                last_heartbeat=None,
                trades_total=None,
                trades_today=None,
                safety_violations_total=None,
                circuit_breaker_triggers_total=None,
                total_balance=None,
                available_balance=None,
                total_position_value=None
            )


class TuningStatusMonitor:
    """튜닝 세션 상태 모니터"""
    
    def __init__(
        self,
        session_id: str,
        total_iterations: int,
        env: str = "docker",
        mode: str = "paper",
        state_manager: Optional[StateManager] = None
    ):
        """
        Args:
            session_id: 세션 ID
            total_iterations: 총 반복 수
            env: 환경 (docker, local)
            mode: 모드 (paper, shadow, live)
            state_manager: StateManager (기본: 자동 생성)
        """
        self.session_id = session_id
        self.total_iterations = total_iterations
        self.env = env
        self.mode = mode
        
        # StateManager 초기화
        if state_manager:
            self.state_manager = state_manager
        else:
            namespace = f"tuning:{env}:{mode}"
            self.state_manager = StateManager(
                redis_host=os.getenv("REDIS_HOST", "localhost"),
                redis_port=int(os.getenv("REDIS_PORT", "6379")),
                redis_db=0,
                namespace=namespace,
                enabled=True,
                key_prefix="arbitrage"
            )
    
    def load_snapshot(self) -> TuningStatusSnapshot:
        """
        현재 튜닝 세션 상태 스냅샷 로드
        
        Returns:
            TuningStatusSnapshot
        """
        try:
            from arbitrage.tuning import build_tuning_key
            
            # Redis에서 tuning_session:{session_id}:worker:*:iteration:* 패턴 스캔
            completed_iterations = set()
            workers = set()
            metrics_keys = set()
            last_update = None
            
            if self.state_manager._redis_connected and self.state_manager._redis:
                try:
                    # 패턴: tuning_session:{session_id}:worker:*:iteration:*
                    pattern = f"*tuning_session:{self.session_id}:worker:*:iteration:*"
                    keys = self.state_manager._redis.keys(pattern)
                    
                    for key in keys:
                        # 키에서 worker_id와 iteration 추출
                        parts = key.split(":")
                        try:
                            worker_idx = parts.index("worker")
                            iteration_idx = parts.index("iteration")
                            
                            if worker_idx + 1 < len(parts) and iteration_idx + 1 < len(parts):
                                worker_id = parts[worker_idx + 1]
                                iteration = parts[iteration_idx + 1]
                                
                                workers.add(worker_id)
                                completed_iterations.add((worker_id, iteration))
                                
                                # 메트릭 키 수집
                                data = self.state_manager._redis.hgetall(key)
                                if data:
                                    # timestamp 업데이트
                                    if "timestamp" in data:
                                        try:
                                            ts = datetime.fromisoformat(data["timestamp"])
                                            if last_update is None or ts > last_update:
                                                last_update = ts
                                        except (ValueError, TypeError):
                                            pass
                        except (ValueError, IndexError):
                            pass
                
                except Exception as e:
                    logger.warning(f"Failed to scan Redis keys: {e}")
            else:
                # in-memory fallback
                for key, value in self.state_manager._in_memory_store.items():
                    if f"tuning_session:{self.session_id}" in key and "worker:" in key and "iteration:" in key:
                        parts = key.split(":")
                        try:
                            worker_idx = parts.index("worker")
                            iteration_idx = parts.index("iteration")
                            
                            if worker_idx + 1 < len(parts) and iteration_idx + 1 < len(parts):
                                worker_id = parts[worker_idx + 1]
                                iteration = parts[iteration_idx + 1]
                                
                                workers.add(worker_id)
                                completed_iterations.add((worker_id, iteration))
                        except (ValueError, IndexError):
                            pass
            
            return TuningStatusSnapshot(
                session_id=self.session_id,
                total_iterations=self.total_iterations,
                completed_iterations=len(completed_iterations),
                workers=sorted(list(workers)),
                metrics_keys=sorted(list(metrics_keys)),
                last_update=last_update
            )
        
        except Exception as e:
            logger.error(f"Failed to load Tuning status snapshot: {e}")
            # 빈 스냅샷 반환
            return TuningStatusSnapshot(
                session_id=self.session_id,
                total_iterations=self.total_iterations,
                completed_iterations=0,
                workers=[],
                metrics_keys=[],
                last_update=None
            )
