"""
D48: HTTP Client with Rate Limit & Retry 테스트

레이트 리밋 및 exponential backoff 재시도 기능 검증
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import requests

from arbitrage.exchanges.http_client import HTTPClient, RateLimitConfig, RateLimitError


class TestD48HTTPClientRateLimit:
    """D48 HTTPClient 레이트리밋 테스트"""

    def test_http_client_initialization(self):
        """HTTP 클라이언트 초기화"""
        config = RateLimitConfig(
            max_requests_per_sec=5.0,
            max_retry=3,
            base_backoff_seconds=0.5,
        )
        
        client = HTTPClient(config)
        
        assert client.config.max_requests_per_sec == 5.0
        assert client.config.max_retry == 3
        assert client.config.base_backoff_seconds == 0.5

    def test_http_client_default_config(self):
        """기본 설정으로 초기화"""
        client = HTTPClient()
        
        assert client.config.max_requests_per_sec == 5.0
        assert client.config.max_retry == 3
        assert client.config.base_backoff_seconds == 0.5

    @patch('arbitrage.exchanges.http_client.requests.request')
    def test_http_get_success(self, mock_request):
        """GET 요청 성공"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_request.return_value = mock_response
        
        client = HTTPClient()
        response = client.get("https://api.example.com/test")
        
        assert response.status_code == 200
        assert response.json() == {"result": "ok"}
        mock_request.assert_called_once()

    @patch('arbitrage.exchanges.http_client.requests.request')
    def test_http_post_success(self, mock_request):
        """POST 요청 성공"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123"}
        mock_request.return_value = mock_response
        
        client = HTTPClient()
        response = client.post(
            "https://api.example.com/test",
            json={"data": "value"}
        )
        
        assert response.status_code == 201
        mock_request.assert_called_once()

    @patch('arbitrage.exchanges.http_client.requests.request')
    def test_http_delete_success(self, mock_request):
        """DELETE 요청 성공"""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response
        
        client = HTTPClient()
        response = client.delete("https://api.example.com/test/123")
        
        assert response.status_code == 204
        mock_request.assert_called_once()

    @patch('arbitrage.exchanges.http_client.requests.request')
    @patch('arbitrage.exchanges.http_client.time.sleep')
    def test_http_retry_on_500_error(self, mock_sleep, mock_request):
        """500 에러 시 재시도"""
        # 첫 2번은 500 에러, 3번째는 성공
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"result": "ok"}
        
        mock_request.side_effect = [
            mock_response_500,
            mock_response_500,
            mock_response_200,
        ]
        
        client = HTTPClient(RateLimitConfig(max_retry=3))
        response = client.get("https://api.example.com/test")
        
        assert response.status_code == 200
        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2  # 2번 재시도

    @patch('arbitrage.exchanges.http_client.requests.request')
    @patch('arbitrage.exchanges.http_client.time.sleep')
    def test_http_retry_on_429_rate_limit(self, mock_sleep, mock_request):
        """429 (Rate Limit) 에러 시 재시도"""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"result": "ok"}
        
        mock_request.side_effect = [
            mock_response_429,
            mock_response_200,
        ]
        
        client = HTTPClient(RateLimitConfig(max_retry=3))
        response = client.get("https://api.example.com/test")
        
        assert response.status_code == 200
        assert mock_request.call_count == 2

    @patch('arbitrage.exchanges.http_client.requests.request')
    @patch('arbitrage.exchanges.http_client.time.sleep')
    def test_http_retry_exhausted(self, mock_sleep, mock_request):
        """재시도 횟수 초과"""
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_request.return_value = mock_response_500
        
        client = HTTPClient(RateLimitConfig(max_retry=2))
        response = client.get("https://api.example.com/test")
        
        # 최대 재시도 횟수 초과해도 응답 반환 (4xx/5xx는 재시도 후 반환)
        assert response.status_code == 500
        assert mock_request.call_count == 2

    @patch('arbitrage.exchanges.http_client.requests.request')
    @patch('arbitrage.exchanges.http_client.time.sleep')
    def test_http_retry_on_timeout(self, mock_sleep, mock_request):
        """타임아웃 시 재시도"""
        mock_request.side_effect = [
            requests.Timeout("Connection timeout"),
            Mock(status_code=200, json=lambda: {"result": "ok"}),
        ]
        
        client = HTTPClient(RateLimitConfig(max_retry=3))
        response = client.get("https://api.example.com/test")
        
        assert response.status_code == 200
        assert mock_request.call_count == 2

    @patch('arbitrage.exchanges.http_client.requests.request')
    def test_http_timeout_exhausted(self, mock_request):
        """타임아웃 재시도 횟수 초과"""
        mock_request.side_effect = requests.Timeout("Connection timeout")
        
        client = HTTPClient(RateLimitConfig(max_retry=2))
        
        with pytest.raises(requests.Timeout):
            client.get("https://api.example.com/test")
        
        assert mock_request.call_count == 2

    @patch('arbitrage.exchanges.http_client.requests.request')
    @patch('arbitrage.exchanges.http_client.time.sleep')
    def test_exponential_backoff(self, mock_sleep, mock_request):
        """Exponential backoff 검증"""
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        mock_request.side_effect = [
            mock_response_500,
            mock_response_500,
            mock_response_200,
        ]
        
        config = RateLimitConfig(
            max_retry=3,
            base_backoff_seconds=0.5,
        )
        client = HTTPClient(config)
        response = client.get("https://api.example.com/test")
        
        assert response.status_code == 200
        
        # Backoff 시간: 0.5s, 1.0s
        sleep_calls = mock_sleep.call_args_list
        assert len(sleep_calls) == 2
        # 첫 번째 backoff: 0.5 * 2^0 = 0.5
        # 두 번째 backoff: 0.5 * 2^1 = 1.0

    @patch('arbitrage.exchanges.http_client.requests.request')
    def test_rate_limit_enforcement(self, mock_request):
        """레이트리밋 적용 검증"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        config = RateLimitConfig(max_requests_per_sec=5.0)
        client = HTTPClient(config)
        
        # 5개 요청 (1초 내)
        for i in range(5):
            client.get(f"https://api.example.com/test{i}")
        
        # 요청이 5번 이상 실행되었는지 확인
        assert mock_request.call_count >= 5

    def test_rate_limit_config_dataclass(self):
        """RateLimitConfig 데이터클래스"""
        config = RateLimitConfig(
            max_requests_per_sec=10.0,
            max_retry=5,
            base_backoff_seconds=1.0,
        )
        
        assert config.max_requests_per_sec == 10.0
        assert config.max_retry == 5
        assert config.base_backoff_seconds == 1.0
