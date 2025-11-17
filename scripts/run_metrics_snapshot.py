#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metrics Snapshot Script
=======================
CSV 기반 로그 파일을 읽어 실시간 메트릭 요약을 출력합니다.

사용법:
    python scripts/run_metrics_snapshot.py

기능:
- 총 PnL (KRW)
- 승률 (%)
- 심볼별 PnL
- 최근 N개 트레이드 목록
- 거래소별 슬리피지 통계 (PHASE C3+)

Note:
    - PHASE C4에서는 CSV 기반으로만 동작합니다.
    - PHASE D에서 PostgreSQL backend로 교체 가능하도록 설계되었습니다.
"""

import csv
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
from collections import defaultdict

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.models import Position
from arbitrage.storage import CsvStorage


class MetricsSnapshot:
    """CSV 기반 메트릭 스냅샷 분석기"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.storage = CsvStorage(data_dir)
        self.positions: List[Position] = []
        self.orders_data: List[Dict] = []
        self.spreads_data: List[Dict] = []

    def load_data(self) -> None:
        """CSV 파일에서 데이터 로드"""
        self.positions = self.storage.load_positions()
        self._load_orders()
        self._load_spreads()

    def _load_orders(self) -> None:
        """orders.csv 로드"""
        orders_file = self.data_dir / "orders.csv"
        if not orders_file.exists():
            return
        
        with orders_file.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.orders_data = list(reader) if reader else []

    def _load_spreads(self) -> None:
        """spreads.csv 로드"""
        spreads_file = self.data_dir / "spreads.csv"
        if not spreads_file.exists():
            return
        
        with spreads_file.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.spreads_data = list(reader) if reader else []

    def calculate_total_pnl(self) -> tuple[float, int]:
        """총 PnL 계산
        
        Returns:
            (total_pnl_krw, closed_position_count)
        """
        total_pnl = 0.0
        closed_count = 0
        
        for pos in self.positions:
            if pos.status == "CLOSED" and pos.pnl_krw is not None:
                total_pnl += pos.pnl_krw
                closed_count += 1
        
        return total_pnl, closed_count

    def calculate_win_rate(self) -> tuple[float, int, int]:
        """승률 계산
        
        Returns:
            (win_rate_pct, win_count, total_count)
        """
        closed_positions = [p for p in self.positions if p.status == "CLOSED"]
        if not closed_positions:
            return 0.0, 0, 0
        
        win_count = sum(1 for p in closed_positions if p.pnl_krw is not None and p.pnl_krw > 0)
        total_count = len(closed_positions)
        win_rate = (win_count / total_count * 100) if total_count > 0 else 0.0
        
        return win_rate, win_count, total_count

    def calculate_symbol_pnl(self) -> Dict[str, float]:
        """심볼별 PnL 계산
        
        Returns:
            {symbol: total_pnl_krw}
        """
        symbol_pnl = defaultdict(float)
        
        for pos in self.positions:
            if pos.status == "CLOSED" and pos.pnl_krw is not None:
                symbol_pnl[pos.symbol] += pos.pnl_krw
        
        return dict(sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True))

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """최근 N개 트레이드 조회
        
        Args:
            limit: 조회할 트레이드 수
        
        Returns:
            트레이드 정보 리스트
        """
        closed_positions = [p for p in self.positions if p.status == "CLOSED"]
        closed_positions.sort(key=lambda p: p.timestamp_close or datetime.min, reverse=True)
        
        trades = []
        for pos in closed_positions[:limit]:
            if pos.pnl_krw is not None:
                trades.append({
                    "symbol": pos.symbol,
                    "open_time": pos.timestamp_open.isoformat() if pos.timestamp_open else "N/A",
                    "close_time": pos.timestamp_close.isoformat() if pos.timestamp_close else "N/A",
                    "pnl_krw": pos.pnl_krw,
                    "pnl_pct": pos.pnl_pct or 0.0,
                })
        
        return trades

    def calculate_slippage_stats(self) -> Dict[str, Dict]:
        """슬리피지 통계 계산 (PHASE C3+)
        
        Returns:
            {venue: {avg_slippage_bps, min_slippage_bps, max_slippage_bps, count}}
        """
        slippage_stats = defaultdict(lambda: {
            "total_bps": 0.0,
            "min_bps": float('inf'),
            "max_bps": 0.0,
            "count": 0,
        })
        
        for order in self.orders_data:
            venue = order.get("venue", "unknown")
            slippage_str = order.get("slippage_bps", "")
            
            if slippage_str:
                try:
                    slippage_bps = float(slippage_str)
                    stats = slippage_stats[venue]
                    stats["total_bps"] += slippage_bps
                    stats["min_bps"] = min(stats["min_bps"], slippage_bps)
                    stats["max_bps"] = max(stats["max_bps"], slippage_bps)
                    stats["count"] += 1
                except ValueError:
                    pass
        
        # 평균 계산
        result = {}
        for venue, stats in slippage_stats.items():
            if stats["count"] > 0:
                result[venue] = {
                    "avg_slippage_bps": stats["total_bps"] / stats["count"],
                    "min_slippage_bps": stats["min_bps"],
                    "max_slippage_bps": stats["max_bps"],
                    "count": stats["count"],
                }
        
        return result

    def print_summary(self) -> None:
        """메트릭 요약 출력"""
        print("\n" + "=" * 70)
        print("Arbitrage-Lite: Metrics Snapshot".center(70))
        print("=" * 70)
        
        # 데이터 로드 상태
        total_positions = len(self.positions)
        closed_positions = sum(1 for p in self.positions if p.status == "CLOSED")
        open_positions = total_positions - closed_positions
        
        print(f"\n📊 데이터 요약")
        print(f"  전체 포지션: {total_positions}")
        print(f"  청산됨: {closed_positions}")
        print(f"  진행 중: {open_positions}")
        
        if total_positions == 0:
            print("\n⚠️  데이터가 없습니다. 먼저 run_paper.py를 실행하세요.")
            return
        
        # 총 PnL
        total_pnl, closed_count = self.calculate_total_pnl()
        print(f"\n💰 총 PnL")
        print(f"  총 손익: {total_pnl:+,.0f} KRW")
        print(f"  청산 트레이드: {closed_count}")
        
        # 승률
        win_rate, win_count, total_count = self.calculate_win_rate()
        if total_count > 0:
            print(f"\n📈 승률")
            print(f"  승률: {win_rate:.1f}% ({win_count} / {total_count})")
        
        # 심볼별 PnL
        symbol_pnl = self.calculate_symbol_pnl()
        if symbol_pnl:
            print(f"\n🔤 심볼별 PnL")
            for symbol, pnl in symbol_pnl.items():
                print(f"  {symbol}: {pnl:+,.0f} KRW")
        
        # 슬리피지 통계
        slippage_stats = self.calculate_slippage_stats()
        if slippage_stats:
            print(f"\n📉 슬리피지 통계 (Order Routing & Slippage Model)")
            for venue, stats in sorted(slippage_stats.items()):
                print(f"  {venue}:")
                print(f"    평균: {stats['avg_slippage_bps']:.1f} bps")
                print(f"    최소: {stats['min_slippage_bps']:.1f} bps")
                print(f"    최대: {stats['max_slippage_bps']:.1f} bps")
                print(f"    샘플: {stats['count']}")
        
        # 최근 트레이드
        recent_trades = self.get_recent_trades(limit=10)
        if recent_trades:
            print(f"\n📋 최근 {len(recent_trades)} 트레이드")
            for i, trade in enumerate(recent_trades, 1):
                print(
                    f"  {i:2d}) {trade['symbol']} | "
                    f"{trade['open_time'][:19]} → {trade['close_time'][:19]} | "
                    f"{trade['pnl_krw']:+7.0f} KRW ({trade['pnl_pct']:+6.2f}%)"
                )
        
        print("\n" + "=" * 70)
        print(f"생성 시간: {datetime.now(timezone.utc).isoformat()}")
        print(f"데이터 경로: {self.data_dir.absolute()}")
        print("=" * 70 + "\n")


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Arbitrage-Lite Metrics Snapshot")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="데이터 디렉토리 (기본값: data)"
    )
    args = parser.parse_args()
    
    snapshot = MetricsSnapshot(data_dir=args.data_dir)
    snapshot.load_data()
    snapshot.print_summary()


if __name__ == "__main__":
    main()
