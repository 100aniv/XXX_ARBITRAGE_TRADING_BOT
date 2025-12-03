#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D80-2: Real Market Edge & Spread Reality Check Analyzer
실제 시장 엣지 및 스프레드 현실성 검증 분석기

목적:
    D77-0-RM-EXT 1시간 Top20/Top50 실행 결과를 기반으로,
    "엔진/인프라 검증 GO"와 "실제 수익 구조의 현실성"을 명확히 구분하여 평가합니다.
    
핵심 기능:
    1. KPI 파일 로드 및 요약 (Top20/Top50)
    2. Win Rate 100% 구조적 원인 분석
        - 진입 조건: spread > fee + safety_margin
        - PAPER 모드 한계: 부분 체결/슬리피지/호가 변동 미반영
    3. PnL 구조 분석 (시간당/라운드트립당)
    4. 수수료/슬리피지 시나리오별 PnL 재계산 (Conservative/Moderate/Pessimistic)
    5. 스프레드 요구사항 역산 추정
    6. 한계점 식별 (Data Logging, Fill Model, Market Impact, Inventory Cost)
    7. Next Steps 제안 (D80-3, D80-4, D81-x, D82-x)

이 스크립트의 설계 원칙:
    - 기존 D77-4 analyzer 구조 재사용 (오벌리팩토링 금지)
    - 엔진/도메인 코드 수정 없음 (분석 계층만 추가)
    - 정량적 데이터 기반 평가 (추측/가정 최소화)
    - "1조 프로그램" 관점에서 현실성 평가 (과장 금지)

Usage:
    # Top20 + Top50 KPI 파일 경로 지정
    python scripts/d80_2_real_market_edge_analyzer.py \
        --top20-kpi logs/d77-0-rm-ext/run_20251204_001336/1h_top20_kpi.json \
        --top50-kpi logs/d77-0-rm-ext/run_20251204_012509/1h_top50_kpi.json \
        --output-dir logs/d80-2

Output:
    - 콘솔 요약 출력 (80자 구분선 형식)
    - JSON 결과: logs/d80-2/d80_2_edge_summary.json

