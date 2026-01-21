# -*- coding: utf-8 -*-
"""
D80-3: Trade-level Logging Module
트레이드 레벨 로깅 모듈

목적:
    각 round trip의 스프레드/유동성/체결 정보를 JSONL 파일로 로깅하여,
    D80-4 (Fill Model), D81-x (Market Impact) 분석에 활용.

설계 원칙:
    - 최소 침습: 기존 엔진 코드 수정 최소화
    - 확장 가능: 향후 PostgreSQL 통합 가능한 구조
    - 성능 고려: 파일 I/O 최소화 (버퍼링)

Author: arbitrage-lite project
Date: 2025-12-04
"""

import json
import logging
import statistics
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class TradeLogEntry:
    """
    Trade-level 로그 엔트리
    
    각 round trip (또는 개별 레그)마다 하나씩 생성.
    D80-4, D81-x에서 슬리피지/Market Impact 분석에 활용.
    
    Attributes:
        timestamp: 로그 생성 시각 (ISO 8601)
        session_id: D77 run session ID
        trade_id: 고유 거래 ID
        universe_mode: Universe 모드 ("TOP_20", "TOP_50", etc.)
        symbol: 거래 심볼 ("BTC/USDT", etc.)
        route_type: 라우팅 타입 ("cross_exchange", etc.)
        
        # 진입 정보
        entry_timestamp: 진입 시각
        entry_bid_upbit: 진입 시 Upbit bid 가격
        entry_ask_upbit: 진입 시 Upbit ask 가격
        entry_bid_binance: 진입 시 Binance bid 가격
        entry_ask_binance: 진입 시 Binance ask 가격
        entry_spread_bps: 진입 시 스프레드 (basis points)
        entry_bid_volume_upbit: 진입 시 Upbit bid 호가 잔량
        entry_ask_volume_binance: 진입 시 Binance ask 호가 잔량
        
        # 퇴출 정보
        exit_timestamp: 퇴출 시각
        exit_bid_upbit: 퇴출 시 Upbit bid 가격
        exit_ask_upbit: 퇴출 시 Upbit ask 가격
        exit_bid_binance: 퇴출 시 Binance bid 가격
        exit_ask_binance: 퇴출 시 Binance ask 가격
        exit_spread_bps: 퇴출 시 스프레드 (basis points)
        exit_bid_volume_upbit: 퇴출 시 Upbit bid 호가 잔량
        exit_ask_volume_binance: 퇴출 시 Binance ask 호가 잔량
        
        # 체결 정보
        order_quantity: 주문 수량
        filled_quantity: 실제 체결 수량 (현재 PAPER는 100%)
        fill_price_upbit: Upbit 체결 가격
        fill_price_binance: Binance 체결 가격
        
        # 비용 정보
        fee_upbit_bps: Upbit 수수료 (bps, 추정치)
        fee_binance_bps: Binance 수수료 (bps, 추정치)
        estimated_slippage_bps: 추정 슬리피지 (현재는 0, D80-4에서 모델링)
        
        # D81-0: Fill Model 정보
        buy_slippage_bps: 매수 슬리피지 (D80-4+)
        sell_slippage_bps: 매도 슬리피지 (D80-4+)
        buy_fill_ratio: 매수 체결 비율 (0.0~1.0, D80-4+)
        sell_fill_ratio: 매도 체결 비율 (0.0~1.0, D80-4+)
        
        # PnL 정보
        gross_pnl_usd: 총 PnL (수수료 전)
        net_pnl_usd: 순 PnL (수수료 후)
        trade_result: "win", "loss", "breakeven"
        
        # 메타 정보
        execution_latency_ms: 진입→퇴출 소요 시간 (ms)
        risk_check_passed: RiskGuard 통과 여부
        notes: 추가 메모 (선택적)
    """
    
    # 기본 식별 정보
    timestamp: str
    session_id: str
    trade_id: str
    universe_mode: str
    symbol: str
    route_type: str = "cross_exchange"
    
    # 진입 정보
    entry_exchange_long: str = ""
    entry_exchange_short: str = ""
    entry_timestamp: str = ""
    entry_bid_upbit: float = 0.0
    entry_ask_upbit: float = 0.0
    entry_bid_binance: float = 0.0
    entry_ask_binance: float = 0.0
    entry_spread_bps: float = 0.0
    entry_bid_volume_upbit: float = 0.0
    entry_ask_volume_binance: float = 0.0
    
    # 퇴출 정보
    exit_timestamp: str = ""
    exit_bid_upbit: float = 0.0
    exit_ask_upbit: float = 0.0
    exit_bid_binance: float = 0.0
    exit_ask_binance: float = 0.0
    exit_spread_bps: float = 0.0
    exit_bid_volume_upbit: float = 0.0
    exit_ask_volume_binance: float = 0.0
    
    # 체결 정보
    order_quantity: float = 0.0
    filled_quantity: float = 0.0
    fill_price_upbit: float = 0.0
    fill_price_binance: float = 0.0
    
    # 비용 정보
    fee_upbit_bps: float = 5.0  # 기본값: 5bps
    fee_binance_bps: float = 4.0  # 기본값: 4bps
    estimated_slippage_bps: float = 0.0  # D80-4에서 모델링 예정
    
    # D81-0: Fill Model 정보
    buy_slippage_bps: float = 0.0
    sell_slippage_bps: float = 0.0
    buy_fill_ratio: float = 1.0  # 기본값: 100% 체결
    sell_fill_ratio: float = 1.0  # 기본값: 100% 체결
    
    # PnL 정보
    gross_pnl_usd: float = 0.0
    net_pnl_usd: float = 0.0
    trade_result: str = "win"  # "win", "loss", "breakeven"
    
    # 메타 정보
    execution_latency_ms: float = 0.0
    risk_check_passed: bool = True
    notes: str = ""


