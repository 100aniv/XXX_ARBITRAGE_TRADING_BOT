"""
D49: WebSocket Client 베이스 클래스

WebSocket 연결/재연결, 메시지 수신, 에러 처리를 담당하는 추상 베이스 클래스.

라이브러리: websockets (표준 라이브러리 기반, 가볍고 안정적)

특징:
- 자동 재연결 (exponential backoff)
- ping/pong 및 heartbeat 관리
- 에러 분류 (네트워크/프로토콜/서버)
- 종료 신호 처리 (graceful shutdown)
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ReconnectBackoffConfig:
    """재연결 백오프 설정"""
    initial: float = 1.0      # 초기 대기 시간 (초)
    max: float = 30.0         # 최대 대기 시간 (초)
    multiplier: float = 2.0   # exponential backoff 배수


class WebSocketError(Exception):
    """WebSocket 에러 베이스 클래스"""
    pass


class WebSocketConnectionError(WebSocketError):
    """연결 에러"""
    pass


class WebSocketProtocolError(WebSocketError):
    """프로토콜 에러"""
    pass


class WebSocketTimeoutError(WebSocketError):
    """타임아웃 에러"""
    pass


class BaseWebSocketClient(ABC):
    """
    WebSocket 클라이언트 베이스 클래스
    
    책임:
    - 연결/재연결 관리
    - ping/pong 및 heartbeat
    - 메시지 수신 루프
    - 에러 처리 및 분류
    
    사용 예:
        client = UpbitWebSocketClient(...)
        await client.connect()
        await client.subscribe(["orderbook.KRW-BTC"])
        asyncio.create_task(client.receive_loop())
        # 메시지는 on_message() 콜백으로 전달됨
    """
    
    def __init__(
        self,
        url: str,
        reconnect_config: Optional[ReconnectBackoffConfig] = None,
        heartbeat_interval: float = 30.0,
        timeout: float = 10.0,
    ):
        """
        Args:
            url: WebSocket URL (예: wss://api.upbit.com/websocket/v1)
            reconnect_config: 재연결 백오프 설정
            heartbeat_interval: heartbeat 간격 (초)
            timeout: 연결 타임아웃 (초)
        """
        self.url = url
        self.reconnect_config = reconnect_config or ReconnectBackoffConfig()
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        
        self.ws = None
        self.is_connected = False
        self.is_running = False
        self._reconnect_attempt = 0
        self._last_heartbeat = time.time()
    
    @abstractmethod
    async def subscribe(self, channels: List[str]) -> None:
        """
        채널 구독
        
        Args:
            channels: 구독할 채널 목록
        """
        pass
    
    @abstractmethod
    def on_message(self, message: Dict[str, Any]) -> None:
        """
        메시지 핸들러 (구현체에서 오버라이드)
        
        Args:
            message: 수신한 메시지 (JSON 파싱됨)
        """
        pass
    
    def on_error(self, error: Exception) -> None:
        """
        에러 핸들러 (선택적 오버라이드)
        
        Args:
            error: 발생한 에러
        """
        logger.error(f"[D49_WS] Error: {error}")
    
    def on_reconnect(self) -> None:
        """
        재연결 핸들러 (선택적 오버라이드)
        """
        logger.info(f"[D49_WS] Reconnected to {self.url}")
    
    async def connect(self) -> None:
        """
        WebSocket 연결
        
        Raises:
            WebSocketConnectionError: 연결 실패
        """
        try:
            logger.info(f"[D49_WS] Connecting to {self.url}")
            
            # websockets 라이브러리 사용
            try:
                import websockets
            except ImportError:
                raise ImportError(
                    "websockets 라이브러리가 필요합니다. "
                    "pip install websockets 를 실행하세요."
                )
            
            self.ws = await asyncio.wait_for(
                websockets.connect(self.url),
                timeout=self.timeout,
            )
            
            self.is_connected = True
            self._reconnect_attempt = 0
            self._last_heartbeat = time.time()
            
            logger.info(f"[D49_WS] Connected to {self.url}")
            logger.debug(f"[D49_WS_DEBUG] Connection successful, ws object: {type(self.ws)}")
        
        except asyncio.TimeoutError:
            raise WebSocketTimeoutError(f"Connection timeout: {self.url}")
        except Exception as e:
            raise WebSocketConnectionError(f"Connection failed: {e}")
    
    async def disconnect(self) -> None:
        """
        WebSocket 종료
        """
        try:
            self.is_running = False
            if self.ws:
                await self.ws.close()
            self.is_connected = False
            logger.info(f"[D49_WS] Disconnected from {self.url}")
        except Exception as e:
            logger.error(f"[D49_WS] Disconnect error: {e}")
    
    async def receive_loop(self) -> None:
        """
        메시지 수신 루프 (백그라운드)
        
        - 자동 재연결 (exponential backoff)
        - heartbeat 관리
        - 메시지 파싱 및 콜백
        """
        self.is_running = True
        
        while self.is_running:
            try:
                if not self.is_connected:
                    await self._reconnect()
                
                # 메시지 수신
                raw_message = await asyncio.wait_for(
                    self.ws.recv(),
                    timeout=self.timeout,
                )
                
                # D83-1.6 DEBUG: raw 메시지 정보
                logger.debug(
                    f"[D49_WS_DEBUG] Received message: type={type(raw_message)}, "
                    f"len={len(raw_message) if isinstance(raw_message, (str, bytes)) else 'N/A'}"
                )
                
                # D83-1.6 FIX: bytes를 str로 변환 (Upbit은 binary로 메시지 전송)
                if isinstance(raw_message, bytes):
                    try:
                        message_str = raw_message.decode('utf-8')
                        logger.debug(f"[D49_WS_DEBUG] Decoded bytes to UTF-8: {message_str[:100]}...")
                    except UnicodeDecodeError as e:
                        logger.error(f"[D49_WS] Failed to decode bytes message: {e}")
                        continue
                else:
                    message_str = raw_message
                
                # JSON 파싱
                try:
                    message = json.loads(message_str)
                    logger.debug(f"[D49_WS_DEBUG] Parsed JSON message: keys={list(message.keys())}")
                    self.on_message(message)
                    self._last_heartbeat = time.time()
                except json.JSONDecodeError as e:
                    logger.error(f"[D49_WS] JSON parse error: {e}")
                    self.on_error(WebSocketProtocolError(f"Invalid JSON: {e}"))
            
            except asyncio.TimeoutError:
                # heartbeat 체크
                if time.time() - self._last_heartbeat > self.heartbeat_interval * 2:
                    logger.warning(f"[D49_WS] Heartbeat timeout")
                    await self.disconnect()
            
            except Exception as e:
                logger.error(f"[D49_WS] Receive error: {e}")
                self.on_error(e)
                await self.disconnect()
    
    async def _reconnect(self) -> None:
        """
        자동 재연결 (exponential backoff)
        """
        backoff_time = self._calculate_backoff()
        
        logger.warning(
            f"[D49_WS] Reconnecting in {backoff_time:.1f}s "
            f"(attempt {self._reconnect_attempt + 1})"
        )
        
        await asyncio.sleep(backoff_time)
        
        try:
            await self.connect()
            self.on_reconnect()
        except WebSocketConnectionError:
            self._reconnect_attempt += 1
            # 다음 루프에서 재시도
    
    def _calculate_backoff(self) -> float:
        """
        Exponential backoff 시간 계산
        
        공식: initial * (multiplier ^ attempt)
        최대값: max
        """
        backoff = (
            self.reconnect_config.initial *
            (self.reconnect_config.multiplier ** self._reconnect_attempt)
        )
        return min(backoff, self.reconnect_config.max)
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """
        메시지 전송
        
        Args:
            message: 전송할 메시지 (dict)
        """
        if not self.is_connected:
            raise WebSocketConnectionError("Not connected")
        
        try:
            message_str = json.dumps(message)
            logger.debug(f"[D49_WS_DEBUG] Sending message: {message_str[:200]}..." if len(message_str) > 200 else f"[D49_WS_DEBUG] Sending message: {message_str}")
            await self.ws.send(message_str)
        except Exception as e:
            logger.error(f"[D49_WS] Send error: {e}")
            raise WebSocketProtocolError(f"Send failed: {e}")
