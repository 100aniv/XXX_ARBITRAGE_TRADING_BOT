#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Monitor (PHASE D11)
==========================

프로세스 리소스 모니터링 (선택적 의존성: psutil).

특징:
- psutil 없는 환경에서도 graceful fallback
- CPU, 메모리, 파일 디스크립터 추적
- 임계치 기반 경고
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# psutil 선택적 임포트
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("[SysMonitor] psutil not installed, system monitoring disabled")


@dataclass
class ResourceSample:
    """리소스 샘플"""
    timestamp: float
    cpu_pct: float              # CPU 사용률 (%)
    rss_mb: float               # 메모리 (MB)
    open_files: int             # 열린 파일 수
    num_threads: int            # 스레드 수
    available: bool = True      # 데이터 수집 가능 여부


@dataclass
class SysMonitorConfig:
    """시스템 모니터 설정"""
    enabled: bool = True
    max_cpu_pct: float = 90.0           # CPU 임계치 (%)
    max_rss_mb: float = 2048.0          # 메모리 임계치 (MB)
    sample_interval_sec: float = 30.0   # 샘플 간격 (초)
    warn_cpu_pct: float = 75.0          # CPU 경고 임계치 (%)
    warn_rss_mb: float = 1536.0         # 메모리 경고 임계치 (MB)


class SystemMonitor:
    """시스템 모니터"""
    
    def __init__(self, config: Optional[SysMonitorConfig] = None):
        """
        Args:
            config: SysMonitorConfig 인스턴스
        """
        self.config = config or SysMonitorConfig()
        self.enabled = self.config.enabled and HAS_PSUTIL
        self.last_sample: Optional[ResourceSample] = None
        self.process = None
        
        if self.enabled:
            try:
                self.process = psutil.Process()
                logger.info("[SysMonitor] System monitoring enabled")
            except Exception as e:
                logger.warning(f"[SysMonitor] Failed to initialize: {e}")
                self.enabled = False
        else:
            logger.info("[SysMonitor] System monitoring disabled (psutil not available)")
    
    def sample(self) -> ResourceSample:
        """
        현재 리소스 상태 샘플링
        
        Returns:
            ResourceSample 인스턴스
        """
        import time
        
        if not self.enabled or self.process is None:
            return ResourceSample(
                timestamp=time.time(),
                cpu_pct=0.0,
                rss_mb=0.0,
                open_files=0,
                num_threads=0,
                available=False
            )
        
        try:
            # CPU 사용률 (%)
            cpu_pct = self.process.cpu_percent(interval=0.1)
            
            # 메모리 (MB)
            mem_info = self.process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            
            # 열린 파일 수
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, AttributeError):
                open_files = 0
            
            # 스레드 수
            num_threads = self.process.num_threads()
            
            sample = ResourceSample(
                timestamp=time.time(),
                cpu_pct=cpu_pct,
                rss_mb=rss_mb,
                open_files=open_files,
                num_threads=num_threads,
                available=True
            )
            
            self.last_sample = sample
            return sample
        
        except Exception as e:
            logger.warning(f"[SysMonitor] Sampling error: {e}")
            return ResourceSample(
                timestamp=time.time(),
                cpu_pct=0.0,
                rss_mb=0.0,
                open_files=0,
                num_threads=0,
                available=False
            )
    
    def check_thresholds(self, sample: ResourceSample) -> Dict[str, Any]:
        """
        임계치 확인
        
        Args:
            sample: ResourceSample 인스턴스
        
        Returns:
            {
                'cpu_ok': bool,
                'cpu_warn': bool,
                'memory_ok': bool,
                'memory_warn': bool,
                'alerts': [...]
            }
        """
        alerts = []
        
        # CPU 확인
        cpu_ok = sample.cpu_pct <= self.config.max_cpu_pct
        cpu_warn = sample.cpu_pct > self.config.warn_cpu_pct
        
        if not cpu_ok:
            alerts.append(f"CPU critical: {sample.cpu_pct:.1f}% > {self.config.max_cpu_pct}%")
        elif cpu_warn:
            alerts.append(f"CPU warning: {sample.cpu_pct:.1f}% > {self.config.warn_cpu_pct}%")
        
        # 메모리 확인
        memory_ok = sample.rss_mb <= self.config.max_rss_mb
        memory_warn = sample.rss_mb > self.config.warn_rss_mb
        
        if not memory_ok:
            alerts.append(f"Memory critical: {sample.rss_mb:.1f}MB > {self.config.max_rss_mb}MB")
        elif memory_warn:
            alerts.append(f"Memory warning: {sample.rss_mb:.1f}MB > {self.config.warn_rss_mb}MB")
        
        return {
            'cpu_ok': cpu_ok,
            'cpu_warn': cpu_warn,
            'memory_ok': memory_ok,
            'memory_warn': memory_warn,
            'alerts': alerts
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        if self.last_sample is None or not self.last_sample.available:
            return {
                'available': False,
                'cpu_pct': 0.0,
                'rss_mb': 0.0,
                'open_files': 0,
                'num_threads': 0
            }
        
        return {
            'available': True,
            'cpu_pct': self.last_sample.cpu_pct,
            'rss_mb': self.last_sample.rss_mb,
            'open_files': self.last_sample.open_files,
            'num_threads': self.last_sample.num_threads
        }