class TradeLogger:
    """
    Trade-level 로깅 인터페이스
    
    책임:
    - TradeLogEntry를 JSONL 파일로 저장
    - Run별 / Universe별 로그 파일 분리
    - 메타데이터 저장
    
    사용 예시:
        logger = TradeLogger(
            base_dir=Path("logs/d80-3/trades"),
            run_id="run_20251204_001336",
            universe_mode="TOP_20"
        )
        
        entry = TradeLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id="d77-0-top_20-20251204001337",
            trade_id="rt_001",
            symbol="BTC/USDT",
            ...
        )
        
        logger.log_trade(entry)
        logger.save_metadata({...})
    """
    
    def __init__(
        self,
        base_dir: Path,
        run_id: str,
        universe_mode: str,
        session_id: str = ""
    ):
        """
        TradeLogger 초기화
        
        Args:
            base_dir: 로그 베이스 디렉토리 (예: logs/d80-3/trades)
            run_id: 실행 ID (예: run_20251204_001336)
            universe_mode: Universe 모드 (예: TOP_20)
            session_id: 세션 ID (선택적, 메타데이터 저장 시 사용)
        """
        self.base_dir = Path(base_dir)
        self.run_id = run_id
        self.universe_mode = universe_mode
        self.session_id = session_id
        
        self.log_file = self._init_log_file()
        self.trade_count = 0
        
        logger.info(
            f"[D80-3] TradeLogger initialized: "
            f"log_file={self.log_file}, universe={universe_mode}"
        )
    
    def _init_log_file(self) -> Path:
        """
        로그 파일 초기화
        
        로그 파일 경로: {base_dir}/{run_id}/{universe_label}_trade_log.jsonl
        예: logs/d80-3/trades/run_20251204_001336/top20_trade_log.jsonl
        
        Returns:
            로그 파일 경로
        """
        run_dir = self.base_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Universe 모드를 파일명으로 변환 (TOP_20 -> top20)
        universe_label = self.universe_mode.lower().replace("_", "")
        log_file = run_dir / f"{universe_label}_trade_log.jsonl"
        
        return log_file
    
    def log_trade(self, entry: TradeLogEntry) -> None:
        """
        Trade 로그 기록
        
        JSONL 형식으로 한 줄씩 append.
        파일 I/O 오버헤드를 최소화하기 위해 버퍼링 사용.
        
        Args:
            entry: TradeLogEntry 객체
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                json.dump(asdict(entry), f, ensure_ascii=False)
                f.write("\n")
            
            self.trade_count += 1
            
            # 100개마다 로그 출력 (성능 고려)
            if self.trade_count % 100 == 0:
                logger.info(
                    f"[D80-3] {self.trade_count} trades logged to {self.log_file.name}"
                )
        
        except Exception as e:
            logger.error(f"[D80-3] Failed to log trade: {e}", exc_info=True)
    
    def save_metadata(self, metadata: dict) -> None:
        """
        Run 메타데이터 저장
        
        메타데이터 파일: {base_dir}/{run_id}/metadata.json
        
        Args:
            metadata: 메타데이터 딕셔너리
        """
        try:
            metadata_file = self.log_file.parent / "metadata.json"
            
            # 기본 메타데이터 추가
            metadata["run_id"] = self.run_id
            metadata["universe_mode"] = self.universe_mode
            metadata["log_file"] = self.log_file.name
            metadata["total_trades_logged"] = self.trade_count
            metadata["version"] = "D80-3"
            
            if self.session_id:
                metadata["session_id"] = self.session_id
            
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[D80-3] Metadata saved to {metadata_file}")
        
        except Exception as e:
            logger.error(f"[D80-3] Failed to save metadata: {e}", exc_info=True)
    
    def get_trade_count(self) -> int:
        """
        현재까지 로깅된 트레이드 수 반환
        
        Returns:
            트레이드 수
        """
        return self.trade_count
    
    def get_aggregated_fill_metrics(self) -> dict:
        """
        D82-1: 로그된 트레이드에서 Fill Model 관련 KPI 집계.
        
        Returns:
            dict with keys:
            - avg_buy_slippage_bps
            - avg_sell_slippage_bps
            - avg_buy_fill_ratio
            - avg_sell_fill_ratio
            - partial_fills_count
            - failed_fills_count (항상 0, ExecutionResult에서 필터링됨)
        """
        if not self.log_file.exists():
            return {
                "avg_buy_slippage_bps": 0.0,
                "avg_sell_slippage_bps": 0.0,
                "avg_buy_fill_ratio": 1.0,
                "avg_sell_fill_ratio": 1.0,
                "partial_fills_count": 0,
                "failed_fills_count": 0,
            }
        
        buy_slippages = []
        sell_slippages = []
        buy_fill_ratios = []
        sell_fill_ratios = []
        partial_fills_count = 0
        
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        entry = json.loads(line)
                        
                        # Collect slippages
                        if "buy_slippage_bps" in entry and entry["buy_slippage_bps"] is not None:
                            buy_slippages.append(float(entry["buy_slippage_bps"]))
                        if "sell_slippage_bps" in entry and entry["sell_slippage_bps"] is not None:
                            sell_slippages.append(float(entry["sell_slippage_bps"]))
                        
                        # Collect fill ratios
                        if "buy_fill_ratio" in entry and entry["buy_fill_ratio"] is not None:
                            buy_fill_ratios.append(float(entry["buy_fill_ratio"]))
                        if "sell_fill_ratio" in entry and entry["sell_fill_ratio"] is not None:
                            sell_fill_ratios.append(float(entry["sell_fill_ratio"]))
                        
                        # Count partial fills
                        buy_ratio = float(entry.get("buy_fill_ratio", 1.0))
                        sell_ratio = float(entry.get("sell_fill_ratio", 1.0))
                        if buy_ratio < 1.0 or sell_ratio < 1.0:
                            partial_fills_count += 1
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            logger.error(f"[D82-1] Failed to aggregate fill metrics: {e}")
        
        return {
            "avg_buy_slippage_bps": sum(buy_slippages) / len(buy_slippages) if buy_slippages else 0.0,
            "avg_sell_slippage_bps": sum(sell_slippages) / len(sell_slippages) if sell_slippages else 0.0,
            "avg_buy_fill_ratio": sum(buy_fill_ratios) / len(buy_fill_ratios) if buy_fill_ratios else 1.0,
            "avg_sell_fill_ratio": sum(sell_fill_ratios) / len(sell_fill_ratios) if sell_fill_ratios else 1.0,
            "partial_fills_count": partial_fills_count,
            "failed_fills_count": 0,  # PaperExecutor doesn't generate failed fills
        }
    
    def close(self) -> None:
        """
        TradeLogger 종료 (현재는 no-op, 향후 버퍼 플러시 등 추가 가능)
        """
        logger.info(
            f"[D80-3] TradeLogger closed: {self.trade_count} trades logged"
        )


def create_mock_trade_entry(
    trade_id: str,
    session_id: str,
    universe_mode: str,
    symbol: str = "BTC/USDT"
) -> TradeLogEntry:
    """
    Mock TradeLogEntry 생성 (테스트/개발용)
    
    Args:
        trade_id: 거래 ID
        session_id: 세션 ID
        universe_mode: Universe 모드
        symbol: 심볼 (기본값: BTC/USDT)
    
    Returns:
        Mock TradeLogEntry
    """
    now = datetime.now(timezone.utc).isoformat()
    
    return TradeLogEntry(
        timestamp=now,
        session_id=session_id,
        trade_id=trade_id,
        universe_mode=universe_mode,
        symbol=symbol,
        route_type="cross_exchange",
        entry_exchange_long="upbit",
        entry_exchange_short="binance",
        entry_timestamp=now,
        entry_bid_upbit=45000.5,
        entry_ask_upbit=45010.2,
        entry_bid_binance=44980.1,
        entry_ask_binance=44990.3,
        entry_spread_bps=45.0,
        entry_bid_volume_upbit=2.5,
        entry_ask_volume_binance=3.2,
        exit_timestamp=now,
        exit_bid_upbit=45005.0,
        exit_ask_upbit=45015.0,
        exit_bid_binance=44985.0,
        exit_ask_binance=44995.0,
        exit_spread_bps=44.0,
        exit_bid_volume_upbit=2.3,
        exit_ask_volume_binance=3.0,
        order_quantity=0.1,
        filled_quantity=0.1,
        fill_price_upbit=45010.2,
        fill_price_binance=44990.3,
        fee_upbit_bps=5.0,
        fee_binance_bps=4.0,
        estimated_slippage_bps=0.0,
        gross_pnl_usd=19.90,
        net_pnl_usd=18.92,
        trade_result="win",
        execution_latency_ms=3333.0,
        risk_check_passed=True,
        notes="Mock trade entry for testing"
    )


# =============================================================================
# D82-8: Runtime Edge Monitor
# =============================================================================

@dataclass
class EdgeSnapshot:
    """
    Runtime Edge 스냅샷
    
    특정 시점의 Rolling Window Edge 통계를 기록.
    D85-x Tuning Cluster, Adaptive Threshold에서 재사용 가능.
    """
    timestamp: str
    window_size: int  # 최근 N개 트레이드
    
    # Edge 통계
    avg_spread_bps: float
    avg_slippage_bps: float
    avg_fee_bps: float
    effective_edge_bps: float  # spread - slippage - fee
    
    # PnL 통계
    avg_pnl_bps: float
    total_pnl_usd: float
    
    # 거래 통계
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float


class RuntimeEdgeMonitor:
    """
    Runtime Edge Monitor
    
    목적:
        Real PAPER 실행 중에 Rolling Window 기준으로
        Effective Edge, Slippage, PnL 통계를 실시간 계산/로깅.
    
    설계:
        - Trade Logger가 남기는 TradeLogEntry 스트림을 구독
        - 최근 N개 트레이드 기준 Rolling Window 계산
        - Snapshot을 JSONL 형태로 로깅
        - Settings를 통해 on/off 가능
    
    Usage:
        monitor = RuntimeEdgeMonitor(window_size=50, output_path="logs/edge_monitor.jsonl")
        monitor.record_trade(trade_entry)
        snapshot = monitor.get_current_snapshot()
    """
    
    def __init__(
        self,
        window_size: int = 50,
        output_path: Optional[Path] = None,
        enabled: bool = True,
        fee_bps: float = 9.0  # Upbit 5bps + Binance 4bps
    ):
        """
        Args:
            window_size: Rolling window 크기 (최근 N개 트레이드)
            output_path: Snapshot 로그 파일 경로 (JSONL)
            enabled: 모니터 활성화 여부
            fee_bps: 고정 수수료 (bps)
        """
        self.window_size = window_size
        self.output_path = Path(output_path) if output_path else None
        self.enabled = enabled
        self.fee_bps = fee_bps
        
        # Rolling window buffer
        self.trade_buffer: List[TradeLogEntry] = []
        
        # 로그 파일 초기화
        if self.enabled and self.output_path:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"[EdgeMonitor] Initialized: window={window_size}, output={output_path}")
    
    def record_trade(self, trade: TradeLogEntry) -> None:
        """
        트레이드를 기록하고 Rolling Window 업데이트.
        
        Args:
            trade: TradeLogEntry 객체
        """
        if not self.enabled:
            return
        
        # Buffer에 추가
        self.trade_buffer.append(trade)
        
        # Window 크기 초과 시 오래된 트레이드 제거
        if len(self.trade_buffer) > self.window_size:
            self.trade_buffer.pop(0)
        
        # Snapshot 생성 & 로깅
        if len(self.trade_buffer) >= min(10, self.window_size):  # 최소 10개 이상부터
            snapshot = self.get_current_snapshot()
            if snapshot and self.output_path:
                self._log_snapshot(snapshot)
    
    def get_current_snapshot(self) -> Optional[EdgeSnapshot]:
        """
        현재 Rolling Window 기준 Edge Snapshot 생성.
        
        Returns:
            EdgeSnapshot 또는 None (트레이드가 부족한 경우)
        """
        if not self.enabled or len(self.trade_buffer) == 0:
            return None
        
        # Spread 계산 (Entry + Exit 평균)
        spreads = []
        for trade in self.trade_buffer:
            # Entry/Exit spread 평균
            if trade.entry_spread_bps and trade.exit_spread_bps:
                avg_spread = (trade.entry_spread_bps + trade.exit_spread_bps) / 2.0
                spreads.append(avg_spread)
        
        # Slippage 계산
        slippages = []
        for trade in self.trade_buffer:
            if trade.buy_slippage_bps and trade.sell_slippage_bps:
                avg_slip = (trade.buy_slippage_bps + trade.sell_slippage_bps) / 2.0
                slippages.append(avg_slip)
        
        # PnL 계산
        pnls_usd = []
        pnls_bps = []
        for trade in self.trade_buffer:
            if trade.net_pnl_usd is not None:
                pnls_usd.append(trade.net_pnl_usd)
                # PnL (bps) 추정: notional ≈ order_quantity * fill_price
                if trade.order_quantity and trade.fill_price_binance:
                    notional = trade.order_quantity * trade.fill_price_binance
                    if notional > 0:
                        pnl_bps = (trade.net_pnl_usd / notional) * 10000.0
                        pnls_bps.append(pnl_bps)
        
        # Win/Loss 카운트
        win_count = sum(1 for trade in self.trade_buffer if trade.trade_result == "win")
        loss_count = sum(1 for trade in self.trade_buffer if trade.trade_result == "loss")
        
        # 통계 계산
        avg_spread = statistics.mean(spreads) if spreads else 0.0
        avg_slip = statistics.mean(slippages) if slippages else 0.0
        avg_pnl_bps = statistics.mean(pnls_bps) if pnls_bps else 0.0
        total_pnl_usd = sum(pnls_usd) if pnls_usd else 0.0
        win_rate = win_count / len(self.trade_buffer) if len(self.trade_buffer) > 0 else 0.0
        
        # Effective Edge = Spread - Slippage - Fee
        effective_edge = avg_spread - avg_slip - self.fee_bps
        
        return EdgeSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            window_size=len(self.trade_buffer),
            avg_spread_bps=avg_spread,
            avg_slippage_bps=avg_slip,
            avg_fee_bps=self.fee_bps,
            effective_edge_bps=effective_edge,
            avg_pnl_bps=avg_pnl_bps,
            total_pnl_usd=total_pnl_usd,
            total_trades=len(self.trade_buffer),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate
        )
    
    def _log_snapshot(self, snapshot: EdgeSnapshot) -> None:
        """
        Snapshot을 JSONL 형태로 로깅.
        
        Args:
            snapshot: EdgeSnapshot 객체
        """
        if not self.output_path:
            return
        
        try:
            with open(self.output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(snapshot), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"[EdgeMonitor] Failed to log snapshot: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        현재 상태 요약.
        
        Returns:
            요약 딕셔너리
        """
        snapshot = self.get_current_snapshot()
        if not snapshot:
            return {
                "enabled": self.enabled,
                "window_size": self.window_size,
                "current_trades": len(self.trade_buffer),
                "status": "insufficient_data"
            }
        
        return {
            "enabled": self.enabled,
            "window_size": self.window_size,
            "current_trades": len(self.trade_buffer),
            "effective_edge_bps": snapshot.effective_edge_bps,
            "avg_pnl_bps": snapshot.avg_pnl_bps,
            "win_rate": snapshot.win_rate,
            "status": "active"
        }
