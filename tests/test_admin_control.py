"""
D205-12: Admin Control Engine 테스트

테스트 범위:
1. Unit: ControlState 직렬화/역직렬화
2. Unit: Command 처리 (pause/resume/stop/panic/blacklist/emergency_close)
3. Unit: Audit log 기록
4. Integration: Redis 상태 저장/읽기
5. Integration: 엔진 루프 훅 (should_process_tick, is_symbol_blacklisted)
"""

import pytest
import json
import os
import redis
from pathlib import Path
from datetime import datetime, timezone
from arbitrage.v2.core.admin_control import (
    AdminControl,
    ControlMode,
    ControlState,
    AuditLogEntry,
)


@pytest.fixture
def redis_client():
    """Redis 테스트 클라이언트 (DB 1 사용)"""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6380"))
    client = redis.Redis(host=redis_host, port=redis_port, db=1, decode_responses=True)
    yield client
    # Cleanup: 테스트 키 삭제
    for key in client.scan_iter("v2:test:*"):
        client.delete(key)


@pytest.fixture
def admin_control(redis_client, tmp_path):
    """AdminControl 테스트 인스턴스"""
    audit_log_path = tmp_path / "admin_audit.jsonl"
    return AdminControl(
        redis_client=redis_client,
        run_id="test_run_001",
        env="test",
        audit_log_path=audit_log_path,
    )


def test_control_state_serialization():
    """ControlState 직렬화/역직렬화 테스트"""
    state = ControlState(
        mode=ControlMode.RUNNING,
        symbol_blacklist={"BTC/KRW", "ETH/KRW"},
        updated_by="test",
        reason="test reason",
    )
    
    # to_dict
    data = state.to_dict()
    assert data["mode"] == "RUNNING"
    assert set(data["symbol_blacklist"]) == {"BTC/KRW", "ETH/KRW"}
    assert data["updated_by"] == "test"
    assert data["reason"] == "test reason"
    
    # from_dict
    restored = ControlState.from_dict(data)
    assert restored.mode == ControlMode.RUNNING
    assert restored.symbol_blacklist == {"BTC/KRW", "ETH/KRW"}
    assert restored.updated_by == "test"
    assert restored.reason == "test reason"


def test_admin_control_init(admin_control, redis_client):
    """AdminControl 초기화 테스트"""
    # Redis에 초기 상태 저장 확인
    state_key = "v2:test:test_run_001:control:state"
    assert redis_client.exists(state_key) == 1
    
    # 초기 상태: RUNNING
    status = admin_control.status()
    assert status["mode"] == "RUNNING"
    assert status["symbol_blacklist"] == []
    assert status["updated_by"] == "system"
    assert status["reason"] == "Initial state"


def test_pause_resume(admin_control):
    """pause/resume 명령 테스트"""
    # pause
    result = admin_control.pause(reason="Manual pause", actor="test_user")
    assert result["status"] == "ok"
    assert result["after"]["mode"] == "PAUSED"
    
    # 상태 확인
    status = admin_control.status()
    assert status["mode"] == "PAUSED"
    assert status["updated_by"] == "test_user"
    assert status["reason"] == "Manual pause"
    
    # resume
    result = admin_control.resume(reason="Manual resume", actor="test_user")
    assert result["status"] == "ok"
    assert result["after"]["mode"] == "RUNNING"
    
    # 상태 확인
    status = admin_control.status()
    assert status["mode"] == "RUNNING"
    assert status["updated_by"] == "test_user"
    assert status["reason"] == "Manual resume"


def test_pause_from_panic_forbidden(admin_control):
    """PANIC 상태에서 pause 금지 테스트"""
    # PANIC 상태로 전환
    admin_control.panic(reason="Test panic", actor="test_user")
    
    # PANIC → PAUSED 금지
    result = admin_control.pause(reason="Try pause", actor="test_user")
    assert result["status"] == "error"
    assert "Cannot pause from PANIC mode" in result["message"]


