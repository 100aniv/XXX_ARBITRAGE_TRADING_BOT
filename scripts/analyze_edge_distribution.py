#!/usr/bin/env python3
"""
D207-4 CTO Audit: edge_distribution.json 분석
- edge_bps, break_even_bps, net_edge_bps 분포 산출
- Double-count 의심 검증
- Break-even 구성요소 분석
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import statistics

def load_edge_distribution(path: str) -> List[Dict[str, Any]]:
    """edge_distribution.json 로드"""
    with open(path, 'r') as f:
        return json.load(f)

def analyze_candidates(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """모든 candidates 수집 및 분석"""
    candidates = []
    
    for tick in data:
        if 'candidates' in tick and tick['candidates']:
            candidates.extend(tick['candidates'])
    
    if not candidates:
        return {"error": "No candidates found"}
    
    # 핵심 지표 추출
    edge_bps_list = [c.get('edge_bps', 0) for c in candidates]
    break_even_bps_list = [c.get('break_even_bps', 0) for c in candidates]
    net_edge_bps_list = [c.get('net_edge_bps', 0) for c in candidates]
    spread_bps_list = [c.get('spread_bps', 0) for c in candidates]
    drift_bps_list = [c.get('deterministic_drift_bps', 0) for c in candidates]
    
    def quantiles(lst):
        """p50, p75, p90, p95, p99 계산"""
        sorted_lst = sorted(lst)
        n = len(sorted_lst)
        return {
            'p50': sorted_lst[int(n * 0.50)],
            'p75': sorted_lst[int(n * 0.75)],
            'p90': sorted_lst[int(n * 0.90)],
            'p95': sorted_lst[int(n * 0.95)],
            'p99': sorted_lst[int(n * 0.99)],
            'max': max(sorted_lst),
            'min': min(sorted_lst),
            'mean': statistics.mean(sorted_lst),
            'median': statistics.median(sorted_lst),
        }
    
    # Double-count 의심 검증
    # edge_bps = spread_bps - break_even_bps - drift_bps
    # net_edge_bps = edge_bps - drift_bps (또는 이미 포함)
    double_count_suspects = []
    for c in candidates[:100]:  # 처음 100개만 샘플
        spread = c.get('spread_bps', 0)
        be = c.get('break_even_bps', 0)
        edge = c.get('edge_bps', 0)
        drift = c.get('deterministic_drift_bps', 0)
        net_edge = c.get('net_edge_bps', 0)
        
        # edge_bps 검증: spread - break_even - drift?
        expected_edge = spread - be - drift
        if abs(edge - expected_edge) > 0.01:
            double_count_suspects.append({
                'spread': spread,
                'break_even': be,
                'drift': drift,
                'edge_actual': edge,
                'edge_expected': expected_edge,
                'net_edge': net_edge,
                'discrepancy': edge - expected_edge,
            })
    
    # Profitable 분포
    profitable_count = sum(1 for c in candidates if c.get('profitable', False))
    
    return {
        'total_candidates': len(candidates),
        'profitable_count': profitable_count,
        'profitable_pct': (profitable_count / len(candidates) * 100) if candidates else 0,
        'spread_bps': quantiles(spread_bps_list),
        'break_even_bps': quantiles(break_even_bps_list),
        'edge_bps': quantiles(edge_bps_list),
        'net_edge_bps': quantiles(net_edge_bps_list),
        'drift_bps': quantiles(drift_bps_list),
        'double_count_suspects': double_count_suspects[:10],  # 상위 10개
        'negative_net_edge_pct': (sum(1 for x in net_edge_bps_list if x < 0) / len(net_edge_bps_list) * 100),
        'positive_net_edge_pct': (sum(1 for x in net_edge_bps_list if x > 0) / len(net_edge_bps_list) * 100),
    }

def main():
    edge_dist_path = Path('logs/evidence/d207_2_longrun_60m_retry_20260126_0047/edge_distribution.json')
    
    if not edge_dist_path.exists():
        print(f"Error: {edge_dist_path} not found")
        sys.exit(1)
    
    print("[D207-4] Loading edge_distribution.json...")
    data = load_edge_distribution(str(edge_dist_path))
    
    print(f"[D207-4] Analyzing {len(data)} ticks...")
    analysis = analyze_candidates(data)
    
    # 결과 출력
    print("\n" + "="*80)
    print("D207-4 CTO AUDIT: Edge Distribution Analysis")
    print("="*80)
    
    if 'error' in analysis:
        print(f"ERROR: {analysis['error']}")
        sys.exit(1)
    
    print(f"\n[SUMMARY]")
    print(f"Total candidates: {analysis['total_candidates']:,}")
    print(f"Profitable: {analysis['profitable_count']} ({analysis['profitable_pct']:.2f}%)")
    print(f"Negative net_edge_bps: {analysis['negative_net_edge_pct']:.2f}%")
    print(f"Positive net_edge_bps: {analysis['positive_net_edge_pct']:.2f}%")
    
    print(f"\n[SPREAD_BPS Distribution]")
    for k, v in analysis['spread_bps'].items():
        print(f"  {k:>6}: {v:>10.4f}")
    
    print(f"\n[BREAK_EVEN_BPS Distribution]")
    for k, v in analysis['break_even_bps'].items():
        print(f"  {k:>6}: {v:>10.4f}")
    
    print(f"\n[EDGE_BPS Distribution]")
    for k, v in analysis['edge_bps'].items():
        print(f"  {k:>6}: {v:>10.4f}")
    
    print(f"\n[NET_EDGE_BPS Distribution]")
    for k, v in analysis['net_edge_bps'].items():
        print(f"  {k:>6}: {v:>10.4f}")
    
    print(f"\n[DRIFT_BPS Distribution]")
    for k, v in analysis['drift_bps'].items():
        print(f"  {k:>6}: {v:>10.4f}")
    
    if analysis['double_count_suspects']:
        print(f"\n[DOUBLE-COUNT SUSPECTS (Top 10)]")
        for i, suspect in enumerate(analysis['double_count_suspects'], 1):
            print(f"  {i}. Spread={suspect['spread']:.2f}, BE={suspect['break_even']:.2f}, "
                  f"Drift={suspect['drift']:.2f}")
            print(f"     Edge(actual)={suspect['edge_actual']:.2f}, "
                  f"Edge(expected)={suspect['edge_expected']:.2f}, "
                  f"Discrepancy={suspect['discrepancy']:.4f}")
    else:
        print(f"\n[DOUBLE-COUNT SUSPECTS]")
        print(f"  None detected (formula is consistent)")
    
    # Evidence 저장
    output_path = Path('logs/evidence/d207_4_cto_audit') / 'edge_analysis.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n[EVIDENCE] Saved: {output_path}")
    print("="*80)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
