"""
D207-2: KPI 정합성 (reject_total = sum(reject_reasons))
"""

from arbitrage.v2.core.metrics import PaperMetrics


def test_reject_total_matches_reject_reasons_sum():
    metrics = PaperMetrics()
    metrics.bump_reject("candidate_none")
    metrics.bump_reject("execution_reject")
    metrics.bump_reject("unknown_reason")

    kpi = metrics.to_dict()

    reject_total = kpi.get("reject_total")
    reject_reasons = kpi.get("reject_reasons") or {}

    assert reject_total == sum(reject_reasons.values())