def test_resume_from_non_paused_forbidden(admin_control):
    """PAUSED가 아닌 상태에서 resume 금지 테스트"""
    # RUNNING 상태에서 resume 시도
    result = admin_control.resume(reason="Try resume", actor="test_user")
    assert result["status"] == "error"
    assert "Cannot resume from RUNNING mode" in result["message"]


def test_stop(admin_control):
    """stop 명령 테스트"""
    result = admin_control.stop(reason="Graceful shutdown", actor="test_user")
    assert result["status"] == "ok"
    assert result["after"]["mode"] == "STOPPING"
    
    status = admin_control.status()
    assert status["mode"] == "STOPPING"


def test_panic(admin_control):
    """panic 명령 테스트"""
    result = admin_control.panic(reason="Emergency stop", actor="test_user")
    assert result["status"] == "ok"
    assert result["after"]["mode"] == "PANIC"
    
    status = admin_control.status()
    assert status["mode"] == "PANIC"


def test_emergency_close(admin_control):
    """emergency_close 명령 테스트"""
    result = admin_control.emergency_close(reason="Force close", actor="test_user")
    assert result["status"] == "ok"
    assert result["after"]["mode"] == "EMERGENCY_CLOSE"
    
    status = admin_control.status()
    assert status["mode"] == "EMERGENCY_CLOSE"


def test_blacklist_add_remove(admin_control):
    """blacklist_add/remove 테스트"""
    # Add
    result = admin_control.blacklist_add(symbol="BTC/KRW", reason="High volatility", actor="test_user")
    assert result["status"] == "ok"
    assert "BTC/KRW" in result["blacklist"]
    
    status = admin_control.status()
    assert "BTC/KRW" in status["symbol_blacklist"]
    
    # Add again (idempotent)
    result = admin_control.blacklist_add(symbol="BTC/KRW", reason="Again", actor="test_user")
    assert result["status"] == "ok"
    assert result["blacklist"].count("BTC/KRW") == 1
    
    # Add another
    result = admin_control.blacklist_add(symbol="ETH/KRW", reason="Test", actor="test_user")
    assert result["status"] == "ok"
    assert len(result["blacklist"]) == 2
    
    # Remove
    result = admin_control.blacklist_remove(symbol="BTC/KRW", reason="Volatility stabilized", actor="test_user")
    assert result["status"] == "ok"
    assert "BTC/KRW" not in result["blacklist"]
    assert "ETH/KRW" in result["blacklist"]
    
    # Remove non-existent (no error)
    result = admin_control.blacklist_remove(symbol="XRP/KRW", reason="Test", actor="test_user")
    assert result["status"] == "ok"


def test_should_process_tick(admin_control):
    """should_process_tick 훅 테스트"""
    # RUNNING: True
    assert admin_control.should_process_tick() is True
    
    # PAUSED: False
    admin_control.pause(reason="Test", actor="test_user")
    assert admin_control.should_process_tick() is False
    
    # STOPPING: False
    admin_control.stop(reason="Test", actor="test_user")
    assert admin_control.should_process_tick() is False
    
    # PANIC: False
    admin_control.panic(reason="Test", actor="test_user")
    assert admin_control.should_process_tick() is False


def test_is_symbol_blacklisted(admin_control):
    """is_symbol_blacklisted 훅 테스트"""
    # 초기: 블랙리스트 없음
    assert admin_control.is_symbol_blacklisted("BTC/KRW") is False
    
    # 블랙리스트 추가
    admin_control.blacklist_add(symbol="BTC/KRW", reason="Test", actor="test_user")
    assert admin_control.is_symbol_blacklisted("BTC/KRW") is True
    assert admin_control.is_symbol_blacklisted("ETH/KRW") is False
    
    # 블랙리스트 제거
    admin_control.blacklist_remove(symbol="BTC/KRW", reason="Test", actor="test_user")
    assert admin_control.is_symbol_blacklisted("BTC/KRW") is False


