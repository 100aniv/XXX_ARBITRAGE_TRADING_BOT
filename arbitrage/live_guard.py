#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Guard (PHASE D10 + D47 확장)
==================================

실거래 모드 보호 및 안전 검증.
D47: LiveSafetyGuard - 실거래 모드 전용 가드 추가
"""

import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LiveGuardStatus:
    """실거래 보호 상태"""
    mode: str                   # mock | paper | live
    env_flag_ok: bool          # LIVE_TRADING=1 환경 변수
    confirm_file_ok: bool      # .live_trading_ok 파일
    safety_ready: bool         # D8 안전 검증
    ws_fresh: bool             # WebSocket 신선도
    redis_heartbeat_ok: bool   # Redis heartbeat
    dry_run_active: bool       # 드라이런 활성화
    reason_blocked: List[str]  # 차단 사유
    
    def is_live_allowed(self) -> bool:
        """실거래 허용 여부"""
        return (
            self.mode == "live"
            and self.env_flag_ok
            and self.confirm_file_ok
            and self.safety_ready
            and self.ws_fresh
            and self.redis_heartbeat_ok
            and not self.dry_run_active
            and len(self.reason_blocked) == 0
        )


class LiveGuard:
    """실거래 보호 시스템"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        safety_validator: Any = None,
        ws_manager: Any = None,
        redis_client: Any = None
    ):
        """
        Args:
            config: 설정
            safety_validator: SafetyValidator 객체
            ws_manager: WebSocket 매니저
            redis_client: Redis 클라이언트
        """
        self.config = config or {}
        self.safety_validator = safety_validator
        self.ws_manager = ws_manager
        self.redis_client = redis_client
        
        # 모드 설정
        mode_config = self.config.get("mode", {})
        self.current_mode = mode_config.get("current", "mock")
        
        # 보호 설정
        live_guards_config = self.config.get("live_guards", {})
        self.require_env_flag = live_guards_config.get("require_env_flag", True)
        self.require_confirm_file = live_guards_config.get("require_manual_confirm_file", True)
        self.require_safety_pass = live_guards_config.get("require_safety_pass", True)
        self.dry_run_on_startup = live_guards_config.get("dry_run_on_startup", True)
        self.dry_run_cycles = live_guards_config.get("dry_run_cycles", 3)
        
        # 프로젝트 루트
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.confirm_file_path = os.path.join(self.project_root, ".live_trading_ok")
    
    def evaluate(self, cycle_index: int = 0) -> LiveGuardStatus:
        """
        실거래 보호 상태 평가
        
        Args:
            cycle_index: 사이클 인덱스 (0부터 시작)
        
        Returns:
            LiveGuardStatus 객체
        """
        status = LiveGuardStatus(
            mode=self.current_mode,
            env_flag_ok=False,
            confirm_file_ok=False,
            safety_ready=False,
            ws_fresh=False,
            redis_heartbeat_ok=False,
            dry_run_active=False,
            reason_blocked=[]
        )
        
        # 모드가 live가 아니면 즉시 반환
        if self.current_mode != "live":
            logger.debug(f"[LiveGuard] Mode is {self.current_mode}, live checks skipped")
            return status
        
        # 환경 변수 확인
        if self.require_env_flag:
            env_flag = os.environ.get("LIVE_TRADING", "").strip()
            if env_flag == "1":
                status.env_flag_ok = True
            else:
                status.reason_blocked.append("LIVE_TRADING env var not set to '1'")
        else:
            status.env_flag_ok = True
        
        # 확인 파일 확인
        if self.require_confirm_file:
            if os.path.exists(self.confirm_file_path):
                status.confirm_file_ok = True
            else:
                status.reason_blocked.append(f".live_trading_ok file not found at {self.confirm_file_path}")
        else:
            status.confirm_file_ok = True
        
        # 안전 검증 확인
        if self.require_safety_pass and self.safety_validator:
            try:
                safety_stats = self.safety_validator.get_safety_stats()
                # 안전 거부가 0이면 OK
                if safety_stats.get("safety_rejections_count", 0) == 0:
                    status.safety_ready = True
                else:
                    status.reason_blocked.append(
                        f"Safety checks failed: {safety_stats['safety_rejections_count']} rejections"
                    )
            except Exception as e:
                status.reason_blocked.append(f"Safety validator error: {e}")
        else:
            status.safety_ready = True
        
        # WebSocket 신선도 확인
        if self.ws_manager:
            try:
                if self.ws_manager.is_healthy():
                    status.ws_fresh = True
                else:
                    status.reason_blocked.append("WebSocket not healthy")
            except Exception as e:
                logger.debug(f"[LiveGuard] WS check error: {e}")
                status.ws_fresh = False
                status.reason_blocked.append(f"WebSocket error: {e}")
        else:
            status.ws_fresh = True
        
        # Redis heartbeat 확인
        if self.redis_client:
            try:
                # Redis ping 테스트
                self.redis_client.ping()
                status.redis_heartbeat_ok = True
            except Exception as e:
                logger.debug(f"[LiveGuard] Redis check error: {e}")
                status.redis_heartbeat_ok = False
                status.reason_blocked.append(f"Redis heartbeat error: {e}")
        else:
            status.redis_heartbeat_ok = True
        
        # 드라이런 확인
        if self.dry_run_on_startup and cycle_index < self.dry_run_cycles:
            status.dry_run_active = True
            status.reason_blocked.append(
                f"Dry-run active: cycle {cycle_index} < {self.dry_run_cycles}"
            )
        
        return status
    
    def get_status_banner(self, status: LiveGuardStatus) -> str:
        """상태 배너 생성"""
        if status.is_live_allowed():
            return "🟢 LIVE TRADING ALLOWED"
        else:
            reasons = "\n  ".join(status.reason_blocked) if status.reason_blocked else "Unknown"
            return f"🔴 LIVE TRADING BLOCKED\n  {reasons}"


