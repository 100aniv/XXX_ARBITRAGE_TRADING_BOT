"""TURN 증거 분석 스크립트: KPI 파싱 및 부분체결 영향 분석"""
import json
import sys
from pathlib import Path

def analyze_kpi(evidence_dir: str) -> dict:
    """KPI.json 파싱"""
    kpi_path = Path(evidence_dir) / "kpi.json"
    with open(kpi_path, encoding='utf-8') as f:
        return json.load(f)

def analyze_trades(evidence_dir: str) -> dict:
    """trades_ledger.jsonl 파싱 및 부분체결 영향 분석"""
    ledger_path = Path(evidence_dir) / "trades_ledger.jsonl"
    trades = []
    with open(ledger_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                trades.append(json.loads(line))
    
    partial_trades = [
        t for t in trades 
        if t.get('entry_partial_fill_ratio', 1.0) < 1.0 
        or t.get('exit_partial_fill_ratio', 1.0) < 1.0
    ]
    
    total_penalty = sum(t.get('partial_fill_penalty', 0) for t in partial_trades)
    
    return {
        'total_trades': len(trades),
        'partial_trades': len(partial_trades),
        'partial_trade_ids': [t['trade_id'] for t in partial_trades],
        'total_partial_penalty': total_penalty,
        'trades': trades,
        'partial_trades_detail': partial_trades
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_turn_evidence.py <evidence_dir1> [evidence_dir2] ...")
        sys.exit(1)
    
    results = {}
    for evidence_dir in sys.argv[1:]:
        name = Path(evidence_dir).name
        kpi = analyze_kpi(evidence_dir)
        trades_info = analyze_trades(evidence_dir)
        
        results[name] = {
            'kpi': {
                'rest_in_tick_count': kpi.get('rest_in_tick_count', -1),
                'error_count': kpi.get('error_count', -1),
                'tick_elapsed_ms_p95': kpi.get('tick_elapsed_ms_p95', -1),
                'tick_sleep_ms_p95': kpi.get('tick_sleep_ms_p95', -1),
                'stop_reason': kpi.get('stop_reason', 'UNKNOWN'),
                'net_pnl_full': kpi.get('net_pnl_full', 0),
                'gross_pnl': kpi.get('gross_pnl', 0),
                'fees_total': kpi.get('fees_total', 0),
                'slippage_cost': kpi.get('slippage_cost', 0),
                'latency_cost': kpi.get('latency_cost', 0),
                'partial_fill_penalty': kpi.get('partial_fill_penalty', 0),
                'exec_cost_total': kpi.get('exec_cost_total', 0),
            },
            'trades': {
                'total': trades_info['total_trades'],
                'partial': trades_info['partial_trades'],
                'total_partial_penalty': trades_info['total_partial_penalty'],
            }
        }
    
    # 출력
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