def test_audit_log_recording(admin_control, tmp_path):
    """Audit log 기록 테스트"""
    audit_log_path = tmp_path / "admin_audit.jsonl"
    
    # 여러 명령 실행
    admin_control.pause(reason="Test pause", actor="user1")
    admin_control.resume(reason="Test resume", actor="user2")
    admin_control.blacklist_add(symbol="BTC/KRW", reason="Test blacklist", actor="user3")
    
    # Audit log 파일 확인
    assert audit_log_path.exists()
    
    # NDJSON 파싱
    entries = []
    with open(audit_log_path, "r", encoding="utf-8") as f:
        for line in f:
            entries.append(json.loads(line))
    
    # 4개 엔트리 (init 포함 안 됨, 명령만 기록)
    assert len(entries) == 3
    
    # pause 엔트리
    assert entries[0]["command"] == "pause"
    assert entries[0]["actor"] == "user1"
    assert entries[0]["args"]["reason"] == "Test pause"
    assert entries[0]["before_state"]["mode"] == "RUNNING"
    assert entries[0]["after_state"]["mode"] == "PAUSED"
    assert entries[0]["result"] == "ok"
    
    # resume 엔트리
    assert entries[1]["command"] == "resume"
    assert entries[1]["actor"] == "user2"
    
    # blacklist_add 엔트리
    assert entries[2]["command"] == "blacklist_add"
    assert entries[2]["actor"] == "user3"
    assert entries[2]["args"]["symbol"] == "BTC/KRW"


def test_redis_state_persistence(admin_control, redis_client):
    """Redis 상태 저장/읽기 테스트"""
    state_key = "v2:test:test_run_001:control:state"
    
    # 상태 변경
    admin_control.pause(reason="Test", actor="test_user")
    
    # Redis 직접 읽기
    raw_data = redis_client.get(state_key)
    assert raw_data is not None
    
    data = json.loads(raw_data)
    assert data["mode"] == "PAUSED"
    assert data["updated_by"] == "test_user"
    assert data["reason"] == "Test"
    
    # TTL 확인 (1h = 3600s)
    ttl = redis_client.ttl(state_key)
    assert 3500 < ttl <= 3600


def test_mode_transition_sequence(admin_control):
    """상태 전이 시퀀스 테스트"""
    # RUNNING → PAUSED → RUNNING
    assert admin_control.status()["mode"] == "RUNNING"
    
    admin_control.pause(reason="Test", actor="user")
    assert admin_control.status()["mode"] == "PAUSED"
    
    admin_control.resume(reason="Test", actor="user")
    assert admin_control.status()["mode"] == "RUNNING"
    
    # RUNNING → STOPPING (복구 불가)
    admin_control.stop(reason="Test", actor="user")
    assert admin_control.status()["mode"] == "STOPPING"
    
    # STOPPING → RUNNING 불가
    result = admin_control.resume(reason="Test", actor="user")
    assert result["status"] == "error"
    
    # PANIC → 어디로도 갈 수 없음
    admin_control.panic(reason="Test", actor="user")
    assert admin_control.status()["mode"] == "PANIC"
    
    result = admin_control.pause(reason="Test", actor="user")
    assert result["status"] == "error"
    
    result = admin_control.resume(reason="Test", actor="user")
    assert result["status"] == "error"


def test_blacklist_preserved_across_mode_changes(admin_control):
    """모드 변경 시 블랙리스트 유지 테스트"""
    # 블랙리스트 추가
    admin_control.blacklist_add(symbol="BTC/KRW", reason="Test", actor="user")
    admin_control.blacklist_add(symbol="ETH/KRW", reason="Test", actor="user")
    
    # PAUSED로 변경
    admin_control.pause(reason="Test", actor="user")
    status = admin_control.status()
    assert set(status["symbol_blacklist"]) == {"BTC/KRW", "ETH/KRW"}
    
    # RESUME
    admin_control.resume(reason="Test", actor="user")
    status = admin_control.status()
    assert set(status["symbol_blacklist"]) == {"BTC/KRW", "ETH/KRW"}
    
    # STOPPING
    admin_control.stop(reason="Test", actor="user")
    status = admin_control.status()
    assert set(status["symbol_blacklist"]) == {"BTC/KRW", "ETH/KRW"}
