#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Trading Script (PHASE D4 + D13)
====================================

실거래 모드 실행 스크립트 (D13: 시크릿 관리).

⚠️  경고: 실제 자금이 사용됩니다!

실행 방법:
    python scripts/run_live.py
    python scripts/run_live.py --mock  (Mock 모드)

기능:
- Live API 연동 (Upbit, Binance)
- 메트릭 서버 실행
- Paper/Live 모드 전환
- D13: 시크릿 관리 (.env 지원)
"""

import argparse
import sys
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# D13: 시크릿 매니저 초기화 (가장 먼저)
try:
    from arbitrage.secrets import init_secrets
    secrets = init_secrets(env_file=str(project_root / ".env"), fail_on_missing=False)
    logger_temp = logging.getLogger("arbitrage.run_live")
    logger_temp.info("[D13] Secrets manager initialized")
except Exception as e:
    logger_temp = logging.getLogger("arbitrage.run_live")
    logger_temp.warning(f"[D13] Secrets manager initialization failed: {e}")

from arbitrage.live_api import get_live_api
from arbitrage.metrics import get_metrics_collector
from arbitrage.metrics_server import get_metrics_server
from arbitrage.storage import get_storage
from arbitrage.ws_manager import get_ws_manager
from arbitrage.signal_engine import ArbitrageSignalEngine
from arbitrage.execution_engine import ExecutionEngine
from arbitrage.order_manager import OrderManager
from arbitrage.safety import SafetyContext, SafetyValidator
from arbitrage.position_engine import PositionEngine
from arbitrage.stoploss import StopLossEngine
from arbitrage.rebalancer import RebalancerEngine
from arbitrage.alert import AlertSystem
from arbitrage.live_guard import LiveGuard
from arbitrage.watchdog import Watchdog, WatchdogConfig
from arbitrage.sys_monitor import SystemMonitor, SysMonitorConfig
from arbitrage.logging_utils import get_live_loop_logger
from arbitrage.longrun import LongRunTester
from arbitrage.perf import PerformanceProfiler

# 로깅 설정 (D11: 공통 로거 사용)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = get_live_loop_logger()


def parse_args() -> argparse.Namespace:
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Arbitrage-Lite Live Trading (PHASE D4)"
    )
    parser.add_argument(
        "--config",
        default="config/live.yml",
        help="설정 파일 경로"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock 모드 (API KEY 없을 때 자동 활성화)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="루프 간격 (초)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="한 번만 실행 후 종료"
    )
    parser.add_argument(
        "--ws-test",
        action="store_true",
        help="WebSocket 테스트 모드"
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=None,
        help="최대 루프 수 (지정 시 --once 무시)"
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "paper", "live"],
        default=None,
        help="실행 모드 (config 파일 오버라이드)"
    )
    return parser.parse_args()


def load_live_config(config_path: str) -> dict:
    """Live 설정 파일 로드
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        설정 딕셔너리
    """
    import yaml
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except UnicodeDecodeError:
        # Windows 환경 폴백
        with open(config_path, 'r', encoding='cp949') as f:
            return yaml.safe_load(f)


def main():
    """메인 함수"""
    args = parse_args()
    
    logger.info("[LIVE] Starting Live Trading Service (PHASE D4)")
    
    # 설정 로드
    try:
        config = load_live_config(args.config)
    except Exception as e:
        logger.error(f"[LIVE] Failed to load config: {e}")
        return 1
    
    # 모드 판단 (--mode 옵션이 우선)
    if args.mode:
        config["mode"]["current"] = args.mode
    
    current_mode = config.get("mode", {}).get("current", "mock")
    mock_mode = args.mock or current_mode == "mock"
    
    # 저장소 초기화
    storage = get_storage(config)
    logger.info(f"[LIVE] Storage initialized: {type(storage).__name__}")
    
    # Live API 초기화 (Upbit)
    upbit_config = config.get("upbit", {})
    upbit_api = get_live_api(config, exchange="upbit")
    logger.info(f"[LIVE] Upbit API initialized (mock={mock_mode})")
    
    # Live API 초기화 (Binance)
    binance_config = config.get("binance", {})
    binance_api = get_live_api(config, exchange="binance")
    logger.info(f"[LIVE] Binance API initialized (mock={mock_mode})")
    
    # 메트릭 수집기 초기화
    metrics_collector = get_metrics_collector(storage)
    logger.info("[LIVE] Metrics collector initialized")
    
    # 시그널 엔진 초기화 (D7)
    signal_engine_config = config.get("signal_engine", {})
    signal_engine = ArbitrageSignalEngine(signal_engine_config)
    logger.info("[LIVE] Signal engine initialized")
    
    # 실행 엔진 초기화 (D7)
    execution_engine_config = config.get("execution_engine", {})
    execution_engine = ExecutionEngine(execution_engine_config)
    logger.info("[LIVE] Execution engine initialized")
    
    # 주문 관리자 초기화 (D7)
    order_manager_config = config.get("order_manager", {})
    order_manager = OrderManager(order_manager_config)
    logger.info("[LIVE] Order manager initialized")
    
    # 안전 검증기 초기화 (D8)
    safety_config = config.get("safety", {})
    safety_context = SafetyContext(safety_config)
    safety_validator = SafetyValidator(safety_context)
    logger.info("[LIVE] Safety validator initialized")
    
    # 포지션 엔진 초기화 (D9)
    position_engine_config = config.get("position_engine", {})
    position_engine = PositionEngine(position_engine_config)
    logger.info("[LIVE] Position engine initialized")
    
    # 손절매 엔진 초기화 (D9)
    stoploss_config = config.get("stoploss", {})
    stoploss_engine = StopLossEngine(stoploss_config)
    logger.info("[LIVE] Stop-loss engine initialized")
    
    # 리밸런싱 엔진 초기화 (D9)
    rebalancer_config = config.get("rebalancer", {})
    rebalancer_engine = RebalancerEngine(rebalancer_config)
    logger.info("[LIVE] Rebalancer engine initialized")
    
    # 알림 시스템 초기화 (D9)
    alert_config = config.get("alert", {})
    alert_system = AlertSystem(alert_config)
    logger.info("[LIVE] Alert system initialized")
    
    # LiveGuard 초기화 (D10)
    live_guard = LiveGuard(
        config=config,
        safety_validator=safety_validator,
        ws_manager=None,  # 아직 초기화되지 않음
        redis_client=None  # Redis 클라이언트 없음
    )
    logger.info("[LIVE] Live guard initialized")
    
    # 워치독 초기화 (D11)
    watchdog_config_dict = config.get("watchdog", {})
    watchdog_config = WatchdogConfig(
        max_ws_lag_ms=watchdog_config_dict.get("max_ws_lag_ms", 5000.0),
        ws_lag_warn_threshold_ms=watchdog_config_dict.get("ws_lag_warn_threshold_ms", 2000.0),
        max_redis_heartbeat_age_ms=watchdog_config_dict.get("max_redis_heartbeat_age_ms", 30000.0),
        redis_heartbeat_warn_threshold_ms=watchdog_config_dict.get("redis_heartbeat_warn_threshold_ms", 15000.0),
        max_loop_latency_ms=watchdog_config_dict.get("max_loop_latency_ms", 5000.0),
        loop_latency_warn_threshold_ms=watchdog_config_dict.get("loop_latency_warn_threshold_ms", 2000.0),
        max_safety_rejections_per_minute=watchdog_config_dict.get("max_safety_rejections_per_minute", 10),
        max_live_errors_per_minute=watchdog_config_dict.get("max_live_errors_per_minute", 5)
    )
    watchdog = Watchdog(watchdog_config)
    logger.info("[LIVE] Watchdog initialized")
    
    # 시스템 모니터 초기화 (D11)
    sys_monitor_config_dict = config.get("sys_monitor", {})
    sys_monitor_config = SysMonitorConfig(
        enabled=sys_monitor_config_dict.get("enabled", True),
        max_cpu_pct=sys_monitor_config_dict.get("max_cpu_pct", 90.0),
        max_rss_mb=sys_monitor_config_dict.get("max_rss_mb", 2048.0),
        warn_cpu_pct=sys_monitor_config_dict.get("warn_cpu_pct", 75.0),
        warn_rss_mb=sys_monitor_config_dict.get("warn_rss_mb", 1536.0),
        sample_interval_sec=sys_monitor_config_dict.get("sample_interval_sec", 30.0)
    )
    sys_monitor = SystemMonitor(sys_monitor_config)
    logger.info("[LIVE] System monitor initialized")
    
    # D12: 장시간 안정성 테스터 초기화
    longrun_config_dict = config.get("longrun", {})
    longrun_tester = LongRunTester(
        enabled=longrun_config_dict.get("enabled", True),
        interval_loops=longrun_config_dict.get("interval_loops", 50),
        snapshot_path=longrun_config_dict.get("snapshot_path", "logs/stability")
    )
    logger.info("[LIVE] Long-run tester initialized")
    
    # D12: 성능 프로파일러 초기화
    perf_profiler = PerformanceProfiler()
    logger.info("[LIVE] Performance profiler initialized")
    
    # WebSocket 매니저 초기화 (D6)
    ws_config = config.get("websocket", {})
    ws_manager = get_ws_manager(ws_config)
    if ws_config.get("enabled", False):
        if ws_manager.start():
            logger.info("[LIVE] WebSocket manager started")
            # 콜백 등록
            ws_manager.register_callback(lambda data: logger.debug(f"[LIVE] WS price: {data}"))
    
    # 메트릭 서버 초기화 (선택적)
    metrics_server_config = config.get("metrics_server", {})
    if metrics_server_config.get("enabled", True):
        metrics_server = get_metrics_server(
            host=metrics_server_config.get("host", "0.0.0.0"),
            port=metrics_server_config.get("port", 8000)
        )
        metrics_server.set_metrics_collector(metrics_collector)
        logger.info(
            f"[LIVE] Metrics server initialized "
            f"({metrics_server_config.get('host')}:{metrics_server_config.get('port')})"
        )
    
    # 메인 루프
    iteration_count = 0
    logger.info(
        f"[LIVE] Starting loop (interval={args.interval}s, once={args.once}, mock={mock_mode})"
    )
    
    try:
        while True:
            loop_start = time.monotonic()
            iteration_count += 1
            
            # D10: LiveGuard 평가
            live_status = live_guard.evaluate(iteration_count - 1)
            is_live_allowed = live_status.is_live_allowed()
            
            # 실거래 모드 배너 출력
            if iteration_count == 1:
                banner = live_guard.get_status_banner(live_status)
                logger.warning(f"[LIVE] {banner}")
            
            # 시세 조회
            upbit_ticker = upbit_api.get_ticker("BTC-KRW")
            binance_ticker = binance_api.get_ticker("BTCUSDT")
            
            # 시그널 계산 (D7)
            if upbit_ticker and binance_ticker:
                ticker_data = {
                    "upbit_bid": upbit_ticker.bid,
                    "upbit_ask": upbit_ticker.ask,
                    "binance_bid": binance_ticker.bid,
                    "binance_ask": binance_ticker.ask
                }
                
                signal = signal_engine.compute_signal(ticker_data)
                
                # 신호 기반 주문 실행 (D7)
                if signal and signal.confidence > 0.5:
                    logger.info(
                        f"[SIGNAL] arbitrage opportunity detected: "
                        f"{signal.opportunity_type}, profit={signal.profit_pct:.2f}%"
                    )
                    
                    success, order_ids = execution_engine.execute_signal(
                        signal=signal,
                        upbit_api=upbit_api,
                        binance_api=binance_api,
                        order_manager=order_manager,
                        safety_validator=safety_validator
                    )
                    
                    if success:
                        logger.info(f"[EXEC] Orders executed: {order_ids}")
            
            # D9: 리밸런싱 체크
            current_exposure = position_engine.get_total_exposure_krw()
            if rebalancer_engine.should_rebalance(current_exposure):
                reduction = rebalancer_engine.calculate_reduction(current_exposure)
                positions_to_close = rebalancer_engine.rebalance(position_engine, reduction)
                if positions_to_close:
                    alert_system.alert_rebalance_executed(len(positions_to_close), reduction)
            
            # D10: 루프 타이밍 기록
            loop_end = time.monotonic()
            loop_latency_ms = (loop_end - loop_start) * 1000
            metrics_collector.record_loop_timing(
                loop_start_time=loop_start,
                loop_end_time=loop_end,
                ws_last_tick=None,
                redis_last_heartbeat=None,
                is_live_trade=is_live_allowed,
                live_status=live_status
            )
            
            # D11: 시스템 모니터링
            sys_sample = sys_monitor.sample()
            sys_stats = sys_monitor.get_stats()
            
            # 메트릭 수집 (D8: 안전 통계 + D9: 포지션 통계 + D10: 성능 + D11: 시스템)
            metrics_data = metrics_collector.get_metrics()
            
            # D12: 성능 프로파일러 기록
            perf_profiler.record_loop(loop_latency_ms)
            perf_profiler.record_ws_lag(metrics_data.get("ws_lag_ms", 0.0))
            perf_profiler.record_redis_heartbeat(metrics_data.get("redis_heartbeat_age_ms", 0.0))
            
            # D12: 장시간 테스터 기록
            longrun_tester.record_loop(loop_latency_ms)
            
            # 통계 수집
            exec_stats = execution_engine.get_stats()
            safety_stats = safety_validator.get_safety_stats()
            position_stats = position_engine.get_stats()
            stoploss_stats = stoploss_engine.get_stats()
            alert_stats = alert_system.get_stats()
            
            # D12: 성능 메트릭 추가
            perf_metrics = perf_profiler.get_all_metrics()
            
            metrics_str = (
                f"[METRICS] pnl={metrics_data.get('pnl', 0)}₩ "
                f"trades={metrics_data.get('num_trades', 0)} "
                f"open_pos={position_stats['open_positions_count']} "
                f"exposure={position_stats['total_exposure_krw']:.0f}₩ "
                f"realized_pnl={position_stats['realized_pnl_today']:.0f}₩ "
                f"signals={exec_stats['total_signals']} "
                f"exec_rate={exec_stats['success_rate']:.1f}% "
                f"safety_rejections={safety_stats['safety_rejections_count']} "
                f"sl_triggers={stoploss_stats['stoploss_triggers']} "
                f"loop_ms={metrics_data.get('loop_latency_ms', 0):.1f} "
                f"loop_p95={perf_metrics.get('loop_p95_ms', 0):.1f} "
                f"cpu={sys_stats.get('cpu_pct', 0):.1f}% "
                f"mem={sys_stats.get('rss_mb', 0):.0f}MB "
                f"live={'✅' if is_live_allowed else '❌'}"
            )
            logger.info(f"[LIVE] {metrics_str}")
            
            # D11: 워치독 평가
            watchdog_status = watchdog.evaluate(metrics_data)
            if watchdog_status.alerts:
                alert_summary = watchdog.get_alert_summary()
                logger.warning(f"[WATCHDOG] {watchdog.get_status_summary()}\n{alert_summary}")
                
                # 경고 이벤트를 alert 시스템으로 전송 (선택)
                for alert_event in watchdog_status.alerts:
                    if alert_event.level.value == "ERROR":
                        alert_system.send_alert(
                            "watchdog",
                            f"{alert_event.component}: {alert_event.message}",
                            "ERROR"
                        )
            
            # 워치독이 shutdown을 요청하면 graceful shutdown
            if watchdog_status.should_shutdown:
                logger.critical(f"[WATCHDOG] {watchdog_status.shutdown_reason}")
                break
            
            # D12: 장시간 테스터 체크포인트
            checkpoint = longrun_tester.take_checkpoint(metrics_data)
            if checkpoint:
                logger.info(f"[LONGRUN] Checkpoint saved (loop={checkpoint.loop_count}, stable={checkpoint.is_stable})")
            
            # --once 모드 또는 --loops 모드 종료
            if args.once:
                logger.info("[LIVE] Exiting (--once mode)")
                break
            
            if args.loops and iteration_count >= args.loops:
                logger.info(f"[LIVE] Exiting (--loops {args.loops} completed)")
                break
            
            # 대기
            logger.debug(f"[LIVE] Waiting {args.interval}s...")
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("[LIVE] Interrupted by user")
    except Exception as e:
        logger.error(f"[LIVE] Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        # WebSocket 정리
        if ws_config.get("enabled", False):
            ws_manager.stop()
        logger.info(f"[LIVE] Shutting down (completed {iteration_count} iterations)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
