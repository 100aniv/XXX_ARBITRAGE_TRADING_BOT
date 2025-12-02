# -*- coding: utf-8 -*-
"""
Prometheus Client Backend (D80-6)

prometheus_client 라이브러리를 사용한 실제 Prometheus 메트릭 백엔드.
"""

import logging
from typing import Dict, List, Optional, Any
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


class PrometheusClientBackend:
    """
    prometheus_client 기반 Metrics Backend.
    
    Features:
    - Counter, Gauge, Histogram 지원
    - Label 기반 time-series
    - /metrics endpoint용 text export
    - Registry 기반 (테스트 시 격리 가능)
    
    Usage:
        backend = PrometheusClientBackend()
        backend.inc_counter("cross_fx_requests", {"source": "binance"}, 1.0)
        backend.set_gauge("cross_fx_rate", {"pair": "USDT_USD"}, 1.0005)
        text = backend.export_prometheus_text()
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Args:
            registry: Prometheus registry (None이면 새로 생성)
        """
        self.registry = registry if registry is not None else CollectorRegistry()
        
        # Metric objects cache
        # key: (metric_name, metric_type)
        # value: Prometheus metric object
        self._metrics: Dict[tuple, Any] = {}
    
    def inc_counter(self, name: str, labels: dict, value: float = 1.0) -> None:
        """
        Counter 증가.
        
        Args:
            name: 메트릭 이름
            labels: 라벨 딕셔너리
            value: 증가량 (기본 1.0)
        """
        counter = self._get_or_create_metric(name, "counter", list(labels.keys()))
        counter.labels(**labels).inc(value)
    
    def set_gauge(self, name: str, labels: dict, value: float) -> None:
        """
        Gauge 설정.
        
        Args:
            name: 메트릭 이름
            labels: 라벨 딕셔너리
            value: 값
        """
        gauge = self._get_or_create_metric(name, "gauge", list(labels.keys()))
        gauge.labels(**labels).set(value)
    
    def observe_histogram(self, name: str, labels: dict, value: float) -> None:
        """
        Histogram 관측값 추가.
        
        Args:
            name: 메트릭 이름
            labels: 라벨 딕셔너리
            value: 관측값
        """
        histogram = self._get_or_create_metric(name, "histogram", list(labels.keys()))
        histogram.labels(**labels).observe(value)
    
    def export_prometheus_text(self) -> str:
        """
        Prometheus text format으로 export.
        
        Returns:
            /metrics endpoint용 텍스트
        """
        return generate_latest(self.registry).decode("utf-8")
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        전체 metrics 스냅샷 (테스트용).
        
        Returns:
            {
                "counters": {...},
                "gauges": {...},
                "histograms": {...}
            }
        """
        # prometheus_client는 내부 상태 조회가 제한적이므로
        # 테스트 시에는 InMemoryMetricsBackend 사용 권장
        return {
            "counters": {},
            "gauges": {},
            "histograms": {},
            "note": "Use InMemoryMetricsBackend for testing"
        }
    
    def _get_or_create_metric(
        self,
        name: str,
        metric_type: str,
        label_names: List[str]
    ) -> Any:
        """
        Metric 객체를 가져오거나 생성.
        
        Args:
            name: 메트릭 이름
            metric_type: "counter", "gauge", "histogram"
            label_names: 라벨 이름 리스트
        
        Returns:
            Prometheus metric 객체
        """
        # Label names를 정렬해서 일관성 유지
        sorted_label_names = tuple(sorted(label_names))
        key = (name, metric_type, sorted_label_names)
        
        if key not in self._metrics:
            if metric_type == "counter":
                metric = Counter(
                    name,
                    f"{name} (counter)",
                    labelnames=sorted_label_names,
                    registry=self.registry
                )
            elif metric_type == "gauge":
                metric = Gauge(
                    name,
                    f"{name} (gauge)",
                    labelnames=sorted_label_names,
                    registry=self.registry
                )
            elif metric_type == "histogram":
                metric = Histogram(
                    name,
                    f"{name} (histogram)",
                    labelnames=sorted_label_names,
                    registry=self.registry
                )
            else:
                raise ValueError(f"Unsupported metric type: {metric_type}")
            
            self._metrics[key] = metric
            logger.debug(
                f"[PROMETHEUS] Created {metric_type}: {name}, labels={sorted_label_names}"
            )
        
        return self._metrics[key]
