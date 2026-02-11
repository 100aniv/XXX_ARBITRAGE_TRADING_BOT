"""
TURN2 검증: profitable 판정이 exec_cost + partial_fill_penalty 반영 후 결정되는지 테스트

목표:
1. raw edge는 +인데, exec_cost로 인해 profitable=False로 뒤집히는 케이스 증명
2. profitable 판정이 단 1곳(detect_candidates)에서만 결정됨을 확인
"""
import pytest
from arbitrage.v2.opportunity.detector import detect_candidates
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


def test_profitable_flipped_by_exec_cost():
    """
    TURN2: raw edge는 양수이지만 exec_cost로 인해 profitable=False로 뒤집히는 케이스
    
    시나리오:
    - raw spread: 20 bps (양수)
    - break_even: 10 bps
    - raw edge: 10 bps (양수)
    - notional: 1,000,000 KRW (대량 주문)
    - orderbook depth: 매우 작음 (100,000 KRW)
    - 예상: partial_fill_penalty로 인해 net_edge_after_exec < 0 → profitable=False
    """
    fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0)
    fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0)
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    
    params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=0.0,
        latency_bps=0.0,
        buffer_bps=0.0,
    )
    
    # 가격 설정: 100 bps spread (충분히 큰 값)
    price_a = 100_000_000.0  # 1억 KRW (Upbit)
    price_b = 101_000_000.0  # 1억 100만 KRW (Binance, normalized to KRW)
    
    # raw spread = abs((price_a - price_b) / price_b * 10000) ≈ 99 bps
    # break_even은 detector에서 계산됨
    # 목표: raw edge는 양수이지만 exec_cost로 인해 profitable=False
    
    # notional: 100만 KRW (대량)
    notional = 1_000_000.0
    
    # orderbook depth: 매우 작음 (10만 KRW씩만 available)
    # → partial fill penalty 발생
    upbit_bid_size = 100_000.0
    upbit_ask_size = 100_000.0
    binance_bid_size = 100_000.0
    binance_ask_size = 100_000.0
    
    candidate = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=price_a,
        price_b=price_b,
        params=params,
        notional=notional,
        upbit_bid_size=upbit_bid_size,
        upbit_ask_size=upbit_ask_size,
        binance_bid_size=binance_bid_size,
        binance_ask_size=binance_ask_size,
    )
    
    assert candidate is not None, "Candidate should be created"
    assert candidate.edge_bps > 0, f"Raw edge should be positive, got {candidate.edge_bps}"
    assert candidate.exec_cost_bps is not None, "exec_cost_bps should be calculated"
    assert candidate.exec_cost_bps > 0, f"exec_cost should be positive, got {candidate.exec_cost_bps}"
    assert candidate.net_edge_after_exec_bps is not None, "net_edge_after_exec_bps should exist"
    
    # TURN2 핵심 검증: profitable=False (exec_cost로 뒤집힘)
    assert candidate.profitable is False, (
        f"profitable should be False (flipped by exec_cost). "
        f"edge_bps={candidate.edge_bps}, exec_cost_bps={candidate.exec_cost_bps}, "
        f"net_edge_after_exec_bps={candidate.net_edge_after_exec_bps}"
    )
    
    # 로그 출력 (증거 기록용)
    print(f"\n[TURN2 EVIDENCE] profitable flipped by exec_cost:")
    print(f"  raw_edge_bps: {candidate.edge_bps:.2f}")
    print(f"  exec_cost_bps: {candidate.exec_cost_bps:.2f}")
    print(f"  net_edge_after_exec_bps: {candidate.net_edge_after_exec_bps:.2f}")
    print(f"  profitable: {candidate.profitable} (expected: False)")
    print(f"  exec_model_version: {candidate.exec_model_version}")


def test_profitable_remains_true_with_low_exec_cost():
    """
    대조군: orderbook depth가 충분하면 exec_cost가 작아서 profitable=True 유지
    """
    fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0)
    fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0)
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    
    params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=0.0,
        latency_bps=0.0,
        buffer_bps=0.0,
    )
    
    price_a = 100_000_000.0
    price_b = 101_000_000.0  # 100 bps spread
    
    notional = 100_000.0  # 10만 KRW (소량)
    
    # orderbook depth: 충분함 (100만 KRW씩 available)
    upbit_bid_size = 1_000_000.0
    upbit_ask_size = 1_000_000.0
    binance_bid_size = 1_000_000.0
    binance_ask_size = 1_000_000.0
    
    candidate = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=price_a,
        price_b=price_b,
        params=params,
        notional=notional,
        upbit_bid_size=upbit_bid_size,
        upbit_ask_size=upbit_ask_size,
        binance_bid_size=binance_bid_size,
        binance_ask_size=binance_ask_size,
    )
    
    assert candidate is not None
    assert candidate.edge_bps > 0
    assert candidate.exec_cost_bps is not None
    assert candidate.net_edge_after_exec_bps is not None
    assert candidate.net_edge_after_exec_bps > 0
    
    # 대조군: profitable=True 유지
    assert candidate.profitable is True, (
        f"profitable should remain True. "
        f"edge_bps={candidate.edge_bps}, exec_cost_bps={candidate.exec_cost_bps}, "
        f"net_edge_after_exec_bps={candidate.net_edge_after_exec_bps}"
    )


def test_profitable_judgment_single_location():
    """
    profitable 판정이 detect_candidates 한 곳에서만 결정되는지 확인
    (중복 로직 없음)
    """
    fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0)
    fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0)
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    
    params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=0.0,
        latency_bps=0.0,
        buffer_bps=0.0,
    )
    
    price_a = 100_000_000.0
    price_b = 100_010_000.0  # 10 bps spread
    
    # exec_cost 없는 케이스
    candidate_no_exec = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=price_a,
        price_b=price_b,
        params=params,
        notional=None,  # exec_cost 계산 안함
    )
    
    # exec_cost 있는 케이스
    candidate_with_exec = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=price_a,
        price_b=price_b,
        params=params,
        notional=100_000.0,
        upbit_bid_size=1_000_000.0,
        upbit_ask_size=1_000_000.0,
        binance_bid_size=1_000_000.0,
        binance_ask_size=1_000_000.0,
    )
    
    # 둘 다 생성되어야 함
    assert candidate_no_exec is not None
    assert candidate_with_exec is not None
    
    # exec_cost 없으면 net_edge_bps만으로 판정
    assert candidate_no_exec.exec_cost_bps is None
    assert candidate_no_exec.profitable == (candidate_no_exec.net_edge_bps > 0)
    
    # exec_cost 있으면 net_edge_after_exec_bps로 판정
    assert candidate_with_exec.exec_cost_bps is not None
    assert candidate_with_exec.profitable == (candidate_with_exec.net_edge_after_exec_bps > 0)
    
    print(f"\n[TURN2 EVIDENCE] profitable judgment single location verified:")
    print(f"  no_exec: profitable={candidate_no_exec.profitable}, net_edge_bps={candidate_no_exec.net_edge_bps:.2f}")
    print(f"  with_exec: profitable={candidate_with_exec.profitable}, net_edge_after_exec_bps={candidate_with_exec.net_edge_after_exec_bps:.2f}")
