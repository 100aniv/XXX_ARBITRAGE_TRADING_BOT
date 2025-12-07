# -*- coding: utf-8 -*-
"""
D84-2: Runner Configuration 테스트

CalibratedFillModel + L2 + FillEventCollector 통합 검증 (Dry-run 수준)
"""

import json
import pytest
from pathlib import Path
import sys

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.execution.fill_model import SimpleFillModel, CalibratedFillModel, CalibrationTable
from arbitrage.metrics.fill_stats import FillEventCollector
from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.config.settings import Settings

# D83-2: Binance L2 Provider Import 테스트
from arbitrage.exchanges.upbit_l2_ws_provider import UpbitL2WebSocketProvider
from arbitrage.exchanges.binance_l2_ws_provider import BinanceL2WebSocketProvider


def test_calibration_loading():
    """Calibration JSON 로딩 테스트"""
    calibration_path = Path(__file__).parent.parent / "logs" / "d84" / "d84_1_calibration.json"
    
    if not calibration_path.exists():
        pytest.skip(f"Calibration 파일이 존재하지 않습니다: {calibration_path}")
    
    with open(calibration_path, "r") as f:
        calibration_data = json.load(f)
    
    # CalibrationTable은 6개 필드만 받음 (total_events, unmatched_events 제외)
    calibration = CalibrationTable(
        version=calibration_data["version"],
        zones=calibration_data["zones"],
        default_buy_fill_ratio=calibration_data["default_buy_fill_ratio"],
        default_sell_fill_ratio=calibration_data["default_sell_fill_ratio"],
        created_at=calibration_data["created_at"],
        source=calibration_data["source"],
    )
    
    assert calibration.version == "d84_1"
    assert len(calibration.zones) > 0
    assert 0.0 <= calibration.default_buy_fill_ratio <= 1.0
    assert 0.0 <= calibration.default_sell_fill_ratio <= 1.0


def test_calibrated_fill_model_creation():
    """CalibratedFillModel 생성 테스트"""
    # Mock Calibration
    calibration = CalibrationTable(
        version="test",
        created_at="2025-12-06T00:00:00",
        source="test",
        zones=[
            {
                "zone_id": "Z1",
                "entry_min": 5.0,
                "entry_max": 7.0,
                "tp_min": 7.0,
                "tp_max": 12.0,
                "buy_fill_ratio": 0.3,
                "sell_fill_ratio": 1.0,
                "samples": 10,
            }
        ],
        default_buy_fill_ratio=0.25,
        default_sell_fill_ratio=1.0,
    )
    base_model = SimpleFillModel()
    
    fill_model = CalibratedFillModel(
        base_model=base_model,
        calibration=calibration,
        entry_bps=6.0,  # Z1에 매칭
        tp_bps=10.0,
    )
    
    assert fill_model.base_model is not None
    assert fill_model.calibration is not None
    assert fill_model.zone is not None
    assert fill_model.zone.zone_id == "Z1"


def test_fill_event_collector_creation(tmp_path):
    """FillEventCollector 생성 테스트"""
    output_path = tmp_path / "fill_events.jsonl"
    
    collector = FillEventCollector(
        output_path=output_path,
        enabled=True,
        session_id="test_session",
    )
    
    assert collector.enabled is True
    assert collector.session_id == "test_session"
    assert collector.output_path == output_path


def test_executor_factory_integration():
    """ExecutorFactory 통합 테스트"""
    portfolio_state = PortfolioState(
        total_balance=10000.0,
        available_balance=10000.0,
    )
    risk_limits = RiskLimits(
        max_notional_per_trade=10000.0,
        max_daily_loss=1000.0,
        max_open_trades=10,
    )
    risk_guard = RiskGuard(risk_limits=risk_limits)
    
    settings = Settings.from_env()
    settings.fill_model.enable_fill_model = True
    
    executor_factory = ExecutorFactory()
    
    executor = executor_factory.create_paper_executor(
        symbol="BTC",
        portfolio_state=portfolio_state,
        risk_guard=risk_guard,
        fill_model_config=settings.fill_model,
    )
    
    assert executor is not None
    assert executor.symbol == "BTC"
    assert executor.enable_fill_model is True


def test_runner_components_compatibility():
    """Runner 주요 컴포넌트 호환성 테스트"""
    # 1. Calibration
    calibration = CalibrationTable(
        version="test",
        created_at="2025-12-06T00:00:00",
        source="test",
        zones=[],
        default_buy_fill_ratio=0.25,
        default_sell_fill_ratio=1.0,
    )
    
    # 2. Fill Model
    base_model = SimpleFillModel()
    fill_model = CalibratedFillModel(
        base_model=base_model,
        calibration=calibration,
        entry_bps=10.0,
        tp_bps=12.0,
    )
    
    # 3. FillEventCollector
    collector = FillEventCollector(
        output_path=Path("/tmp/test.jsonl"),
        enabled=False,  # Dry-run
        session_id="test",
    )
    
    # 4. Executor
    portfolio_state = PortfolioState(
        total_balance=10000.0,
        available_balance=10000.0,
    )
    risk_limits = RiskLimits(
        max_notional_per_trade=10000.0,
        max_daily_loss=1000.0,
        max_open_trades=10,
    )
    risk_guard = RiskGuard(risk_limits=risk_limits)
    
    executor_factory = ExecutorFactory()
    executor = executor_factory.create_paper_executor(
        symbol="BTC",
        portfolio_state=portfolio_state,
        risk_guard=risk_guard,
        fill_model_config=Settings.from_env().fill_model,
        fill_event_collector=collector,
    )
    
    # Fill Model 강제 주입
    executor.fill_model = fill_model
    executor.enable_fill_model = True
    
    assert executor.fill_model == fill_model
    assert executor.fill_event_collector == collector


def test_l2_provider_upbit_creation():
    """D83-1: Upbit L2 Provider 생성 테스트"""
    provider = UpbitL2WebSocketProvider(
        symbols=["KRW-BTC"],
        heartbeat_interval=30.0,
        timeout=10.0,
    )
    
    assert provider is not None
    assert provider.symbols == ["KRW-BTC"]
    assert len(provider.latest_snapshots) == 0


def test_l2_provider_binance_creation():
    """D83-2: Binance L2 Provider 생성 테스트"""
    provider = BinanceL2WebSocketProvider(
        symbols=["BTCUSDT"],
        depth="20",
        interval="100ms",
        heartbeat_interval=30.0,
        timeout=10.0,
    )
    
    assert provider is not None
    assert provider.symbols == ["BTCUSDT"]
    assert len(provider.latest_snapshots) == 0
