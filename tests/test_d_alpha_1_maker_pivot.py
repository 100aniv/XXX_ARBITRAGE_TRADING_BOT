"""
D_ALPHA-1: Maker Pivot MVP 테스트

검증 항목:
- FeeModel.calculate_maker_taker_fee_bps()가 Decimal 반환 및 Maker rebate 반영
- estimate_fill_probability()가 보수적 기본값 반환
- estimate_maker_net_edge_bps()가 Decimal 정밀도로 계산
- detect_candidates()가 maker_mode에서 fill_probability 및 maker_net_edge_bps 계산
- OpportunityCandidate가 maker_mode 필드 포함
"""

import pytest
from decimal import Decimal
from arbitrage.domain.fee_model import FeeModel, FeeStructure, UPBIT_FEE, BINANCE_FEE
from arbitrage.v2.domain.fill_probability import (
    estimate_fill_probability,
    estimate_maker_net_edge_bps,
    calculate_opportunity_cost_bps,
)
from arbitrage.v2.opportunity.detector import detect_candidates
from arbitrage.v2.domain.break_even import BreakEvenParams


def test_fee_model_calculate_maker_taker_fee_decimal():
    """FeeModel.calculate_maker_taker_fee_bps()가 Decimal 반환"""
    fee_model = FeeModel(fee_a=UPBIT_FEE, fee_b=BINANCE_FEE)
    
    # Maker-Taker 하이브리드 수수료 계산
    total_fee = fee_model.calculate_maker_taker_fee_bps(
        entry_type_a="maker",  # Upbit maker: -5.0 bps (rebate)
        entry_type_b="taker",  # Binance taker: 10.0 bps
        exit_type_a="taker",   # Upbit taker: 5.0 bps
        exit_type_b="taker",   # Binance taker: 10.0 bps
    )
    
    # Decimal 타입 확인
    assert isinstance(total_fee, Decimal)
    
    # 계산 검증: -5.0 + 10.0 + 5.0 + 10.0 = 20.0 bps
    assert total_fee == Decimal("20.0")


def test_fee_model_maker_rebate_reduces_cost():
    """Maker rebate가 총 비용을 감소시킴"""
    fee_model = FeeModel(fee_a=UPBIT_FEE, fee_b=BINANCE_FEE)
    
    # Taker-only 모드
    taker_only_fee = fee_model.calculate_maker_taker_fee_bps(
        entry_type_a="taker",
        entry_type_b="taker",
        exit_type_a="taker",
        exit_type_b="taker",
    )
    
    # Maker-Taker 하이브리드 모드
    maker_hybrid_fee = fee_model.calculate_maker_taker_fee_bps(
        entry_type_a="maker",  # Upbit maker rebate
        entry_type_b="taker",
        exit_type_a="taker",
        exit_type_b="taker",
    )
    
    # Maker rebate로 인해 총 비용 감소
    assert maker_hybrid_fee < taker_only_fee
    
    # 구체적 계산 검증
    # Taker-only: 5 + 10 + 5 + 10 = 30 bps
    # Maker-hybrid: -5 + 10 + 5 + 10 = 20 bps
    assert taker_only_fee == Decimal("30.0")
    assert maker_hybrid_fee == Decimal("20.0")


def test_estimate_fill_probability_default():
    """estimate_fill_probability()가 보수적 기본값 반환"""
    fill_prob = estimate_fill_probability()
    
    # Decimal 타입 확인
    assert isinstance(fill_prob, Decimal)
    
    # 기본값 0.7 (70%) 확인
    assert fill_prob == Decimal("0.7000")
    
    # 범위 검증 (0.3 ~ 0.95)
    assert Decimal("0.3") <= fill_prob <= Decimal("0.95")


def test_estimate_fill_probability_with_queue_position():
    """Queue position이 증가하면 fill probability 감소"""
    fill_prob_1 = estimate_fill_probability(queue_position=1)
    fill_prob_5 = estimate_fill_probability(queue_position=5)
    
    # Queue 위치가 뒤쪽일수록 체결 확률 감소
    assert fill_prob_5 < fill_prob_1


def test_calculate_opportunity_cost_bps():
    """Opportunity cost 계산 검증"""
    fill_prob = Decimal("0.7")
    spread_bps = 50.0
    wait_time_seconds = 5.0
    slippage_per_second_bps = 0.2
    
    opportunity_cost = calculate_opportunity_cost_bps(
        fill_probability=fill_prob,
        spread_bps=spread_bps,
        wait_time_seconds=wait_time_seconds,
        slippage_per_second_bps=slippage_per_second_bps,
    )
    
    # Decimal 타입 확인
    assert isinstance(opportunity_cost, Decimal)
    
    # 계산 검증: (1 - 0.7) * (5 * 0.2) = 0.3 bps
    assert opportunity_cost == Decimal("0.3000")


