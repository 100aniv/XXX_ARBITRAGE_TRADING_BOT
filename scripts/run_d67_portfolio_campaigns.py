#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D67: MULTISYMBOL_PORTFOLIO_PNL_AGGREGATION – Campaign Test Suite

목표: 멀티심볼 환경에서 심볼별 PnL을 포트폴리오 레벨로 집계하고,
      전체 포트폴리오 PnL/Equity/Winrate를 계산하여 추적한다.

캠페인:
- P1 (Portfolio Mixed): BTC/ETH 모두 C3 패턴, 포트폴리오 레벨 집계
- P2 (Portfolio High/Low): BTC C2 (고승률), ETH C3 (저승률), 포트폴리오 레벨 집계
- P3 (Portfolio Balanced): BTC/ETH 모두 C3 패턴, 포트폴리오 레벨 집계

실행:
  python scripts/run_d67_portfolio_campaigns.py --duration-minutes 2 --campaigns P1,P2,P3
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.monitoring.metrics_collector import MetricsCollector

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'logs/d67_campaigns_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_engine() -> ArbitrageEngine:
    """ArbitrageEngine 설정"""
    config = ArbitrageConfig(
        min_spread_bps=20.0,
        taker_fee_a_bps=10.0,
        taker_fee_b_bps=10.0,
        slippage_bps=5.0,
        max_position_usd=5000.0,
        max_open_trades=1,
        close_on_spread_reversal=True,
        exchange_a_to_b_rate=2.5,
        bid_ask_spread_bps=100.0,
    )
    engine = ArbitrageEngine(config)
    logger.info(f"[D67_PORTFOLIO] Engine initialized")
    return engine


def setup_runner_for_symbol(
    engine: ArbitrageEngine,
    campaign_id: str,
    symbol_a: str,
    symbol_b: str,
    symbol_specific_pattern: str = None,
) -> ArbitrageLiveRunner:
    """
    ArbitrageLiveRunner 설정 (심볼별)
    
    Args:
        engine: ArbitrageEngine
        campaign_id: 캠페인 ID (P1/P2/P3)
        symbol_a: Symbol A (e.g., KRW-BTC)
        symbol_b: Symbol B (e.g., BTCUSDT)
        symbol_specific_pattern: 심볼별 패턴 (e.g., "C1", "C2", "C3")
    """
    exchange_a = PaperExchange()
    exchange_b = PaperExchange()
    
    from arbitrage.exchanges.base import OrderBookSnapshot
    
    # Symbol A 초기 호가 설정
    snapshot_a = OrderBookSnapshot(
        symbol=symbol_a,
        timestamp=time.time(),
        bids=[(100000.0, 1.0)],
        asks=[(100000.0, 1.0)],
    )
    exchange_a.set_orderbook(symbol_a, snapshot_a)
    
    # Symbol B 초기 호가 설정
    # BTC: 40,000 / ETH: 2,000 (기본값)
    if "BTC" in symbol_b.upper():
        base_price = 40000.0
    elif "ETH" in symbol_b.upper():
        base_price = 2000.0
    else:
        base_price = 40000.0  # 기본값
    
    snapshot_b = OrderBookSnapshot(
        symbol=symbol_b,
        timestamp=time.time(),
        bids=[(base_price, 1.0)],
        asks=[(base_price, 1.0)],
    )
    exchange_b.set_orderbook(symbol_b, snapshot_b)
    
    risk_limits = RiskLimits(
        max_notional_per_trade=5000.0,
        max_daily_loss=10000.0,
        max_open_trades=1,
    )
    
    config = ArbitrageLiveConfig(
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        mode="paper",
        data_source="paper",
        paper_spread_injection_interval=5,
        paper_simulation_enabled=True,
        risk_limits=risk_limits,
    )
    
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=config,
        metrics_collector=MetricsCollector(),
    )
    
    # D67: 캠페인 ID 설정
    # 심볼별 패턴이 지정되면 그것을 사용, 아니면 캠페인 ID 사용
    if symbol_specific_pattern:
        runner._paper_campaign_id = symbol_specific_pattern
        logger.info(
            f"[D67_PORTFOLIO] Runner initialized for campaign {campaign_id}, "
            f"symbols {symbol_a}/{symbol_b}, pattern={symbol_specific_pattern}"
        )
    else:
        runner._paper_campaign_id = campaign_id
        logger.info(
            f"[D67_PORTFOLIO] Runner initialized for campaign {campaign_id}, "
            f"symbols {symbol_a}/{symbol_b}"
        )
    
    return runner


