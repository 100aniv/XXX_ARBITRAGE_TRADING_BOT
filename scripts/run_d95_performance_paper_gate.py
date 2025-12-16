#!/usr/bin/env python3
"""
================================================================================
D95: 1h PAPER 성능 Gate Runner
================================================================================
목적: 1시간 PAPER 모드 성능 검증 (win_rate, TP/SL, 최소 기대값)

실행 옵션:
  - Baseline(1h) 단독 실행
  - Fail-fast: 10분 내 round_trips==0 → 중단

Evidence 생성:
  - docs/D95/evidence/d95_1h_kpi.json
  - docs/D95/evidence/d95_decision.json
  - docs/D95/evidence/d95_log_tail.txt

Exit Code:
  - 0: PASS
  - 2: FAIL

사용:
  python scripts/run_d95_performance_paper_gate.py --duration-sec 3600
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="D95: 1h PAPER 성능 Gate Runner"
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=3600,
        help="Baseline 실행 시간 (초, 기본 3600 = 1h)"
    )
    parser.add_argument(
        "--log-tail-lines",
        type=int,
        default=200,
        help="로그 tail 라인 수 (기본 200)"
    )
    parser.add_argument(
        "--evidence-dir",
        type=str,
        default="docs/D95/evidence",
        help="Evidence 출력 디렉토리 (기본: docs/D95/evidence)"
    )
    parser.add_argument(
        "--zone-profile",
        type=str,
        default="config/arbitrage/zone_profiles_d95_performance.yaml",
        help="Zone profile 파일 경로"
    )
    parser.add_argument(
        "--fail-fast-minutes",
        type=int,
        default=10,
        help="Fail-fast 시간 (분, 기본 10) - round_trips==0이면 중단"
    )
    return parser.parse_args()


def check_required_secrets() -> Tuple[bool, List[str]]:
    """필수 시크릿 검증"""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/check_required_secrets.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True, []
        else:
            return False, ["Secrets check failed"]
    except Exception as e:
        return False, [f"Secrets check error: {e}"]


def run_paper_performance(duration_sec: int, zone_profile: str) -> Tuple[int, Path, Dict[str, Any]]:
    """
    PAPER Performance 실행 (run_d77_0_topn_arbitrage_paper.py 재사용)
    
    Args:
        duration_sec: 실행 시간 (초)
        zone_profile: Zone profile 파일 경로
    
    Returns:
        (exit_code, log_path, kpi_dict)
    """
    print(f"\n{'='*80}")
    print(f"[D95] PAPER Performance Gate 실행 시작")
    print(f"  Duration: {duration_sec}s ({duration_sec/60:.1f}m)")
    print(f"  Zone Profile: {zone_profile}")
    print(f"{'='*80}\n")
    
    # 실행 시작
    start_time = time.time()
    
    cmd = [
        sys.executable,
        "scripts/run_d77_0_topn_arbitrage_paper.py",
        "--data-source", "real",
        "--topn-size", "20",
        "--run-duration-seconds", str(duration_sec),
        "--monitoring-enabled",
        "--zone-profile-file", zone_profile
    ]
    
    print(f"[D95] 실행 명령: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            timeout=duration_sec + 300  # 5분 여유
        )
        
        exit_code = result.returncode
        elapsed = time.time() - start_time
        
        print(f"\n{'='*80}")
        print(f"[D95] 실행 완료")
        print(f"  Exit Code: {exit_code}")
        print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m)")
        print(f"{'='*80}\n")
        
        # 최신 로그 디렉토리 찾기
        logs_dir = Path("logs/d77-0")
        if not logs_dir.exists():
            raise FileNotFoundError(f"로그 디렉토리 없음: {logs_dir}")
        
        # 가장 최근 d77-0-top20-* 디렉토리 찾기
        run_dirs = sorted(
            [d for d in logs_dir.glob("d77-0-top20-*") if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not run_dirs:
            raise FileNotFoundError("실행 로그 디렉토리를 찾을 수 없음")
        
        latest_run_dir = run_dirs[0]
        
        # KPI JSON 읽기
        kpi_files = list(latest_run_dir.glob("*_kpi_summary.json"))
        if not kpi_files:
            raise FileNotFoundError(f"KPI JSON 없음: {latest_run_dir}")
        
        kpi_path = kpi_files[0]
        with open(kpi_path, 'r', encoding='utf-8') as f:
            kpi = json.load(f)
        
        # 로그 파일 경로
        log_path = latest_run_dir / "runner.log"
        
        return exit_code, log_path, kpi
        
    except subprocess.TimeoutExpired:
        print(f"\n❌ [D95] 타임아웃 ({duration_sec + 300}s 초과)")
        return 2, Path(""), {}
    except Exception as e:
        print(f"\n❌ [D95] 실행 오류: {e}")
        return 2, Path(""), {}


def save_evidence(kpi: Dict[str, Any], log_path: Path, evidence_dir: str, tail_lines: int):
    """Evidence 파일 저장"""
    evidence_path = Path(evidence_dir)
    evidence_path.mkdir(parents=True, exist_ok=True)
    
    # 1) KPI JSON
    kpi_file = evidence_path / "d95_1h_kpi.json"
    with open(kpi_file, 'w', encoding='utf-8') as f:
        json.dump(kpi, f, indent=2, ensure_ascii=False)
    print(f"✅ [D95] KPI JSON 저장: {kpi_file}")
    
    # 2) Log tail
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
        
        log_tail_file = evidence_path / "d95_log_tail.txt"
        with open(log_tail_file, 'w', encoding='utf-8') as f:
            f.writelines(tail)
        print(f"✅ [D95] Log tail 저장: {log_tail_file} ({len(tail)} lines)")
    else:
        print(f"⚠️  [D95] 로그 파일 없음: {log_path}")
    
    print(f"\n{'='*80}")
    print(f"[D95] Evidence 저장 완료: {evidence_path}")
    print(f"{'='*80}\n")


def main():
    args = parse_args()
    
    print(f"\n{'='*80}")
    print(f"D95: 1h PAPER 성능 Gate Runner")
    print(f"{'='*80}")
    print(f"Duration: {args.duration_sec}s ({args.duration_sec/60:.1f}m)")
    print(f"Zone Profile: {args.zone_profile}")
    print(f"Evidence Dir: {args.evidence_dir}")
    print(f"Fail-fast: {args.fail_fast_minutes}m")
    print(f"{'='*80}\n")
    
    # 1) Secrets 검증
    print("[D95] Step 1/3: Secrets 검증")
    secrets_ok, missing = check_required_secrets()
    if not secrets_ok:
        print(f"❌ [D95] Secrets 검증 실패: {missing}")
        return 2
    print("✅ [D95] Secrets 검증 통과\n")
    
    # 2) PAPER 실행
    print("[D95] Step 2/3: PAPER Performance 실행")
    exit_code, log_path, kpi = run_paper_performance(args.duration_sec, args.zone_profile)
    
    if exit_code != 0:
        print(f"❌ [D95] PAPER 실행 실패 (exit_code={exit_code})")
        return 2
    
    if not kpi:
        print(f"❌ [D95] KPI 데이터 없음")
        return 2
    
    # 3) Evidence 저장
    print("[D95] Step 3/3: Evidence 저장")
    save_evidence(kpi, log_path, args.evidence_dir, args.log_tail_lines)
    
    # 4) 요약 출력
    print(f"\n{'='*80}")
    print(f"[D95] 실행 요약")
    print(f"{'='*80}")
    print(f"Duration: {kpi.get('duration_minutes', 0):.1f}m")
    print(f"Round Trips: {kpi.get('round_trips_completed', 0)}")
    print(f"Win Rate: {kpi.get('win_rate_pct', 0):.1f}%")
    print(f"PnL: ${kpi.get('total_pnl_usd', 0):.2f}")
    print(f"Exit Reasons:")
    for reason, count in kpi.get('exit_reasons', {}).items():
        print(f"  {reason}: {count}")
    print(f"{'='*80}\n")
    
    print("✅ [D95] PAPER Performance Gate 실행 완료")
    print(f"   다음 단계: python scripts/d95_decision_only.py --kpi {args.evidence_dir}/d95_1h_kpi.json\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