Author: arbitrage-lite project
Date: 2025-12-04
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class D80EdgeAnalyzer:
    """
    Real Market Edge & Spread 현실성 분석기
    
    D77-0-RM-EXT Top20/Top50 1h 실행 결과를 기반으로,
    "엔진/인프라 검증 GO"와 "실제 수익 구조 현실성"을 구분하여 분석합니다.
    
    주요 분석 항목:
        1. Win Rate 100% 구조적 원인 (진입 조건, PAPER 모드 한계)
        2. PnL 구조 (시간당, 라운드트립당)
        3. 수수료/슬리피지 시나리오별 PnL 재계산
        4. 스프레드 요구사항 역산
        5. 한계점 및 Gap 식별
        6. Next Steps 제안
    
    Attributes:
        FEE_SCENARIOS: 수수료/슬리피지 시나리오 정의 (Conservative/Moderate/Pessimistic)
        output_dir: 분석 결과 저장 디렉토리
        analysis_result: 전체 분석 결과를 담는 딕셔너리
    """
    
    # 수수료/슬리피지 시나리오 정의
    # Conservative: 낙관적 (fee 10bps, slippage 5bps)
    # Moderate: 현실적 (fee 20bps, slippage 10bps) - 기본 가정
    # Pessimistic: 비관적 (fee 30bps, slippage 15bps)
    FEE_SCENARIOS = [
        {"name": "Conservative", "fee_bps": 10, "slippage_bps": 5},
        {"name": "Moderate", "fee_bps": 20, "slippage_bps": 10},
        {"name": "Pessimistic", "fee_bps": 30, "slippage_bps": 15},
    ]
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "data_sources": {},
            "top20_summary": {},
            "top50_summary": {},
            "edge_analysis": {},
            "limitations": [],
            "next_steps": [],
        }
    
    def analyze(self, top20_kpi_path: Path, top50_kpi_path: Path) -> Dict:
        """전체 분석 수행"""
        print("="*80)
        print("[D80-2] Real Market Edge & Spread Reality Check")
        print("="*80)
        
        # 1. KPI 로드
        print(f"\n[Step 1/5] Loading KPI files...")
        top20_kpi = self._load_kpi(top20_kpi_path, "Top20")
        top50_kpi = self._load_kpi(top50_kpi_path, "Top50")
        
        self.analysis_result["data_sources"] = {
            "top20_kpi": str(top20_kpi_path),
            "top50_kpi": str(top50_kpi_path),
        }
        
        # 2. 기본 KPI 요약
        print(f"\n[Step 2/5] Summarizing KPIs...")
        self.analysis_result["top20_summary"] = self._summarize_kpi(top20_kpi, "Top20")
        self.analysis_result["top50_summary"] = self._summarize_kpi(top50_kpi, "Top50")
        
        # 3. Edge & Spread 분석
        print(f"\n[Step 3/5] Analyzing Edge & Spread Reality...")
        self.analysis_result["edge_analysis"] = self._analyze_edge(top20_kpi, top50_kpi)
        
        # 4. 한계점 및 Gap 분석
        print(f"\n[Step 4/5] Identifying Limitations & Gaps...")
        self._identify_limitations()
        
        # 5. Next Steps 제안
        print(f"\n[Step 5/5] Proposing Next Steps...")
        self._propose_next_steps()
        
        # 결과 저장
        self._save_results()
        
        # 콘솔 출력
        self._print_summary()
        
        return self.analysis_result
    
    def _load_kpi(self, kpi_path: Path, label: str) -> Dict:
        """KPI JSON 파일 로드"""
        if not kpi_path.exists():
            print(f"[ERROR] {label} KPI file not found: {kpi_path}")
            sys.exit(1)
        
        try:
            with open(kpi_path, 'r', encoding='utf-8') as f:
                kpi = json.load(f)
            print(f"  ✅ {label} KPI loaded: {len(kpi)} fields")
            return kpi
        except Exception as e:
            print(f"[ERROR] Failed to load {label} KPI: {e}")
            sys.exit(1)
    
    def _summarize_kpi(self, kpi: Dict, label: str) -> Dict:
        """KPI 기본 요약"""
        summary = {
            "session_id": kpi.get("session_id", "N/A"),
            "universe": kpi.get("universe_mode", "N/A"),
            "duration_minutes": kpi.get("actual_duration_minutes", kpi.get("duration_minutes", 0)),
            "round_trips": kpi.get("round_trips_completed", 0),
            "total_pnl_usd": kpi.get("total_pnl_usd", 0),
            "win_rate_pct": kpi.get("win_rate_pct", 0),
            "loop_latency_p99_ms": kpi.get("loop_latency_p99_ms", 0),
            "memory_mb": kpi.get("memory_usage_mb", 0),
            "cpu_pct": kpi.get("cpu_usage_pct", 0),
        }
        
        # 시간당 메트릭 계산
        duration_hours = summary["duration_minutes"] / 60.0
        if duration_hours > 0:
            summary["round_trips_per_hour"] = summary["round_trips"] / duration_hours
            summary["pnl_per_hour_usd"] = summary["total_pnl_usd"] / duration_hours
            summary["pnl_per_round_trip_usd"] = summary["total_pnl_usd"] / summary["round_trips"] if summary["round_trips"] > 0 else 0
        else:
            summary["round_trips_per_hour"] = 0
            summary["pnl_per_hour_usd"] = 0
            summary["pnl_per_round_trip_usd"] = 0
        
        print(f"\n  [{label} Summary]")
        print(f"    Round Trips: {summary['round_trips']} ({summary['round_trips_per_hour']:.1f}/h)")
        print(f"    Total PnL: ${summary['total_pnl_usd']:,.2f} (${summary['pnl_per_hour_usd']:,.2f}/h)")
        print(f"    PnL/RT: ${summary['pnl_per_round_trip_usd']:.2f}")
        print(f"    Win Rate: {summary['win_rate_pct']:.1f}%")
        
        return summary
    
    def _analyze_edge(self, top20_kpi: Dict, top50_kpi: Dict) -> Dict:
        """Edge & Spread 현실성 분석"""
        edge_analysis = {
            "win_rate_interpretation": self._interpret_win_rate(top20_kpi, top50_kpi),
            "pnl_structure_analysis": self._analyze_pnl_structure(top20_kpi, top50_kpi),
            "fee_slippage_scenarios": self._calculate_fee_scenarios(top20_kpi, top50_kpi),
            "spread_requirements": self._estimate_spread_requirements(top20_kpi, top50_kpi),
        }
        
        return edge_analysis
    
    def _interpret_win_rate(self, top20_kpi: Dict, top50_kpi: Dict) -> Dict:
        """
        100% 승률 해석 및 구조적 원인 분석
        
        핵심 질문: 왜 100% 승률이 나왔는가?
        
        답변:
            1. 진입 조건이 "보장된 승리" 구조: spread > fee + safety_margin
            2. PAPER 모드 한계:
                - 부분 체결 미모델링 (주문 전량 즉시 체결 가정)
                - 슬리피지 미반영 (제출 가격 그대로 체결 가정)
                - 호가 변동 및 시장 충격 미반영 (호가창 정적 가정)
            3. 현실적 승률 범위: 30~80% (유동성 및 시장 환경에 따라)
        
        Returns:
            dict: {
                "top20_win_rate": float,
                "top50_win_rate": float,
                "is_realistic": bool,
                "explanation": str
            }
        """
        top20_wr = top20_kpi.get("win_rate_pct", 0)
        top50_wr = top50_kpi.get("win_rate_pct", 0)
        
        interpretation = {
            "top20_win_rate": top20_wr,
            "top50_win_rate": top50_wr,
            "is_realistic": top20_wr < 100 and top50_wr < 100,
            "explanation": "",
        }
        
        if top20_wr == 100.0 and top50_wr == 100.0:
            interpretation["explanation"] = (
                "100% 승률은 엔진이 'spread > fee + safety_margin' 조건에서만 진입하도록 "
                "설계되어 있기 때문에 발생한 구조적 결과입니다. 이는 PAPER 모드에서 "
                "부분 체결, 슬리피지, 호가 변동 등을 모델링하지 않았기 때문이며, "
                "실제 시장에서는 30~80% 범위가 현실적입니다."
            )
        else:
            interpretation["explanation"] = f"승률이 {top20_wr:.1f}%/{top50_wr:.1f}%로 현실적 범위에 있습니다."
        
        print(f"\n  [Win Rate Interpretation]")
        print(f"    Top20: {top20_wr:.1f}%, Top50: {top50_wr:.1f}%")
        print(f"    Realistic: {interpretation['is_realistic']}")
        print(f"    {interpretation['explanation'][:100]}...")
        
        return interpretation
    
    def _analyze_pnl_structure(self, top20_kpi: Dict, top50_kpi: Dict) -> Dict:
        """
        PnL 구조 분석 - 시간당 $200k PnL의 의미
        
        핵심 질문: 시간당 $200k PnL은 "실제 수익"인가?
        
        답변: 아니요. 이는 "엔진 벤치마크"일 뿐입니다.
        
        이유:
            1. 수수료 미반영 (Upbit 0.05~0.1%, Binance 0.04~0.075%)
            2. 슬리피지 미반영 (평균 0.05~0.15%)
            3. 호가 잔량 제약 미반영 (대량 거래 시 가격 악화)
            4. 인벤토리 리밸런싱 비용 미반영
        
        현실적 PnL:
            - Conservative 시나리오: 원래 PnL의 97.6% (2.4% 감소)
            - Moderate 시나리오: 원래 PnL의 95.2% (4.8% 감소)
            - Pessimistic 시나리오: 원래 PnL의 92.8% (7.2% 감소)
        
        Returns:
            dict: {
                "top20_pnl_per_rt": float,
                "top50_pnl_per_rt": float,
                "hourly_pnl_top20": float,
                "hourly_pnl_top50": float,
                "interpretation": str
            }
        """
        top20_pnl = top20_kpi.get("total_pnl_usd", 0)
        top50_pnl = top50_kpi.get("total_pnl_usd", 0)
        top20_rt = top20_kpi.get("round_trips_completed", 1)
        top50_rt = top50_kpi.get("round_trips_completed", 1)
        
        pnl_structure = {
            "top20_pnl_per_rt": top20_pnl / top20_rt if top20_rt > 0 else 0,
            "top50_pnl_per_rt": top50_pnl / top50_rt if top50_rt > 0 else 0,
            "hourly_pnl_top20": top20_pnl / (top20_kpi.get("actual_duration_minutes", 60) / 60.0),
            "hourly_pnl_top50": top50_pnl / (top50_kpi.get("actual_duration_minutes", 60) / 60.0),
            "interpretation": "",
        }
        
        pnl_structure["interpretation"] = (
            f"시간당 ${pnl_structure['hourly_pnl_top20']:,.0f} (Top20) / "
            f"${pnl_structure['hourly_pnl_top50']:,.0f} (Top50) 수준은 "
            "엔진 검증용 벤치마크로는 의미가 있으나, 실제 시장 수익 현실성과는 거리가 있습니다. "
            "수수료, 슬리피지, 호가 잔량 제약 등을 반영하면 크게 감소할 것으로 예상됩니다."
        )
        
        print(f"\n  [PnL Structure]")
        print(f"    PnL/RT: ${pnl_structure['top20_pnl_per_rt']:.2f} (Top20), ${pnl_structure['top50_pnl_per_rt']:.2f} (Top50)")
        print(f"    Hourly: ${pnl_structure['hourly_pnl_top20']:,.0f} (Top20), ${pnl_structure['hourly_pnl_top50']:,.0f} (Top50)")
        
        return pnl_structure
    
    def _calculate_fee_scenarios(self, top20_kpi: Dict, top50_kpi: Dict) -> List[Dict]:
        """수수료/슬리피지 시나리오별 PnL 재계산"""
        scenarios = []
        
        for scenario_def in self.FEE_SCENARIOS:
            # Top20 시나리오
            top20_scenario = self._apply_scenario(
                top20_kpi,
                scenario_def["fee_bps"],
                scenario_def["slippage_bps"],
                "Top20"
            )
            top20_scenario["name"] = scenario_def["name"]
            
            # Top50 시나리오
            top50_scenario = self._apply_scenario(
                top50_kpi,
                scenario_def["fee_bps"],
                scenario_def["slippage_bps"],
                "Top50"
            )
            top50_scenario["name"] = scenario_def["name"]
            
            scenarios.append({
                "scenario": scenario_def["name"],
                "fee_bps": scenario_def["fee_bps"],
                "slippage_bps": scenario_def["slippage_bps"],
                "top20": top20_scenario,
                "top50": top50_scenario,
            })
        
        print(f"\n  [Fee/Slippage Scenarios]")
        for s in scenarios:
            print(f"    {s['scenario']} (fee={s['fee_bps']}bps, slip={s['slippage_bps']}bps):")
            print(f"      Top20: ${s['top20']['adjusted_pnl_usd']:,.0f} ({s['top20']['pnl_reduction_pct']:.1f}% reduction)")
            print(f"      Top50: ${s['top50']['adjusted_pnl_usd']:,.0f} ({s['top50']['pnl_reduction_pct']:.1f}% reduction)")
        
        return scenarios
    
    def _apply_scenario(self, kpi: Dict, fee_bps: int, slippage_bps: int, label: str) -> Dict:
        """단일 시나리오 적용"""
        original_pnl = kpi.get("total_pnl_usd", 0)
        round_trips = kpi.get("round_trips_completed", 1)
        
        # 간단한 모델: 각 라운드트립마다 (fee + slippage) * 2 (양방향) 비용 발생
        # 실제로는 거래 금액에 비례하지만, 여기서는 평균 거래 금액을 가정
        # 가정: 평균 거래 금액 = $1000 (실제 로그 데이터가 없으므로 보수적 추정)
        avg_trade_size_usd = 1000
        cost_per_rt = avg_trade_size_usd * (fee_bps + slippage_bps) / 10000 * 2
        
        total_cost = cost_per_rt * round_trips
        adjusted_pnl = original_pnl - total_cost
        pnl_reduction_pct = (total_cost / original_pnl * 100) if original_pnl > 0 else 0
        
        return {
            "original_pnl_usd": original_pnl,
            "total_cost_usd": total_cost,
            "adjusted_pnl_usd": adjusted_pnl,
            "pnl_reduction_pct": pnl_reduction_pct,
        }
    
    def _estimate_spread_requirements(self, top20_kpi: Dict, top50_kpi: Dict) -> Dict:
        """최소 스프레드 요구사항 추정"""
        # 현재 로그에 스프레드 정보가 없으므로, 역산 추정
        # PnL / Round Trips = 평균 스프레드 수익으로 가정
        
        top20_pnl_per_rt = top20_kpi.get("total_pnl_usd", 0) / max(top20_kpi.get("round_trips_completed", 1), 1)
        top50_pnl_per_rt = top50_kpi.get("total_pnl_usd", 0) / max(top50_kpi.get("round_trips_completed", 1), 1)
        
        # 가정: 평균 거래 금액 $1000
        avg_trade_size = 1000
        
        top20_spread_bps = (top20_pnl_per_rt / avg_trade_size) * 10000 if avg_trade_size > 0 else 0
        top50_spread_bps = (top50_pnl_per_rt / avg_trade_size) * 10000 if avg_trade_size > 0 else 0
        
        requirements = {
            "top20_implied_spread_bps": top20_spread_bps,
            "top50_implied_spread_bps": top50_spread_bps,
            "min_spread_for_profitability_bps": 30,  # fee(20) + slippage(10) 기준
            "note": "스프레드 데이터가 로그에 없어 PnL 역산으로 추정. 실제 스프레드 로깅 필요.",
        }
        
        print(f"\n  [Spread Requirements (Estimated)]")
        print(f"    Top20 Implied Spread: {top20_spread_bps:.1f} bps")
        print(f"    Top50 Implied Spread: {top50_spread_bps:.1f} bps")
        print(f"    Min Profitable Spread: {requirements['min_spread_for_profitability_bps']} bps")
        print(f"    Note: {requirements['note']}")
        
        return requirements
    
    def _identify_limitations(self):
        """한계점 및 Gap 식별"""
        limitations = [
            {
                "category": "Data Logging",
                "issue": "Trade-level spread/liquidity 로그 부재",
                "impact": "각 거래의 실제 스프레드, 호가 잔량, 체결 가격을 분석할 수 없음",
                "next_step": "D80-3: Trade-level Spread & Liquidity Logging 강화",
            },
            {
                "category": "Fill Model",
                "issue": "부분 체결 및 슬리피지 미모델링",
                "impact": "100% 승률 및 과대평가된 PnL 발생",
                "next_step": "D80-4: Realistic Fill/Slippage Model 도입",
            },
            {
                "category": "Market Impact",
                "issue": "호가 잔량 제약 및 시장 충격 미반영",
                "impact": "대량 거래 시 실제 체결 가능성 및 가격 영향 미평가",
                "next_step": "D81-x: Market Impact & Liquidity Analysis",
            },
            {
                "category": "Inventory Cost",
                "issue": "인벤토리 리밸런싱 비용 미포함",
                "impact": "Cross-exchange 포지션 조정 비용이 PnL에 반영되지 않음",
                "next_step": "D81-x: Inventory/Rebalancing Cost Modeling",
            },
        ]
        
        self.analysis_result["limitations"] = limitations
        
        print(f"\n  [Limitations & Gaps]")
        for lim in limitations:
            print(f"    - {lim['category']}: {lim['issue']}")
            print(f"      Impact: {lim['impact']}")
            print(f"      Next: {lim['next_step']}")
    
    def _propose_next_steps(self):
        """Next Steps 제안"""
        next_steps = [
            "D80-3: Trade-level Spread & Liquidity Logging 강화 - 각 거래의 스프레드, 호가, 체결 가격 로깅",
            "D80-4: Realistic Fill/Slippage Model 도입 - 부분 체결, 슬리피지, 호가 변동 모델링",
            "D81-x: Market Impact & Liquidity Analysis - 호가 잔량 제약 및 시장 충격 분석",
            "D81-x: Inventory/Rebalancing Cost Modeling - Cross-exchange 포지션 조정 비용 반영",
            "D82-x: Long-term (12h+) Real Market Validation - 장기 실행으로 Edge 지속성 검증",
        ]
        
        self.analysis_result["next_steps"] = next_steps
        
        print(f"\n  [Proposed Next Steps]")
        for i, step in enumerate(next_steps, 1):
            print(f"    {i}. {step}")
    
    def _save_results(self):
        """분석 결과 저장"""
        output_path = self.output_dir / "d80_2_edge_summary.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n[✅] Analysis results saved: {output_path}")
    
    def _print_summary(self):
        """최종 요약 출력"""
        print("\n" + "="*80)
        print("[D80-2] Analysis Summary")
        print("="*80)
        
        print(f"\n✅ Infrastructure/Engine Level: GO (D77-0-RM-EXT COMPLETE)")
        print(f"   - Top20: {self.analysis_result['top20_summary']['round_trips']} RTs, "
              f"${self.analysis_result['top20_summary']['total_pnl_usd']:,.0f} PnL")
        print(f"   - Top50: {self.analysis_result['top50_summary']['round_trips']} RTs, "
              f"${self.analysis_result['top50_summary']['total_pnl_usd']:,.0f} PnL")
        
        print(f"\n⚠️  Real Market Edge Reality: NEEDS FURTHER VALIDATION")
        print(f"   - 100% Win Rate: Structural (PAPER mode limitation)")
        print(f"   - $200k/h PnL: Benchmark only (not realistic profit expectation)")
        print(f"   - Missing: Trade-level spread, liquidity, fill model")
        
        print(f"\n📋 Limitations Identified: {len(self.analysis_result['limitations'])}")
        for lim in self.analysis_result['limitations']:
            print(f"   - {lim['category']}: {lim['issue']}")
        
        print(f"\n🚀 Next Steps Proposed: {len(self.analysis_result['next_steps'])}")
        for i, step in enumerate(self.analysis_result['next_steps'][:3], 1):
            print(f"   {i}. {step[:70]}...")
        
        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description="D80-2: Real Market Edge & Spread Reality Check Analyzer"
    )
    parser.add_argument(
        "--top20-kpi",
        required=True,
        help="Top20 1h KPI JSON file path"
    )
    parser.add_argument(
        "--top50-kpi",
        required=True,
        help="Top50 1h KPI JSON file path"
    )
    parser.add_argument(
        "--output-dir",
        default="logs/d80-2",
        help="Output directory for analysis results (default: logs/d80-2)"
    )
    
    args = parser.parse_args()
    
    top20_kpi_path = Path(args.top20_kpi)
    top50_kpi_path = Path(args.top50_kpi)
    output_dir = Path(args.output_dir)
    
    analyzer = D80EdgeAnalyzer(output_dir)
    result = analyzer.analyze(top20_kpi_path, top50_kpi_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