# ============================================================================
# D47: LiveSafetyGuard - 실거래 모드 전용 가드
# ============================================================================

@dataclass
class LiveGuardDecision:
    """실거래 주문 발행 전 가드 결정"""
    allowed: bool
    reason: Optional[str] = None
    session_stop: bool = False


class LiveSafetyGuard:
    """
    D47: 실거래 모드 전용 보안 가드
    
    역할:
    - 필수 조건 확인 (enabled, allowed_symbols, 잔고, 일일 손실 등)
    - dry_run_scale 적용
    - 주문 발행 직전 최종 검증
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: ArbitrageLiveConfig를 dict로 변환한 설정
                - live_trading.enabled: bool
                - live_trading.dry_run_scale: float (0.0~1.0)
                - live_trading.allowed_symbols: list[str]
                - live_trading.min_account_balance: float
                - live_trading.max_daily_loss: float
                - live_trading.max_notional_per_trade: float
        """
        self.config = config or {}
        self.live_trading_config = self.config.get("live_trading", {})
        
        # 설정 읽기
        self.enabled = self.live_trading_config.get("enabled", False)
        self.dry_run_scale = self.live_trading_config.get("dry_run_scale", 0.01)
        self.allowed_symbols = self.live_trading_config.get("allowed_symbols", [])
        self.min_account_balance = self.live_trading_config.get("min_account_balance", 50.0)
        self.max_daily_loss = self.live_trading_config.get("max_daily_loss", 20.0)
        self.max_notional_per_trade = self.live_trading_config.get("max_notional_per_trade", 50.0)
        
        # 통계
        self.total_orders_attempted = 0
        self.total_orders_allowed = 0
        self.total_orders_blocked = 0
        self.block_reasons = {}  # reason -> count
        
        logger.info(
            f"[D47_LIVE_GUARD] Initialized: "
            f"enabled={self.enabled}, dry_run_scale={self.dry_run_scale}, "
            f"allowed_symbols={self.allowed_symbols}"
        )
    
    def check_before_send_order(
        self,
        symbol: str,
        notional_usd: float,
        current_balance: float,
        current_daily_loss: float,
    ) -> LiveGuardDecision:
        """
        주문 발행 직전 최종 검증
        
        Args:
            symbol: 거래 심볼 (예: "KRW-BTC", "BTCUSDT")
            notional_usd: 주문 규모 (USD 기준)
            current_balance: 현재 계좌 잔고 (USD 기준)
            current_daily_loss: 현재 일일 손실 (USD 기준, 음수)
        
        Returns:
            LiveGuardDecision
        """
        self.total_orders_attempted += 1
        
        # 1) enabled 체크
        if not self.enabled:
            reason = "live_trading.enabled=False"
            self._record_block(reason)
            logger.warning(f"[D47_LIVE_GUARD] Order blocked: {reason}")
            return LiveGuardDecision(allowed=False, reason=reason)
        
        # 2) allowed_symbols 체크
        if self.allowed_symbols and symbol not in self.allowed_symbols:
            reason = f"symbol '{symbol}' not in allowed_symbols {self.allowed_symbols}"
            self._record_block(reason)
            logger.warning(f"[D47_LIVE_GUARD] Order blocked: {reason}")
            return LiveGuardDecision(allowed=False, reason=reason)
        
        # 3) min_account_balance 체크
        if current_balance < self.min_account_balance:
            reason = f"account balance {current_balance:.2f} < min {self.min_account_balance:.2f}"
            self._record_block(reason)
            logger.warning(f"[D47_LIVE_GUARD] Order blocked: {reason}")
            return LiveGuardDecision(allowed=False, reason=reason)
        
        # 4) max_daily_loss 체크
        if current_daily_loss < -self.max_daily_loss:
            reason = f"daily loss {current_daily_loss:.2f} exceeds max {-self.max_daily_loss:.2f}"
            self._record_block(reason)
            logger.warning(f"[D47_LIVE_GUARD] Order blocked: {reason}")
            return LiveGuardDecision(allowed=False, reason=reason, session_stop=True)
        
        # 5) max_notional_per_trade 체크
        if notional_usd > self.max_notional_per_trade:
            reason = f"notional {notional_usd:.2f} > max {self.max_notional_per_trade:.2f}"
            self._record_block(reason)
            logger.warning(f"[D47_LIVE_GUARD] Order blocked: {reason}")
            return LiveGuardDecision(allowed=False, reason=reason)
        
        # 모든 체크 통과
        self.total_orders_allowed += 1
        logger.info(
            f"[D47_LIVE_GUARD] Order allowed: {symbol} notional={notional_usd:.2f} "
            f"balance={current_balance:.2f} daily_loss={current_daily_loss:.2f}"
        )
        return LiveGuardDecision(allowed=True)
    
    def apply_dry_run_scale(self, original_qty: float) -> float:
        """
        dry_run_scale 적용하여 수량 축소
        
        Args:
            original_qty: 원래 계산된 수량
        
        Returns:
            축소된 수량
        """
        scaled_qty = original_qty * self.dry_run_scale
        if scaled_qty != original_qty:
            logger.debug(
                f"[D47_LIVE_GUARD] Quantity scaled: {original_qty:.8f} → {scaled_qty:.8f} "
                f"(scale={self.dry_run_scale})"
            )
        return scaled_qty
    
    def _record_block(self, reason: str):
        """차단 사유 기록"""
        self.total_orders_blocked += 1
        self.block_reasons[reason] = self.block_reasons.get(reason, 0) + 1
    
    def get_summary(self) -> Dict[str, Any]:
        """통계 요약"""
        return {
            "total_orders_attempted": self.total_orders_attempted,
            "total_orders_allowed": self.total_orders_allowed,
            "total_orders_blocked": self.total_orders_blocked,
            "block_reasons": self.block_reasons,
        }