def test_estimate_maker_net_edge_bps():
    """Maker net edge 계산 검증 (Decimal 정밀도)"""
    spread_bps = 50.0
    maker_fee_bps = Decimal("-5.0")  # Upbit maker rebate
    slippage_bps = 5.0
    latency_bps = 2.0
    fill_probability = Decimal("0.7")
    
    maker_net_edge = estimate_maker_net_edge_bps(
        spread_bps=spread_bps,
        maker_fee_bps=maker_fee_bps,
        slippage_bps=slippage_bps,
        latency_bps=latency_bps,
        fill_probability=fill_probability,
    )
    
    # Decimal 타입 확인
    assert isinstance(maker_net_edge, Decimal)
    
    # 계산 검증:
    # opportunity_cost = (1 - 0.7) * (5 * 0.2) = 0.3
    # net_edge = 50 - (-5) - 5 - 2 - 0.3 = 47.7 bps
    assert maker_net_edge == Decimal("47.7000")


def test_detect_candidates_maker_mode():
    """detect_candidates()가 maker_mode에서 fill_probability 및 maker_net_edge_bps 계산"""
    params = BreakEvenParams(
        fee_model=FeeModel(fee_a=UPBIT_FEE, fee_b=BINANCE_FEE),
        slippage_bps=5.0,
        latency_bps=2.0,
        buffer_bps=3.0,
    )
    
    # Maker mode OFF
    candidate_taker = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100000.0,
        price_b=100500.0,  # 0.5% spread
        params=params,
        maker_mode=False,
    )
    
    assert candidate_taker is not None
    assert candidate_taker.maker_mode is False
    assert candidate_taker.fill_probability is None
    assert candidate_taker.maker_net_edge_bps is None
    
    # Maker mode ON
    candidate_maker = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100000.0,
        price_b=100500.0,  # 0.5% spread
        params=params,
        maker_mode=True,
    )
    
    assert candidate_maker is not None
    assert candidate_maker.maker_mode is True
    assert candidate_maker.fill_probability is not None
    assert candidate_maker.maker_net_edge_bps is not None
    
    # Fill probability 범위 검증
    assert 0.3 <= candidate_maker.fill_probability <= 0.95
    
    # Maker net edge가 계산됨
    assert isinstance(candidate_maker.maker_net_edge_bps, float)


def test_maker_mode_positive_net_edge():
    """Maker mode에서 positive net edge 달성 검증"""
    params = BreakEvenParams(
        fee_model=FeeModel(fee_a=UPBIT_FEE, fee_b=BINANCE_FEE),
        slippage_bps=5.0,
        latency_bps=2.0,
        buffer_bps=3.0,
    )
    
    # 충분히 큰 spread (1.0%)
    candidate = detect_candidates(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100000.0,
        price_b=101000.0,  # 1.0% spread
        params=params,
        maker_mode=True,
    )
    
    assert candidate is not None
    assert candidate.maker_net_edge_bps is not None
    
    # Maker net edge > 0 (수익성 있음)
    assert candidate.maker_net_edge_bps > 0
    
    # Profitable 플래그도 True
    assert candidate.profitable is True


def test_upbit_fee_structure_has_maker_rebate():
    """UPBIT_FEE가 Maker rebate를 반영"""
    assert UPBIT_FEE.maker_fee_bps == -5.0  # -0.05% (rebate)
    assert UPBIT_FEE.taker_fee_bps == 5.0   # 0.05%


def test_binance_fee_structure_reduced_maker_fee():
    """BINANCE_FEE가 감소된 Maker fee 반영"""
    assert BINANCE_FEE.maker_fee_bps == 2.0   # 0.02% (reduced from 10.0)
    assert BINANCE_FEE.taker_fee_bps == 10.0  # 0.10%


def test_decimal_precision_throughout_pipeline():
    """전체 파이프라인에서 Decimal 정밀도 유지"""
    # 1. FeeModel
    fee_model = FeeModel(fee_a=UPBIT_FEE, fee_b=BINANCE_FEE)
    total_fee_decimal = fee_model.calculate_maker_taker_fee_bps(
        entry_type_a="maker",
        entry_type_b="taker",
        exit_type_a="taker",
        exit_type_b="taker",
    )
    assert isinstance(total_fee_decimal, Decimal)
    
    # 2. Fill Probability
    fill_prob = estimate_fill_probability()
    assert isinstance(fill_prob, Decimal)
    
    # 3. Opportunity Cost
    opportunity_cost = calculate_opportunity_cost_bps(
        fill_probability=fill_prob,
        spread_bps=50.0,
    )
    assert isinstance(opportunity_cost, Decimal)
    
    # 4. Maker Net Edge
    maker_net_edge = estimate_maker_net_edge_bps(
        spread_bps=50.0,
        maker_fee_bps=Decimal("-5.0"),
        slippage_bps=5.0,
        latency_bps=2.0,
        fill_probability=fill_prob,
    )
    assert isinstance(maker_net_edge, Decimal)
    
    # 정밀도 확인 (소수점 4자리)
    assert str(maker_net_edge).count('.') == 1
    decimal_places = len(str(maker_net_edge).split('.')[1])
    assert decimal_places <= 4
