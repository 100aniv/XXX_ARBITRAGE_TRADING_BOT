"""
D205-12-1: AdminControl Engine Integration Tests

목표: PaperRunner에 AdminControl 훅이 실제로 연결되어 동작하는지 검증

Tests:
1. mode=PAUSED → intents_created == 0 (주문 생성 멈춤)
2. symbol blacklist → 해당 심볼 intent 생성 안 됨
3. mode=RUNNING 복귀 → 정상 동작 재개
"""

import pytest
import redis
import time
from pathlib import Path

from arbitrage.v2.core.admin_control import AdminControl, ControlMode
from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig


@pytest.fixture
def redis_client():
    """Redis 클라이언트 (DB 1, 테스트 전용)"""
    client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    yield client
    # 테스트 후 flush (오염 방지)
    client.flushdb()


@pytest.fixture
def admin_control(redis_client):
    """AdminControl 인스턴스"""
    return AdminControl(
        redis_client=redis_client,
        run_id="test_d205_12_1",
        env="test",
    )


def test_paused_mode_stops_order_generation(admin_control, tmp_path):
    """
    Test 1: mode=PAUSED → intents_created == 0
    
    AdminControl이 PAUSED일 때 엔진이 주문 생성을 멈추는지 검증
    """
    # Arrange: PAUSED 모드로 전환
    admin_control.pause(actor="test", reason="integration test")
    
    # PaperRunner 생성 (AdminControl 연결)
    config = PaperRunnerConfig(
        duration_minutes=0.05,  # 3초 (빠른 테스트)
        phase="test",
        run_id="test_paused_mode",
        output_dir=str(tmp_path / "test_paused"),
        db_mode="off",
        use_real_data=False,
    )
    runner = PaperRunner(config, admin_control=admin_control)
    
    # Act: 실행
    exit_code = runner.run()
    
    # Assert
    assert exit_code == 0, "Runner should complete successfully"
    assert runner.kpi.intents_created == 0, "PAUSED mode should prevent intent creation"
    assert runner.kpi.reject_reasons["admin_paused"] > 0, "Should have admin_paused rejects"
    print(f"✅ Test 1 PASS: admin_paused={runner.kpi.reject_reasons['admin_paused']}, intents={runner.kpi.intents_created}")


def test_symbol_blacklist_blocks_intent(admin_control, tmp_path):
    """
    Test 2: symbol blacklist → 해당 심볼 intent 생성 안 됨
    
    AdminControl blacklist에 심볼 추가 시 해당 심볼 주문 생성이 차단되는지 검증
    """
    # Arrange: BTC/KRW blacklist 추가
    admin_control.blacklist_add(symbol="BTC/KRW", actor="test", reason="integration test")
    
    # PaperRunner 생성 (AdminControl 연결)
    config = PaperRunnerConfig(
        duration_minutes=0.05,  # 3초
        phase="test",
        run_id="test_blacklist",
        output_dir=str(tmp_path / "test_blacklist"),
        db_mode="off",
        use_real_data=False,
    )
    runner = PaperRunner(config, admin_control=admin_control)
    
    # Act: 실행
    exit_code = runner.run()
    
    # Assert
    assert exit_code == 0, "Runner should complete successfully"
    assert runner.kpi.reject_reasons["symbol_blacklisted"] > 0, "Should have symbol_blacklisted rejects"
    print(f"✅ Test 2 PASS: symbol_blacklisted={runner.kpi.reject_reasons['symbol_blacklisted']}")


def test_running_mode_resume(admin_control, tmp_path):
    """
    Test 3: mode=RUNNING 복귀 → 정상 동작 재개
    
    PAUSED → RUNNING 전환 시 정상 동작 재개되는지 검증
    """
    # Arrange: PAUSED → RUNNING 전환
    admin_control.pause(actor="test", reason="initial pause")
    admin_control.resume(actor="test", reason="resume test")
    
    # PaperRunner 생성 (AdminControl 연결)
    config = PaperRunnerConfig(
        duration_minutes=0.05,  # 3초
        phase="test",
        run_id="test_resume",
        output_dir=str(tmp_path / "test_resume"),
        db_mode="off",
        use_real_data=False,
    )
    runner = PaperRunner(config, admin_control=admin_control)
    
    # Act: 실행
    exit_code = runner.run()
    
    # Assert
    assert exit_code == 0, "Runner should complete successfully"
    assert runner.kpi.intents_created > 0, "RUNNING mode should allow intent creation"
    assert runner.kpi.reject_reasons["admin_paused"] == 0, "Should have no admin_paused rejects"
    print(f"[PASS] Test 3: intents_created={runner.kpi.intents_created}, admin_paused=0")


def test_no_admin_control_normal_operation(tmp_path):
    """
    Test 4 (보너스): admin_control=None → 정상 동작 (하위 호환)
    
    AdminControl이 None일 때 기존 동작 유지되는지 검증
    """
    # Arrange: AdminControl 없이 생성
    config = PaperRunnerConfig(
        duration_minutes=0.05,  # 3초
        phase="test",
        run_id="test_no_admin",
        output_dir=str(tmp_path / "test_no_admin"),
        db_mode="off",
        use_real_data=False,
    )
    runner = PaperRunner(config, admin_control=None)  # admin_control=None
    
    # Act: 실행
    exit_code = runner.run()
    
    # Assert
    assert exit_code == 0, "Runner should complete successfully"
    assert runner.kpi.intents_created > 0, "Should create intents normally without AdminControl"
    assert runner.kpi.reject_reasons["admin_paused"] == 0, "Should have no admin_paused rejects"
    assert runner.kpi.reject_reasons["symbol_blacklisted"] == 0, "Should have no symbol_blacklisted rejects"
    print(f"✅ Test 4 PASS: intents_created={runner.kpi.intents_created}, no admin rejects")
