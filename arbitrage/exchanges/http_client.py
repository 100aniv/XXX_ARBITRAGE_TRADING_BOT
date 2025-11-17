# -*- coding: utf-8 -*-
"""
D48: HTTP Client with Rate Limit & Retry

레이트 리밋 및 exponential backoff 재시도 기능을 제공하는 HTTP 클라이언트.
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """레이트 리밋 설정"""
    max_requests_per_sec: float = 5.0  # 초당 최대 요청 수
    max_retry: int = 3  # 최대 재시도 횟수
    base_backoff_seconds: float = 0.5  # 기본 backoff 시간 (초)


class RateLimitError(Exception):
    """레이트 리밋 초과 에러"""
    pass


class HTTPClient:
    """
    D48: HTTP 클라이언트 with 레이트 리밋 & exponential backoff 재시도
    
    역할:
    - 레이트 리밋 체크 (초당 요청 수 제한)
    - HTTP 요청 실행
    - 429/timeout/특정 에러 시 exponential backoff 재시도
    - 모든 재시도 실패 시 예외 발생
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Args:
            config: RateLimitConfig 인스턴스
        """
        self.config = config or RateLimitConfig()
        
        # 레이트 리밋 추적
        self._request_times = []  # 최근 요청 시간들
        self._min_interval = 1.0 / self.config.max_requests_per_sec
        
        logger.info(
            f"[D48_HTTP_CLIENT] Initialized: "
            f"max_requests_per_sec={self.config.max_requests_per_sec}, "
            f"max_retry={self.config.max_retry}, "
            f"base_backoff={self.config.base_backoff_seconds}s"
        )
    
    def _check_rate_limit(self):
        """
        레이트 리밋 체크 및 대기
        
        초당 max_requests_per_sec를 초과하지 않도록 대기.
        """
        now = time.time()
        
        # 1초 이상 전의 요청 제거
        self._request_times = [t for t in self._request_times if now - t < 1.0]
        
        # 현재 초 내 요청 수 확인
        if len(self._request_times) >= self.config.max_requests_per_sec:
            # 대기 필요
            oldest_time = self._request_times[0]
            wait_time = 1.0 - (now - oldest_time)
            if wait_time > 0:
                logger.debug(
                    f"[D48_HTTP_CLIENT] Rate limit: waiting {wait_time:.2f}s "
                    f"({len(self._request_times)} requests in last 1s)"
                )
                time.sleep(wait_time)
        
        # 현재 요청 시간 기록
        self._request_times.append(time.time())
    
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[str] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        """
        HTTP 요청 실행 (레이트 리밋 & 재시도 포함)
        
        Args:
            method: HTTP 메서드 (GET, POST, DELETE 등)
            url: 요청 URL
            headers: 요청 헤더
            params: 쿼리 파라미터
            json: JSON 바디
            data: 텍스트 바디
            timeout: 타임아웃 (초)
        
        Returns:
            requests.Response 객체
        
        Raises:
            RateLimitError: 레이트 리밋 초과
            requests.RequestException: HTTP 요청 실패 (모든 재시도 소진)
        """
        # 레이트 리밋 체크
        self._check_rate_limit()
        
        # exponential backoff 재시도
        last_exception = None
        for attempt in range(self.config.max_retry):
            try:
                logger.debug(
                    f"[D48_HTTP_CLIENT] {method} {url} (attempt {attempt + 1}/{self.config.max_retry})"
                )
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=timeout,
                )
                
                # 429 (Too Many Requests) 또는 5xx 에러는 재시도
                if response.status_code == 429:
                    if attempt < self.config.max_retry - 1:
                        backoff_time = self.config.base_backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"[D48_HTTP_CLIENT] Rate limited (429): "
                            f"backoff {backoff_time:.2f}s before retry"
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise RateLimitError(f"Rate limit exceeded after {self.config.max_retry} retries")
                
                if response.status_code >= 500:
                    if attempt < self.config.max_retry - 1:
                        backoff_time = self.config.base_backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"[D48_HTTP_CLIENT] Server error ({response.status_code}): "
                            f"backoff {backoff_time:.2f}s before retry"
                        )
                        time.sleep(backoff_time)
                        continue
                
                # 성공 또는 클라이언트 에러 (4xx, 2xx)
                logger.debug(
                    f"[D48_HTTP_CLIENT] Response: {response.status_code} "
                    f"(attempt {attempt + 1}/{self.config.max_retry})"
                )
                return response
            
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exception = e
                if attempt < self.config.max_retry - 1:
                    backoff_time = self.config.base_backoff_seconds * (2 ** attempt)
                    logger.warning(
                        f"[D48_HTTP_CLIENT] {type(e).__name__}: "
                        f"backoff {backoff_time:.2f}s before retry"
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    raise
        
        # 모든 재시도 소진
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Unknown error in HTTP request")
    
    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        """GET 요청"""
        return self.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
    
    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[str] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        """POST 요청"""
        return self.request(
            method="POST",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            timeout=timeout,
        )
    
    def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> requests.Response:
        """DELETE 요청"""
        return self.request(
            method="DELETE",
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
