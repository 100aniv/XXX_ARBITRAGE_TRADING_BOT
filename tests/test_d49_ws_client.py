"""
D49: WebSocket Client 테스트

BaseWebSocketClient의 연결, 재연결, 메시지 처리 기능을 검증한다.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from arbitrage.exchanges.ws_client import (
    BaseWebSocketClient,
    ReconnectBackoffConfig,
    WebSocketConnectionError,
    WebSocketTimeoutError,
    WebSocketProtocolError,
)


class MockWebSocketClient(BaseWebSocketClient):
    """테스트용 Mock WebSocket 클라이언트"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages_received = []
        self.subscribed_channels = []
    
    async def subscribe(self, channels: List[str]) -> None:
        """채널 구독"""
        self.subscribed_channels.extend(channels)
    
    def on_message(self, message: Dict[str, Any]) -> None:
        """메시지 핸들러"""
        self.messages_received.append(message)


class TestD49WebSocketClientBasics:
    """D49 WebSocket 클라이언트 기본 테스트"""
    
    def test_ws_client_initialization(self):
        """WebSocket 클라이언트 초기화"""
        url = "wss://api.example.com/ws"
        client = MockWebSocketClient(url)
        
        assert client.url == url
        assert client.is_connected is False
        assert client.is_running is False
        assert client.reconnect_config is not None
    
    def test_ws_client_custom_config(self):
        """사용자 정의 설정"""
        config = ReconnectBackoffConfig(
            initial=2.0,
            max=60.0,
            multiplier=3.0,
        )
        client = MockWebSocketClient(
            "wss://api.example.com/ws",
            reconnect_config=config,
            heartbeat_interval=60.0,
            timeout=20.0,
        )
        
        assert client.reconnect_config.initial == 2.0
        assert client.reconnect_config.max == 60.0
        assert client.heartbeat_interval == 60.0
        assert client.timeout == 20.0
    
    @pytest.mark.asyncio
    async def test_ws_connect_success(self):
        """연결 성공"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        
        with patch('arbitrage.exchanges.ws_client.asyncio.wait_for') as mock_wait:
            mock_wait.return_value = mock_ws
            
            await client.connect()
            
            assert client.is_connected is True
            assert client.ws is not None
    
    @pytest.mark.asyncio
    async def test_ws_connect_timeout(self):
        """연결 타임아웃"""
        client = MockWebSocketClient("wss://api.example.com/ws", timeout=1.0)
        
        with patch('arbitrage.exchanges.ws_client.asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(WebSocketTimeoutError):
                await client.connect()
    
    @pytest.mark.asyncio
    async def test_ws_disconnect(self):
        """연결 종료"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        client.ws = mock_ws
        client.is_connected = True
        
        await client.disconnect()
        
        assert client.is_connected is False
        mock_ws.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ws_send_message(self):
        """메시지 전송"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        client.ws = mock_ws
        client.is_connected = True
        
        message = {"type": "subscribe", "channels": ["orderbook"]}
        await client.send_message(message)
        
        mock_ws.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ws_send_message_not_connected(self):
        """연결되지 않은 상태에서 메시지 전송"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        client.is_connected = False
        
        message = {"type": "subscribe"}
        
        with pytest.raises(WebSocketConnectionError):
            await client.send_message(message)


class TestD49WebSocketReconnect:
    """D49 WebSocket 재연결 테스트"""
    
    def test_backoff_calculation_initial(self):
        """Exponential backoff 계산 (초기)"""
        config = ReconnectBackoffConfig(initial=1.0, max=30.0, multiplier=2.0)
        client = MockWebSocketClient(
            "wss://api.example.com/ws",
            reconnect_config=config,
        )
        
        # 첫 번째 재시도: 1.0 * 2^0 = 1.0
        client._reconnect_attempt = 0
        backoff = client._calculate_backoff()
        assert backoff == 1.0
    
    def test_backoff_calculation_exponential(self):
        """Exponential backoff 계산 (지수)"""
        config = ReconnectBackoffConfig(initial=1.0, max=30.0, multiplier=2.0)
        client = MockWebSocketClient(
            "wss://api.example.com/ws",
            reconnect_config=config,
        )
        
        # 두 번째 재시도: 1.0 * 2^1 = 2.0
        client._reconnect_attempt = 1
        backoff = client._calculate_backoff()
        assert backoff == 2.0
        
        # 세 번째 재시도: 1.0 * 2^2 = 4.0
        client._reconnect_attempt = 2
        backoff = client._calculate_backoff()
        assert backoff == 4.0
    
    def test_backoff_calculation_max(self):
        """Exponential backoff 계산 (최대값 제한)"""
        config = ReconnectBackoffConfig(initial=1.0, max=10.0, multiplier=2.0)
        client = MockWebSocketClient(
            "wss://api.example.com/ws",
            reconnect_config=config,
        )
        
        # 충분히 높은 재시도: 1.0 * 2^5 = 32.0 > 10.0
        client._reconnect_attempt = 5
        backoff = client._calculate_backoff()
        assert backoff == 10.0  # 최대값으로 제한


class TestD49WebSocketMessageHandling:
    """D49 WebSocket 메시지 처리 테스트"""
    
    def test_on_message_callback(self):
        """메시지 콜백"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        message = {"type": "orderbook", "data": {"bid": 100, "ask": 101}}
        client.on_message(message)
        
        assert len(client.messages_received) == 1
        assert client.messages_received[0] == message
    
    def test_on_error_callback(self):
        """에러 콜백"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        error = Exception("Test error")
        client.on_error(error)
        
        # 기본 구현: 로그만 남김
        # 실제 에러 처리는 구현체에서 오버라이드
    
    def test_on_reconnect_callback(self):
        """재연결 콜백"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        client.on_reconnect()
        
        # 기본 구현: 로그만 남김


class TestD49WebSocketErrorHandling:
    """D49 WebSocket 에러 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_json_parse_error(self):
        """JSON 파싱 에러"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            "invalid json {",  # 첫 번째: 잘못된 JSON
            asyncio.TimeoutError(),  # 두 번째: 타임아웃 (루프 종료)
        ]
        
        client.ws = mock_ws
        client.is_connected = True
        
        # receive_loop는 에러를 처리하고 계속 진행
        # (실제 구현에서는 백그라운드 태스크로 실행)
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """연결 에러 처리"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        with patch('arbitrage.exchanges.ws_client.asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = Exception("Connection refused")
            
            with pytest.raises(WebSocketConnectionError):
                await client.connect()


class TestD49WebSocketIntegration:
    """D49 WebSocket 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_subscribe_channels(self):
        """채널 구독"""
        client = MockWebSocketClient("wss://api.example.com/ws")
        
        channels = ["orderbook.KRW-BTC", "ticker.KRW-BTC"]
        await client.subscribe(channels)
        
        assert client.subscribed_channels == channels
    
    def test_reconnect_config_defaults(self):
        """재연결 설정 기본값"""
        config = ReconnectBackoffConfig()
        
        assert config.initial == 1.0
        assert config.max == 30.0
        assert config.multiplier == 2.0
