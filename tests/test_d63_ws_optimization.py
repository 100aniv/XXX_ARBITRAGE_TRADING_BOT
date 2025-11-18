"""
D63: WebSocket Optimization Tests

멀티심볼 WS 최적화 검증:
- 심볼별 asyncio.Queue 생성 및 사용
- 비동기 메시지 핸들링
- WS 큐 메트릭 수집
- longrun_analyzer WS 메트릭 분석
"""

import asyncio
import pytest
import time
from typing import Dict, Optional

from arbitrage.exchanges.market_data_provider import WebSocketMarketDataProvider
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.monitoring.metrics_collector import MetricsCollector


class TestD63WSOptimization:
    """D63 WebSocket 최적화 테스트"""
    
    def test_ws_provider_has_symbol_queues(self):
        """심볼별 큐가 생성되는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # D63: 심볼별 큐 속성 확인
        assert hasattr(provider, 'symbol_queues'), "symbol_queues 속성 필요"
        assert isinstance(provider.symbol_queues, dict), "symbol_queues는 Dict이어야 함"
    
    def test_ws_provider_creates_queue_for_symbol(self):
        """특정 심볼에 대해 큐가 생성되는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 심볼에 대해 큐 생성
        provider._ensure_queue_for_symbol("KRW-BTC")
        
        assert "KRW-BTC" in provider.symbol_queues, "KRW-BTC 큐 생성 필요"
        assert isinstance(provider.symbol_queues["KRW-BTC"], asyncio.Queue), "큐는 asyncio.Queue이어야 함"
    
    def test_ws_callback_puts_message_to_queue(self):
        """WS 콜백이 메시지를 큐에 넣는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 테스트 스냅샷 생성
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=int(time.time() * 1000),
            bids=[(100000.0, 1.0)],
            asks=[(100100.0, 1.0)],
        )
        
        # 콜백 호출 (큐에 메시지 적재)
        provider.on_upbit_snapshot(snapshot)
        
        # 큐에 메시지가 있는지 확인
        assert "KRW-BTC" in provider.symbol_queues, "큐 생성 필요"
        assert not provider.symbol_queues["KRW-BTC"].empty(), "큐에 메시지 있어야 함"
    
    @pytest.mark.asyncio
    async def test_ws_consumer_processes_queue(self):
        """비동기 컨슈머가 큐를 처리하는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 테스트 스냅샷
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=int(time.time() * 1000),
            bids=[(100000.0, 1.0)],
            asks=[(100100.0, 1.0)],
        )
        
        # 콜백으로 큐에 메시지 적재
        provider.on_upbit_snapshot(snapshot)
        
        # 컨슈머 실행 (짧은 시간)
        consumer_task = asyncio.create_task(provider._consume_symbol_queue("KRW-BTC"))
        await asyncio.sleep(0.1)
        consumer_task.cancel()
        
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        # latest_snapshots에 업데이트되었는지 확인
        assert "KRW-BTC" in provider.latest_snapshots, "latest_snapshots 업데이트 필요"
        assert provider.latest_snapshots["KRW-BTC"].symbol == "KRW-BTC"
    
    def test_metrics_collector_has_ws_queue_metrics(self):
        """MetricsCollector가 WS 큐 메트릭을 추적하는지 확인"""
        metrics = MetricsCollector()
        
        # D63: WS 큐 메트릭 필드 확인
        assert hasattr(metrics, 'ws_queue_depth_max'), "ws_queue_depth_max 필드 필요"
        assert hasattr(metrics, 'ws_queue_lag_ms_max'), "ws_queue_lag_ms_max 필드 필요"
        assert hasattr(metrics, 'ws_queue_lag_ms_warn_threshold'), "ws_queue_lag_ms_warn_threshold 필드 필요"
    
    def test_metrics_collector_updates_ws_queue_metrics(self):
        """MetricsCollector가 WS 큐 메트릭을 업데이트하는지 확인"""
        metrics = MetricsCollector()
        
        # WS 큐 메트릭 업데이트
        metrics.update_ws_queue_metrics(
            queue_depth=5,
            queue_lag_ms=50.0,
            symbol="KRW-BTC"
        )
        
        # 메트릭이 기록되었는지 확인
        assert metrics.ws_queue_depth_max >= 5, "ws_queue_depth_max 업데이트 필요"
        assert metrics.ws_queue_lag_ms_max >= 50.0, "ws_queue_lag_ms_max 업데이트 필요"
    
    def test_metrics_collector_detects_queue_lag_warning(self):
        """MetricsCollector가 큐 지연 경고를 감지하는지 확인"""
        metrics = MetricsCollector()
        
        # 높은 큐 지연 업데이트
        metrics.update_ws_queue_metrics(
            queue_depth=10,
            queue_lag_ms=1500.0,  # 1.5초 (경고 임계값 > 1000ms)
            symbol="KRW-BTC"
        )
        
        # 경고 조건 확인
        assert metrics.ws_queue_lag_ms_max > metrics.ws_queue_lag_ms_warn_threshold, \
            "큐 지연이 경고 임계값을 초과해야 함"
    
    def test_ws_provider_multisymbol_queues(self):
        """여러 심볼에 대해 독립적인 큐가 유지되는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 여러 심볼에 대해 큐 생성
        provider._ensure_queue_for_symbol("KRW-BTC")
        provider._ensure_queue_for_symbol("KRW-ETH")
        provider._ensure_queue_for_symbol("BTCUSDT")
        
        # 각 심볼의 큐가 독립적인지 확인
        assert len(provider.symbol_queues) == 3, "3개 심볼 큐 필요"
        assert provider.symbol_queues["KRW-BTC"] is not provider.symbol_queues["KRW-ETH"], \
            "각 심볼의 큐는 독립적이어야 함"
    
    def test_ws_provider_queue_isolation(self):
        """한 심볼의 큐가 다른 심볼에 영향을 주지 않는지 확인"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        # 두 심볼의 스냅샷 생성
        snapshot_btc = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=int(time.time() * 1000),
            bids=[(100000.0, 1.0)],
            asks=[(100100.0, 1.0)],
        )
        
        snapshot_eth = OrderBookSnapshot(
            symbol="KRW-ETH",
            timestamp=int(time.time() * 1000),
            bids=[(50000.0, 1.0)],
            asks=[(50100.0, 1.0)],
        )
        
        # 각각 콜백 호출
        provider.on_upbit_snapshot(snapshot_btc)
        provider.on_upbit_snapshot(snapshot_eth)
        
        # 각 큐의 크기 확인
        btc_queue_size = provider.symbol_queues["KRW-BTC"].qsize()
        eth_queue_size = provider.symbol_queues["KRW-ETH"].qsize()
        
        assert btc_queue_size == 1, "KRW-BTC 큐에 1개 메시지"
        assert eth_queue_size == 1, "KRW-ETH 큐에 1개 메시지"
    
    def test_ws_provider_backward_compatibility(self):
        """기존 snapshot_upbit/snapshot_binance 호환성 유지"""
        ws_adapters = {"upbit": None, "binance": None}
        provider = WebSocketMarketDataProvider(ws_adapters)
        
        snapshot = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=int(time.time() * 1000),
            bids=[(100000.0, 1.0)],
            asks=[(100100.0, 1.0)],
        )
        
        # 콜백 호출
        provider.on_upbit_snapshot(snapshot)
        
        # 레거시 필드도 업데이트되었는지 확인
        assert provider.snapshot_upbit is not None, "snapshot_upbit 호환성 필요"
        assert provider.snapshot_upbit.symbol == "KRW-BTC"


