"""
D205-4: DecisionTrace — "왜 0 trades인가?" 숫자로 설명

목표:
- Gate별 차단 카운트 (spread, liquidity, cooldown, ratelimit)
- 기회 수 추적 (evaluated_ticks vs opportunities_total)
- 가짜 낙관 방지 (winrate 100% 감지)
- Latency 계측 (tick→decision, decision→intent, tick→intent)

SSOT: docs/v2/design/EVIDENCE_FORMAT.md
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from datetime import datetime
import json


@dataclass
class LatencyMetrics:
    """레이턴시 메트릭"""
    tick_to_decision_ms: List[float] = field(default_factory=list)  # tick 수신 → 의사결정
    decision_to_intent_ms: List[float] = field(default_factory=list)  # 의사결정 → intent 생성
    tick_to_intent_ms: List[float] = field(default_factory=list)  # tick 수신 → intent 생성
    
    def add_tick_to_decision(self, latency_ms: float):
        """Tick → Decision 레이턴시 추가"""
        self.tick_to_decision_ms.append(latency_ms)
    
    def add_decision_to_intent(self, latency_ms: float):
        """Decision → Intent 레이턴시 추가"""
        self.decision_to_intent_ms.append(latency_ms)
    
    def add_tick_to_intent(self, latency_ms: float):
        """Tick → Intent 레이턴시 추가"""
        self.tick_to_intent_ms.append(latency_ms)
    
    def percentile(self, data: List[float], p: int) -> float:
        """퍼센타일 계산"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        return round(sorted_data[min(idx, len(sorted_data) - 1)], 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "tick_to_decision_ms": {
                "p50": self.percentile(self.tick_to_decision_ms, 50),
                "p95": self.percentile(self.tick_to_decision_ms, 95),
                "p99": self.percentile(self.tick_to_decision_ms, 99),
                "max": max(self.tick_to_decision_ms) if self.tick_to_decision_ms else 0.0,
                "count": len(self.tick_to_decision_ms),
            },
            "decision_to_intent_ms": {
                "p50": self.percentile(self.decision_to_intent_ms, 50),
                "p95": self.percentile(self.decision_to_intent_ms, 95),
                "p99": self.percentile(self.decision_to_intent_ms, 99),
                "max": max(self.decision_to_intent_ms) if self.decision_to_intent_ms else 0.0,
                "count": len(self.decision_to_intent_ms),
            },
            "tick_to_intent_ms": {
                "p50": self.percentile(self.tick_to_intent_ms, 50),
                "p95": self.percentile(self.tick_to_intent_ms, 95),
                "p99": self.percentile(self.tick_to_intent_ms, 99),
                "max": max(self.tick_to_intent_ms) if self.tick_to_intent_ms else 0.0,
                "count": len(self.tick_to_intent_ms),
            },
        }


@dataclass
class DecisionTrace:
    """
    의사결정 추적 (0 trades 원인 분석용)
    
    Attributes:
        evaluated_ticks_total: 평가한 tick 수
        opportunities_total: 스프레드 조건만 만족한 기회 수
        gate_spread_insufficient_count: spread < break_even
        gate_liquidity_insufficient_count: 호가 잔량 부족
        gate_cooldown_count: 쿨다운 중
        gate_ratelimit_count: API 호출 제한
        edge_after_cost_distribution: edge_after_cost 분포 (히스토그램)
        is_optimistic_warning: winrate 100% 경고 플래그
        latency_metrics: 레이턴시 메트릭
    """
    evaluated_ticks_total: int = 0
    opportunities_total: int = 0
    gate_spread_insufficient_count: int = 0
    gate_liquidity_insufficient_count: int = 0
    gate_cooldown_count: int = 0
    gate_ratelimit_count: int = 0
    gate_units_mismatch_count: int = 0  # D205-8: 단위 불일치 경고 카운트
    edge_after_cost_distribution: Dict[str, int] = field(default_factory=lambda: {
        "negative": 0,  # edge < 0
        "zero_to_10": 0,  # 0 <= edge < 10
        "10_to_50": 0,  # 10 <= edge < 50
        "50_plus": 0,  # edge >= 50
    })
    is_optimistic_warning: bool = False
    latency_metrics: LatencyMetrics = field(default_factory=LatencyMetrics)
    
    def record_tick_evaluated(self):
        """Tick 평가 기록"""
        self.evaluated_ticks_total += 1
    
    def record_opportunity(self, edge_bps: float):
        """기회 기록 (edge 분포 포함)"""
        self.opportunities_total += 1
        
        # Edge 분포 업데이트
        if edge_bps < 0:
            self.edge_after_cost_distribution["negative"] += 1
        elif edge_bps < 10:
            self.edge_after_cost_distribution["zero_to_10"] += 1
        elif edge_bps < 50:
            self.edge_after_cost_distribution["10_to_50"] += 1
        else:
            self.edge_after_cost_distribution["50_plus"] += 1
    
    def record_gate_spread_insufficient(self):
        """Spread 부족 게이트 기록"""
        self.gate_spread_insufficient_count += 1
    
    def record_gate_liquidity_insufficient(self):
        """유동성 부족 게이트 기록"""
        self.gate_liquidity_insufficient_count += 1
    
    def record_gate_cooldown(self):
        """쿨다운 게이트 기록"""
        self.gate_cooldown_count += 1
    
    def record_gate_ratelimit(self):
        """Rate limit 게이트 기록"""
        self.gate_ratelimit_count += 1
    
    def set_optimistic_warning(self, is_warning: bool):
        """가짜 낙관 경고 설정"""
        self.is_optimistic_warning = is_warning
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "evaluated_ticks_total": self.evaluated_ticks_total,
            "opportunities_total": self.opportunities_total,
            "gate_breakdown": {
                "spread_insufficient": self.gate_spread_insufficient_count,
                "liquidity_insufficient": self.gate_liquidity_insufficient_count,
                "cooldown": self.gate_cooldown_count,
                "ratelimit": self.gate_ratelimit_count,
                "units_mismatch": self.gate_units_mismatch_count,
            },
            "edge_after_cost_distribution": self.edge_after_cost_distribution,
            "is_optimistic_warning": self.is_optimistic_warning,
            "latency_metrics": self.latency_metrics.to_dict(),
        }
