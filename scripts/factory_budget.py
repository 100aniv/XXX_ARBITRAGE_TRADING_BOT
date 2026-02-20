#!/usr/bin/env python3
"""Factory Budget Auditor - Best Value Routing & Cost Estimation.

TASK 10: AC별 예상 비용 산출 + 가성비 모델 추천.

Usage:
    python scripts/factory_budget.py
    just factory_budget
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.factory.controller import (
    parse_ledger_rows,
    classify_intent,
    select_agent,
    extract_paths_from_notes,
    _is_v2_alpha_ticket,
    LEDGER_PATH,
)

MODEL_COST_PER_1K_TOKENS = {
    "openai": {
        "low": {"input": 0.00015, "output": 0.0006},      # gpt-4.1-mini
        "mid": {"input": 0.002, "output": 0.008},          # gpt-4.1
        "high": {"input": 0.01, "output": 0.04},           # o3
    },
    "anthropic": {
        "low": {"input": 0.003, "output": 0.015},          # claude-sonnet
        "mid": {"input": 0.003, "output": 0.015},          # claude-sonnet
        "high": {"input": 0.015, "output": 0.075},         # claude-opus
    },
}

AVG_TOKENS_PER_AC = {
    "low": {"input": 2000, "output": 1000},
    "mid": {"input": 5000, "output": 3000},
    "high": {"input": 10000, "output": 6000},
}


def estimate_cost(provider: str, tier: str, complexity: str = "mid") -> float:
    """AC 1개 예상 비용 산출 (USD)."""
    cost_table = MODEL_COST_PER_1K_TOKENS.get(provider, MODEL_COST_PER_1K_TOKENS["openai"])
    tier_cost = cost_table.get(tier, cost_table["mid"])
    tokens = AVG_TOKENS_PER_AC.get(complexity, AVG_TOKENS_PER_AC["mid"])
    
    input_cost = (tokens["input"] / 1000) * tier_cost["input"]
    output_cost = (tokens["output"] / 1000) * tier_cost["output"]
    return round(input_cost + output_cost, 4)


def get_best_value_recommendation(intent: str, file_count: int) -> Dict[str, str]:
    """가성비 모델 추천."""
    if file_count >= 5:
        return {
            "agent": "claude_code",
            "provider": "anthropic",
            "tier": "mid",
            "reason": f"파일 {file_count}개 (>=5) → claude_code 권장, mid tier로 비용 절감 가능",
        }
    
    if intent == "design":
        return {
            "agent": "claude_code",
            "provider": "anthropic",
            "tier": "mid",
            "reason": "설계/아키텍처 작업 → claude_code mid tier 권장",
        }
    
    return {
        "agent": "aider",
        "provider": "openai",
        "tier": "low",
        "reason": f"단순 구현 (파일 {file_count}개) → aider + gpt-4.1-mini로 95% 비용 절감 가능",
    }


def analyze_ticket(row: Dict[str, str]) -> Dict[str, any]:
    """티켓 분석 및 비용 추정."""
    title = row.get("title", "")
    notes = row.get("notes", "")
    ac_id = row.get("ac_id", "")
    
    paths = extract_paths_from_notes(title, notes)
    file_count = len(paths) if paths else 1
    intent = classify_intent(title, notes)
    agent = select_agent(intent, file_count)
    
    provider = "openai" if agent == "aider" else "anthropic"
    
    recommendation = get_best_value_recommendation(intent, file_count)
    
    cost_high = estimate_cost(provider, "high")
    cost_mid = estimate_cost(provider, "mid")
    cost_low = estimate_cost(provider, "low")
    cost_recommended = estimate_cost(recommendation["provider"], recommendation["tier"])
    
    return {
        "ac_id": ac_id,
        "title": title[:50] + "..." if len(title) > 50 else title,
        "intent": intent,
        "file_count": file_count,
        "agent": agent,
        "provider": provider,
        "cost_high": cost_high,
        "cost_mid": cost_mid,
        "cost_low": cost_low,
        "cost_recommended": cost_recommended,
        "recommendation": recommendation,
        "savings_pct": round((1 - cost_recommended / cost_high) * 100, 1) if cost_high > 0 else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Budget Auditor")
    parser.add_argument("--ledger", default=str(LEDGER_PATH), help="AC ledger path")
    parser.add_argument("--limit", type=int, default=20, help="Max tickets to analyze")
    parser.add_argument("--max-budget", type=float, default=5.0, help="Max budget per session (USD)")
    args = parser.parse_args()
    
    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"[ERROR] Ledger not found: {ledger_path}")
        return 1
    
    rows = parse_ledger_rows(ledger_path)
    open_tickets = [r for r in rows if r.get("status") == "OPEN" and _is_v2_alpha_ticket(r)]
    
    print("=" * 80)
    print("  FACTORY BUDGET AUDITOR - Best Value Routing")
    print("=" * 80)
    print(f"\n  [OPEN TICKETS] {len(open_tickets)} / [LIMIT] {args.limit}")
    print(f"  [MAX BUDGET]   ${args.max_budget:.2f} per session\n")
    
    total_high = 0.0
    total_recommended = 0.0
    aider_count = 0
    claude_count = 0
    
    print("-" * 80)
    print(f"{'AC_ID':<25} {'INTENT':<15} {'FILES':<6} {'AGENT':<12} {'HIGH$':<8} {'REC$':<8} {'SAVE%':<6}")
    print("-" * 80)
    
    for row in open_tickets[:args.limit]:
        analysis = analyze_ticket(row)
        total_high += analysis["cost_high"]
        total_recommended += analysis["cost_recommended"]
        
        if analysis["agent"] == "aider":
            aider_count += 1
        else:
            claude_count += 1
        
        print(
            f"{analysis['ac_id']:<25} "
            f"{analysis['intent']:<15} "
            f"{analysis['file_count']:<6} "
            f"{analysis['agent']:<12} "
            f"${analysis['cost_high']:<7.4f} "
            f"${analysis['cost_recommended']:<7.4f} "
            f"{analysis['savings_pct']:<5.1f}%"
        )
    
    print("-" * 80)
    print(f"\n  [SUMMARY]")
    print(f"    - Aider (OpenAI) 선택: {aider_count}개")
    print(f"    - Claude Code 선택:   {claude_count}개")
    print(f"    - High Tier 총 비용:  ${total_high:.4f}")
    print(f"    - 추천 Tier 총 비용:  ${total_recommended:.4f}")
    print(f"    - 예상 절감액:        ${total_high - total_recommended:.4f} ({(1 - total_recommended/total_high)*100:.1f}%)")
    
    if total_recommended > args.max_budget:
        print(f"\n  [WARNING] 추천 비용 ${total_recommended:.2f} > 예산 ${args.max_budget:.2f}")
        print(f"            {int(args.max_budget / (total_recommended / len(open_tickets[:args.limit])))}개 AC만 실행 권장")
    
    print("\n" + "=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