def run_portfolio_campaign(
    campaign_id: str,
    symbols: List[Tuple[str, str]],
    symbol_patterns: Dict[str, str],
    duration_minutes: int,
) -> Dict:
    """
    포트폴리오 캠페인 실행
    
    Args:
        campaign_id: 캠페인 ID (P1/P2/P3)
        symbols: [(symbol_a, symbol_b), ...] 리스트
        symbol_patterns: {symbol_key: pattern} 매핑 (e.g., {"BTCUSDT": "C2", "ETHUSDT": "C3"})
        duration_minutes: 실행 시간 (분)
    
    Returns:
        캠페인 결과 dict (심볼별 + 포트폴리오 레벨)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"[D67_PORTFOLIO] Starting Campaign {campaign_id} ({duration_minutes} min)")
    logger.info(f"[D67_PORTFOLIO] Symbols: {symbols}")
    logger.info(f"[D67_PORTFOLIO] Patterns: {symbol_patterns}")
    logger.info(f"{'='*60}")
    
    # 각 심볼 쌍에 대해 Runner 생성
    runners: Dict[str, ArbitrageLiveRunner] = {}
    for symbol_a, symbol_b in symbols:
        key = f"{symbol_a}/{symbol_b}"
        engine = setup_engine()
        # 심볼별 패턴 조회
        pattern = symbol_patterns.get(symbol_b)
        runner = setup_runner_for_symbol(engine, campaign_id, symbol_a, symbol_b, pattern)
        runners[key] = runner
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    loop_count = 0
    
    # 심볼별 메트릭 추적
    symbol_metrics: Dict[str, Dict[str, float]] = {}
    for key in runners.keys():
        symbol_metrics[key] = {
            'entries': 0,
            'exits': 0,
            'winning_trades': 0,
            'pnl': 0.0,
        }
    
    prev_metrics: Dict[str, Dict[str, float]] = {}
    for key in runners.keys():
        prev_metrics[key] = {
            'entries': 0,
            'exits': 0,
            'winning_trades': 0,
            'pnl': 0.0,
        }
    
    while time.time() < end_time:
        try:
            loop_count += 1
            
            # 각 심볼에 대해 1회 루프 실행
            for key, runner in runners.items():
                success = runner.run_once()
                if not success:
                    logger.warning(f"[D67_PORTFOLIO] Loop {loop_count} failed for {key}")
                
                # 메트릭 수집 (D67: 심볼별 메트릭 사용)
                symbol = runner.config.symbol_b
                current_entries = runner._per_symbol_trades_opened.get(symbol, 0)
                current_exits = runner._per_symbol_trades_closed.get(symbol, 0)
                current_winning = runner._per_symbol_winning_trades.get(symbol, 0)
                current_pnl = runner._per_symbol_pnl.get(symbol, 0.0)
                
                if current_entries > prev_metrics[key]['entries']:
                    prev_metrics[key]['entries'] = current_entries
                    logger.info(f"[D67_PORTFOLIO] Entry detected for {key}! Total: {current_entries}")
                
                if current_exits > prev_metrics[key]['exits']:
                    prev_metrics[key]['exits'] = current_exits
                    logger.info(f"[D67_PORTFOLIO] Exit detected for {key}! Total: {current_exits}")
                
                symbol_metrics[key]['entries'] = current_entries
                symbol_metrics[key]['exits'] = current_exits
                symbol_metrics[key]['winning_trades'] = current_winning
                symbol_metrics[key]['pnl'] = current_pnl
            
            # D67: 포트폴리오 레벨 메트릭 계산
            portfolio_total_pnl = sum(metrics['pnl'] for metrics in symbol_metrics.values())
            portfolio_total_exits = sum(metrics['exits'] for metrics in symbol_metrics.values())
            portfolio_winning_trades = sum(metrics['winning_trades'] for metrics in symbol_metrics.values())
            portfolio_winrate = (portfolio_winning_trades / portfolio_total_exits * 100) if portfolio_total_exits > 0 else 0.0
            portfolio_equity = 10000.0 + portfolio_total_pnl  # 초기 자본 $10,000
            
            # 10초마다 진행 상황 출력
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                logger.info(f"[D67_PORTFOLIO] Loop {loop_count}: elapsed={elapsed:.1f}s")
                for key, metrics in symbol_metrics.items():
                    entries = metrics['entries']
                    exits = metrics['exits']
                    winning = metrics['winning_trades']
                    pnl = metrics['pnl']
                    winrate = (winning / exits * 100) if exits > 0 else 0.0
                    logger.info(
                        f"  {key}: entries={entries}, exits={exits}, "
                        f"winrate={winrate:.1f}%, pnl=${pnl:.2f}"
                    )
                
                # D67: 포트폴리오 레벨 요약
                logger.info(
                    f"  [PORTFOLIO] total_pnl=${portfolio_total_pnl:.2f}, "
                    f"equity=${portfolio_equity:.2f}, winrate={portfolio_winrate:.1f}%"
                )
            
            time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("[D67_PORTFOLIO] Campaign interrupted by user")
            break
        except Exception as e:
            logger.error(f"[D67_PORTFOLIO] Error in loop {loop_count}: {e}")
            break
    
    # 최종 결과
    elapsed = time.time() - start_time
    
    logger.info(f"\n[D67_PORTFOLIO] Campaign {campaign_id} completed:")
    
    campaign_results = {}
    for key, metrics in symbol_metrics.items():
        entries = metrics['entries']
        exits = metrics['exits']
        winning = metrics['winning_trades']
        pnl = metrics['pnl']
        winrate = (winning / exits * 100) if exits > 0 else 0.0
        
        campaign_results[key] = {
            'entries': entries,
            'exits': exits,
            'winrate': winrate,
            'pnl': pnl,
        }
        
        logger.info(f"  {key}:")
        logger.info(f"    Entries: {entries}")
        logger.info(f"    Exits: {exits}")
        logger.info(f"    Winrate: {winrate:.1f}%")
        logger.info(f"    PnL: ${pnl:.2f}")
    
    # D67: 포트폴리오 레벨 결과 추가
    portfolio_total_pnl = sum(metrics['pnl'] for metrics in symbol_metrics.values())
    portfolio_total_exits = sum(metrics['exits'] for metrics in symbol_metrics.values())
    portfolio_winning_trades = sum(metrics['winning_trades'] for metrics in symbol_metrics.values())
    portfolio_winrate = (portfolio_winning_trades / portfolio_total_exits * 100) if portfolio_total_exits > 0 else 0.0
    portfolio_equity = 10000.0 + portfolio_total_pnl
    
    campaign_results['PORTFOLIO'] = {
        'total_pnl': portfolio_total_pnl,
        'equity': portfolio_equity,
        'winrate': portfolio_winrate,
        'total_exits': portfolio_total_exits,
        'winning_trades': portfolio_winning_trades,
    }
    
    logger.info(f"  [PORTFOLIO LEVEL]:")
    logger.info(f"    Total PnL: ${portfolio_total_pnl:.2f}")
    logger.info(f"    Equity: ${portfolio_equity:.2f}")
    logger.info(f"    Winrate: {portfolio_winrate:.1f}%")
    logger.info(f"    Total Exits: {portfolio_total_exits}")
    
    return campaign_results


def check_acceptance(campaign_id: str, results: Dict) -> bool:
    """
    D67 Acceptance Criteria 검증
    
    Args:
        campaign_id: 캠페인 ID (P1/P2/P3)
        results: 캠페인 결과 dict (심볼별 + 포트폴리오 레벨)
    
    Returns:
        모든 기준을 만족하면 True
    """
    logger.info(f"\n[D67_PORTFOLIO] Acceptance Criteria Check:")
    
    all_pass = True
    
    # 심볼별 기준 검증
    for key, metrics in results.items():
        if key == 'PORTFOLIO':
            continue  # 포트폴리오 레벨은 나중에 검증
        
        entries = metrics['entries']
        exits = metrics['exits']
        winrate = metrics['winrate']
        pnl = metrics['pnl']
        
        logger.info(f"  {key}:")
        
        # 공통 기준
        entry_pass = entries >= 5
        exit_pass = exits >= 5
        winrate_calculable = exits > 0
        pnl_pass = pnl != 0.0
        
        logger.info(f"    Entries >= 5: {'PASS' if entry_pass else 'FAIL'} ({entries})")
        logger.info(f"    Exits >= 5: {'PASS' if exit_pass else 'FAIL'} ({exits})")
        logger.info(f"    Winrate calculable: {'PASS' if winrate_calculable else 'FAIL'} ({winrate:.1f}%)")
        logger.info(f"    PnL != 0: {'PASS' if pnl_pass else 'FAIL'} (${pnl:.2f})")
        
        all_pass = all_pass and entry_pass and exit_pass and winrate_calculable and pnl_pass
    
    # D67: 포트폴리오 레벨 기준 검증
    if 'PORTFOLIO' in results:
        portfolio = results['PORTFOLIO']
        total_pnl = portfolio['total_pnl']
        equity = portfolio['equity']
        total_exits = portfolio['total_exits']
        
        logger.info(f"  [PORTFOLIO LEVEL]:")
        
        pnl_pass = total_pnl != 0.0
        equity_pass = equity > 0.0
        exits_pass = total_exits >= 10  # 최소 10개 이상의 거래
        
        # 심볼 독립성 검증: BTC와 ETH의 Entries/Exits가 독립적으로 추적되는지 확인
        btc_entries = None
        eth_entries = None
        btc_exits = None
        eth_exits = None
        for key, metrics in results.items():
            if key == 'PORTFOLIO':
                continue
            if 'BTC' in key.upper():
                btc_entries = metrics['entries']
                btc_exits = metrics['exits']
            elif 'ETH' in key.upper():
                eth_entries = metrics['entries']
                eth_exits = metrics['exits']
        
        independence_pass = True
        if btc_entries is not None and eth_entries is not None:
            # 각 심볼이 독립적으로 거래되고 있는지 확인 (0이 아닌지만 확인)
            independence_pass = btc_entries > 0 and eth_entries > 0 and btc_exits > 0 and eth_exits > 0
            logger.info(f"    Symbol Independence (Entries/Exits > 0): {'PASS' if independence_pass else 'FAIL'} (BTC: {btc_entries}/{btc_exits}, ETH: {eth_entries}/{eth_exits})")
        
        logger.info(f"    Total PnL != 0: {'PASS' if pnl_pass else 'FAIL'} (${total_pnl:.2f})")
        logger.info(f"    Equity > 0: {'PASS' if equity_pass else 'FAIL'} (${equity:.2f})")
        logger.info(f"    Total Exits >= 10: {'PASS' if exits_pass else 'FAIL'} ({total_exits})")
        
        all_pass = all_pass and pnl_pass and equity_pass and exits_pass and independence_pass
    
    return all_pass


def main():
    parser = argparse.ArgumentParser(description="D67 Portfolio Campaign Runner")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=2,
        help="Campaign duration in minutes (default: 2)"
    )
    parser.add_argument(
        "--campaigns",
        type=str,
        default="P1,P2,P3",
        help="Campaigns to run (comma-separated, default: P1,P2,P3)"
    )
    
    args = parser.parse_args()
    
    campaigns = args.campaigns.split(",")
    duration_minutes = args.duration_minutes
    
    # 캠페인별 심볼 설정
    campaign_symbols = {
        "P1": [("KRW-BTC", "BTCUSDT"), ("KRW-ETH", "ETHUSDT")],
        "P2": [("KRW-BTC", "BTCUSDT"), ("KRW-ETH", "ETHUSDT")],
        "P3": [("KRW-BTC", "BTCUSDT"), ("KRW-ETH", "ETHUSDT")],
    }
    
    # 캠페인별 심볼 패턴 설정
    # P1: BTC/ETH 모두 C3 (포트폴리오 Mixed)
    # P2: BTC는 C2 (고승률), ETH는 C3 (저승률) - 포트폴리오 밸런스
    # P3: BTC/ETH 모두 C3 (포트폴리오 Balanced)
    campaign_patterns = {
        "P1": {"BTCUSDT": "C3", "ETHUSDT": "C3"},
        "P2": {"BTCUSDT": "C2", "ETHUSDT": "C3"},
        "P3": {"BTCUSDT": "C3", "ETHUSDT": "C3"},
    }
    
    all_results = {}
    all_pass = True
    
    for campaign_id in campaigns:
        if campaign_id not in campaign_symbols:
            logger.error(f"[D67_PORTFOLIO] Unknown campaign: {campaign_id}")
            continue
        
        symbols = campaign_symbols[campaign_id]
        patterns = campaign_patterns.get(campaign_id, {})
        results = run_portfolio_campaign(campaign_id, symbols, patterns, duration_minutes)
        all_results[campaign_id] = results
        
        # Acceptance Criteria 검증
        campaign_pass = check_acceptance(campaign_id, results)
        all_pass = all_pass and campaign_pass
        
        if campaign_pass:
            logger.info(f"[D67_PORTFOLIO] Campaign {campaign_id}: PASS")
        else:
            logger.info(f"[D67_PORTFOLIO] Campaign {campaign_id}: FAIL")
    
    # 최종 보고서
    logger.info(f"\n{'='*60}")
    logger.info(f"[D67_PORTFOLIO] FINAL REPORT")
    logger.info(f"{'='*60}")
    
    for campaign_id, results in all_results.items():
        logger.info(f"\nCampaign {campaign_id}:")
        for key, metrics in results.items():
            if key == 'PORTFOLIO':
                logger.info(
                    f"  [PORTFOLIO]: total_pnl=${metrics['total_pnl']:.2f}, "
                    f"equity=${metrics['equity']:.2f}, winrate={metrics['winrate']:.1f}%"
                )
            else:
                logger.info(
                    f"  {key}: entries={metrics['entries']}, exits={metrics['exits']}, "
                    f"winrate={metrics['winrate']:.1f}%, pnl=${metrics['pnl']:.2f}"
                )
    
    if all_pass:
        logger.info(f"\n[D67_PORTFOLIO] D67_ACCEPTED: All campaigns passed acceptance criteria")
        return 0
    else:
        logger.error(f"\n[D67_PORTFOLIO] D67_FAILED: Some campaigns did not pass acceptance criteria")
        return 1


if __name__ == "__main__":
    sys.exit(main())
