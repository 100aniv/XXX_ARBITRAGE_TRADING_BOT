# -*- coding: utf-8 -*-
"""
D84-1: Fill Event Collector

목적:
    PAPER 실행 중 Fill 이벤트를 수집하여 JSONL 파일로 저장.
    Fill Model v1 보정을 위한 실측 데이터 수집 인프라.

특징:
    - 최소 침습: enable flag로 on/off 가능
    - JSONL 형식: 스트리밍 append, 대용량 데이터 처리 가능
    - Thread-safe: 여러 Executor에서 동시 호출 가능

Author: arbitrage-lite project
Date: 2025-12-06
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from threading import Lock

from arbitrage.types import OrderSide

logger = logging.getLogger(__name__)


@dataclass
class FillEvent:
    """
    Fill Event 데이터 구조
    
    Attributes:
        timestamp: 이벤트 발생 시각 (ISO format)
        session_id: 세션 식별자
        symbol: 거래 심볼 (예: "BTC/USDT")
        side: 주문 방향 (BUY or SELL)
        entry_bps: Entry Threshold (bps)
        tp_bps: TP Threshold (bps)
        order_quantity: 주문 수량
        filled_quantity: 체결 수량
        fill_ratio: 체결률 (0.0 ~ 1.0)
        slippage_bps: 슬리피지 (basis points)
        available_volume: 호가 잔량 (추정치)
        spread_bps: 스프레드 (bps)
        exit_reason: 퇴출 이유 (예: "take_profit", "time_limit")
        latency_ms: 체결 소요 시간 (ms, 알 수 없으면 None)
    """
    timestamp: str
    session_id: str
    symbol: str
    side: str
    entry_bps: float
    tp_bps: float
    order_quantity: float
    filled_quantity: float
    fill_ratio: float
    slippage_bps: float
    available_volume: float
    spread_bps: float
    exit_reason: str
    latency_ms: Optional[float]


class FillEventCollector:
    """
    Fill Event Collector
    
    PAPER 실행 중 Fill 이벤트를 수집하여 JSONL 파일로 저장.
    
    특징:
        - 선택적 활성화: enabled flag로 on/off
        - Thread-safe: Lock으로 동시 쓰기 보호
        - JSONL 형식: 스트리밍 append
    
    Args:
        output_path: JSONL 출력 파일 경로
        enabled: 수집 활성화 여부 (기본: False)
        session_id: 세션 식별자 (기본: 현재 시각)
    """
    
    def __init__(
        self,
        output_path: Path,
        enabled: bool = False,
        session_id: Optional[str] = None,
    ):
        """
        FillEventCollector 초기화
        
        Args:
            output_path: JSONL 출력 파일 경로
            enabled: 수집 활성화 여부
            session_id: 세션 식별자
        """
        self.output_path = Path(output_path)
        self.enabled = enabled
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.lock = Lock()
        self.events_count = 0
        
        if self.enabled:
            # 출력 디렉토리 생성
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(
                f"[D84-1_FILL_EVENT_COLLECTOR] 초기화: "
                f"session={self.session_id}, "
                f"output={self.output_path}"
            )
    
    def record_fill_event(
        self,
        symbol: str,
        side: OrderSide,
        entry_bps: float,
        tp_bps: float,
        order_quantity: float,
        filled_quantity: float,
        fill_ratio: float,
        slippage_bps: float,
        available_volume: float = 0.0,
        spread_bps: float = 0.0,
        exit_reason: str = "unknown",
        latency_ms: Optional[float] = None,
    ):
        """
        Fill 이벤트 기록
        
        Args:
            symbol: 거래 심볼
            side: 주문 방향
            entry_bps: Entry Threshold
            tp_bps: TP Threshold
            order_quantity: 주문 수량
            filled_quantity: 체결 수량
            fill_ratio: 체결률
            slippage_bps: 슬리피지
            available_volume: 호가 잔량
            spread_bps: 스프레드
            exit_reason: 퇴출 이유
            latency_ms: 체결 소요 시간
        """
        if not self.enabled:
            return
        
        event = FillEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=self.session_id,
            symbol=symbol,
            side=side.value,
            entry_bps=entry_bps,
            tp_bps=tp_bps,
            order_quantity=order_quantity,
            filled_quantity=filled_quantity,
            fill_ratio=fill_ratio,
            slippage_bps=slippage_bps,
            available_volume=available_volume,
            spread_bps=spread_bps,
            exit_reason=exit_reason,
            latency_ms=latency_ms,
        )
        
        # Thread-safe write
        with self.lock:
            try:
                with open(self.output_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(event)) + "\n")
                self.events_count += 1
                
                if self.events_count % 100 == 0:
                    logger.info(
                        f"[D84-1_FILL_EVENT_COLLECTOR] {self.events_count} events recorded"
                    )
            except Exception as e:
                logger.error(
                    f"[D84-1_FILL_EVENT_COLLECTOR] Failed to write event: {e}"
                )
    
    def get_summary(self) -> dict:
        """
        수집 통계 요약
        
        Returns:
            events_count, session_id, output_path 등
        """
        return {
            "enabled": self.enabled,
            "session_id": self.session_id,
            "events_count": self.events_count,
            "output_path": str(self.output_path),
        }
