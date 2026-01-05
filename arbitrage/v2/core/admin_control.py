"""
D205-12: Admin Control Engine (엔진 내부 제어 상태 관리)

책임:
- ControlState 관리 (RUNNING/PAUSED/STOPPING/PANIC/EMERGENCY_CLOSE)
- Command 처리 (pause/resume/stop/panic/blacklist/emergency_close)
- Audit Log 기록 (모든 제어 명령 + 상태 전이)
- Redis Hot-state 저장 (v2:control:* keyspace)

금지:
- UI/웹/텔레그램 구현 (D206-4 영역)
- Grafana 패널 (D206-1 영역)
- 신규 Redis 키스페이스 생성 (REDIS_KEYSPACE.md 준수)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
import redis

logger = logging.getLogger(__name__)


class ControlMode(str, Enum):
    """엔진 제어 모드 (상태)"""
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    PANIC = "PANIC"
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE"


@dataclass
class ControlState:
    """
    엔진 제어 상태 (Redis Hot-state)
    
    Redis Key: v2:{env}:{run_id}:control:state
    """
    mode: ControlMode
    symbol_blacklist: Set[str] = field(default_factory=set)
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_by: str = "system"
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장용 dict 변환"""
        return {
            "mode": self.mode.value,
            "symbol_blacklist": list(self.symbol_blacklist),
            "updated_at_utc": self.updated_at_utc,
            "updated_by": self.updated_by,
            "reason": self.reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlState":
        """Redis 읽기용 dict → ControlState"""
        return cls(
            mode=ControlMode(data["mode"]),
            symbol_blacklist=set(data.get("symbol_blacklist", [])),
            updated_at_utc=data["updated_at_utc"],
            updated_by=data["updated_by"],
            reason=data.get("reason"),
        )


@dataclass
class AuditLogEntry:
    """
    Admin 명령 audit log (append-only)
    
    저장 포맷: NDJSON (logs/admin_audit.jsonl)
    """
    timestamp_utc: str
    actor: str
    command: str
    args: Dict[str, Any]
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    result: str
    error: Optional[str] = None
    
    def to_json(self) -> str:
        """NDJSON 저장용"""
        return json.dumps(asdict(self), ensure_ascii=False)


class AdminControl:
    """
    Admin Control Engine (D205-12)
    
    책임:
    - ControlState 관리 (Redis Hot-state)
    - Command 처리 (pause/resume/stop/panic/blacklist/emergency_close)
    - Audit Log 기록 (append-only NDJSON)
    - 엔진 루프 훅 제공 (should_process_tick, is_symbol_blacklisted)
    
    Redis Keyspace:
    - v2:{env}:{run_id}:control:state (ControlState JSON)
    
    Audit Log:
    - logs/admin_audit.jsonl (NDJSON append-only)
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        run_id: str,
        env: str = "prod",
        audit_log_path: Optional[Path] = None,
    ):
        self.redis = redis_client
        self.run_id = run_id
        self.env = env
        self.audit_log_path = audit_log_path or Path("logs/admin_audit.jsonl")
        
        self.state_key = f"v2:{env}:{run_id}:control:state"
        
        # 초기화: RUNNING 상태로 시작
        initial_state = ControlState(
            mode=ControlMode.RUNNING,
            updated_by="system",
            reason="Initial state",
        )
        self._save_state(initial_state)
        logger.info(f"[D205-12 AdminControl] Initialized: {self.state_key}")
    
    def _save_state(self, state: ControlState):
        """Redis에 ControlState 저장 (TTL 1h)"""
        self.redis.setex(
            self.state_key,
            3600,  # TTL 1h (REDIS_KEYSPACE.md state domain 기준)
            json.dumps(state.to_dict()),
        )
    
    def _load_state(self) -> ControlState:
        """Redis에서 ControlState 읽기"""
        data = self.redis.get(self.state_key)
        if not data:
            raise RuntimeError(f"[D205-12 AdminControl] State key not found: {self.state_key}")
        return ControlState.from_dict(json.loads(data))
    
    def _append_audit_log(self, entry: AuditLogEntry):
        """Audit log 기록 (NDJSON append-only)"""
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")
    
    def pause(self, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """
        엔진 일시 정지 (데이터 수집 유지, 주문/포지션 변경 금지)
        
        Returns:
            {"status": "ok", "before": {...}, "after": {...}}
        """
        before_state = self._load_state()
        
        if before_state.mode == ControlMode.PANIC:
            return {
                "status": "error",
                "message": "Cannot pause from PANIC mode",
            }
        
        after_state = ControlState(
            mode=ControlMode.PAUSED,
            symbol_blacklist=before_state.symbol_blacklist,
            updated_by=actor,
            reason=reason,
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="pause",
            args={"reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.info(f"[D205-12 AdminControl] PAUSED by {actor}: {reason}")
        return {
            "status": "ok",
            "before": before_state.to_dict(),
            "after": after_state.to_dict(),
        }
    
    def resume(self, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """엔진 재개 (PAUSED → RUNNING)"""
        before_state = self._load_state()
        
        if before_state.mode != ControlMode.PAUSED:
            return {
                "status": "error",
                "message": f"Cannot resume from {before_state.mode.value} mode",
            }
        
        after_state = ControlState(
            mode=ControlMode.RUNNING,
            symbol_blacklist=before_state.symbol_blacklist,
            updated_by=actor,
            reason=reason,
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="resume",
            args={"reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.info(f"[D205-12 AdminControl] RESUMED by {actor}: {reason}")
        return {
            "status": "ok",
            "before": before_state.to_dict(),
            "after": after_state.to_dict(),
        }
    
    def stop(self, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """엔진 정지 (graceful shutdown, 신규 주문 금지)"""
        before_state = self._load_state()
        
        after_state = ControlState(
            mode=ControlMode.STOPPING,
            symbol_blacklist=before_state.symbol_blacklist,
            updated_by=actor,
            reason=reason,
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="stop",
            args={"reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.warning(f"[D205-12 AdminControl] STOPPING by {actor}: {reason}")
        return {
            "status": "ok",
            "before": before_state.to_dict(),
            "after": after_state.to_dict(),
        }
    
    def panic(self, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """긴급 중단 (즉시 주문 금지 + 포지션 초기화)"""
        before_state = self._load_state()
        
        after_state = ControlState(
            mode=ControlMode.PANIC,
            symbol_blacklist=before_state.symbol_blacklist,
            updated_by=actor,
            reason=reason,
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="panic",
            args={"reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.error(f"[D205-12 AdminControl] PANIC by {actor}: {reason}")
        return {
            "status": "ok",
            "before": before_state.to_dict(),
            "after": after_state.to_dict(),
        }
    
    def emergency_close(self, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """긴급 포지션 청산 (paper: 포지션 초기화)"""
        before_state = self._load_state()
        
        after_state = ControlState(
            mode=ControlMode.EMERGENCY_CLOSE,
            symbol_blacklist=before_state.symbol_blacklist,
            updated_by=actor,
            reason=reason,
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="emergency_close",
            args={"reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.error(f"[D205-12 AdminControl] EMERGENCY_CLOSE by {actor}: {reason}")
        return {
            "status": "ok",
            "before": before_state.to_dict(),
            "after": after_state.to_dict(),
        }
    
    def blacklist_add(self, symbol: str, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """심볼 블랙리스트 추가 (즉시 거래 중단)"""
        before_state = self._load_state()
        
        after_blacklist = before_state.symbol_blacklist.copy()
        after_blacklist.add(symbol)
        
        after_state = ControlState(
            mode=before_state.mode,
            symbol_blacklist=after_blacklist,
            updated_by=actor,
            reason=f"Blacklist add: {symbol} - {reason}",
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="blacklist_add",
            args={"symbol": symbol, "reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.warning(f"[D205-12 AdminControl] Blacklist ADD: {symbol} by {actor}")
        return {
            "status": "ok",
            "symbol": symbol,
            "blacklist": list(after_blacklist),
        }
    
    def blacklist_remove(self, symbol: str, reason: str, actor: str = "admin") -> Dict[str, Any]:
        """심볼 블랙리스트 제거"""
        before_state = self._load_state()
        
        after_blacklist = before_state.symbol_blacklist.copy()
        if symbol in after_blacklist:
            after_blacklist.remove(symbol)
        
        after_state = ControlState(
            mode=before_state.mode,
            symbol_blacklist=after_blacklist,
            updated_by=actor,
            reason=f"Blacklist remove: {symbol} - {reason}",
        )
        
        self._save_state(after_state)
        
        audit_entry = AuditLogEntry(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            command="blacklist_remove",
            args={"symbol": symbol, "reason": reason},
            before_state=before_state.to_dict(),
            after_state=after_state.to_dict(),
            result="ok",
        )
        self._append_audit_log(audit_entry)
        
        logger.info(f"[D205-12 AdminControl] Blacklist REMOVE: {symbol} by {actor}")
        return {
            "status": "ok",
            "symbol": symbol,
            "blacklist": list(after_blacklist),
        }
    
    def status(self) -> Dict[str, Any]:
        """현재 제어 상태 조회"""
        state = self._load_state()
        return {
            "mode": state.mode.value,
            "symbol_blacklist": list(state.symbol_blacklist),
            "updated_at_utc": state.updated_at_utc,
            "updated_by": state.updated_by,
            "reason": state.reason,
        }
    
    def should_process_tick(self) -> bool:
        """엔진 루프에서 호출: tick 처리 허용 여부"""
        state = self._load_state()
        return state.mode in [ControlMode.RUNNING]
    
    def is_symbol_blacklisted(self, symbol: str) -> bool:
        """엔진 루프에서 호출: 심볼 블랙리스트 체크"""
        state = self._load_state()
        return symbol in state.symbol_blacklist