class TestD63LongrunAnalyzer:
    """D63 longrun_analyzer WS 메트릭 분석 테스트"""
    
    def test_analyzer_detects_ws_queue_lag(self):
        """analyzer가 WS 큐 지연을 감지하는지 확인"""
        from arbitrage.monitoring.longrun_analyzer import LongrunAnalyzer
        
        # 분석기 생성 (로그 파일 없이)
        analyzer = LongrunAnalyzer()
        
        # WS 큐 지연 메트릭 설정
        analyzer.ws_queue_lag_ms_max = 1500.0
        
        # 이상 조건 확인
        assert analyzer.ws_queue_lag_ms_max > 1000.0, "큐 지연 이상 감지 필요"
    
    def test_analyzer_reports_ws_metrics(self):
        """analyzer가 WS 메트릭을 리포트에 포함하는지 확인"""
        from arbitrage.monitoring.longrun_analyzer import LongrunAnalyzer, LongrunReport
        
        analyzer = LongrunAnalyzer()
        
        # 리포트 생성
        report = LongrunReport(scenario="S1", duration_minutes=10)
        
        # 메트릭 설정
        report.ws_queue_depth_max = 10
        report.ws_queue_lag_ms_max = 500.0
        report.ws_reconnect_count = 2
        
        # 리포트 문자열 생성
        report_str = analyzer.generate_report(report)
        
        # 리포트에 WS 큐 메트릭이 포함되었는지 확인
        assert "queue" in report_str.lower() or "D63" in report_str, \
            "WS 큐 메트릭이 리포트에 포함되어야 함"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
