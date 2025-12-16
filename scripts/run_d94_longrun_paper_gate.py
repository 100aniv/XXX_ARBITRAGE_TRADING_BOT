#!/usr/bin/env python3
"""
================================================================================
D94: 1h+ Long-run PAPER 안정성 Gate Runner
================================================================================
목적: 1시간+ PAPER 모드 안정성 검증 및 재현 가능한 증거 생성

실행 옵션:
  - Smoke(20m) + Baseline(1h) 계단식
  - Baseline(1h) 단독 실행

Evidence 생성:
  - docs/D94/evidence/d94_1h_kpi.json
  - docs/D94/evidence/d94_decision.json
  - docs/D94/evidence/d94_log_tail.txt
  - docs/D94/evidence/d94_smoke_kpi.json (--smoke 옵션 시)

Exit Code:
  - 0: PASS / PASS_WITH_WARNINGS
  - 2: FAIL

사용:
  python scripts/run_d94_longrun_paper_gate.py --duration-sec 3600
  python scripts/run_d94_longrun_paper_gate.py --smoke --duration-sec 3600
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
        description="D94: 1h+ Long-run PAPER 안정성 Gate Runner"
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=3600,
        help="Baseline 실행 시간 (초, 기본 3600 = 1h)"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke(20m) 먼저 실행 후 PASS 시 Baseline 진행"
    )
    parser.add_argument(
        "--log-tail-lines",
        type=int,
        default=200,
        help="로그 tail 라인 수 (기본 200)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="docs/D94/evidence",
        help="Evidence 출력 디렉토리 (기본: docs/D94/evidence)"
    )
    return parser.parse_args()


def check_required_secrets() -> Tuple[bool, List[str]]:
    """
    필수 시크릿 검증 (D92 v3.2 재사용)
    
    Returns:
        (all_present, missing_vars)
    """
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


def run_paper_longrun(duration_sec: int, run_type: str) -> Tuple[int, Path, Dict[str, Any]]:
    """
    PAPER Long-run 실행 (run_d77_0_topn_arbitrage_paper.py 재사용)
    
    Args:
        duration_sec: 실행 시간 (초)
        run_type: "smoke" 또는 "baseline"
    
    Returns:
        (exit_code, log_dir, metadata)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"d94_{run_type}_{timestamp}"
    log_dir = Path("logs/d94") / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"D94 {run_type.upper()} 실행 중... (duration={duration_sec}s)")
    print(f"{'='*80}\n")
    
    start_time = datetime.now(timezone.utc)
    
    cmd = [
        sys.executable,
        "scripts/run_d77_0_topn_arbitrage_paper.py",
        "--universe",
        "top20",
        "--run-duration-seconds",
        str(duration_sec),
        "--data-source",
        "real",
        "--monitoring-enabled",
        "--skip-env-check",
        "--validation-profile",
        "none"
    ]
    
    gate_log = log_dir / "gate.log"
    
    try:
        with open(gate_log, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=duration_sec + 300  # 5분 여유
            )
        
        end_time = datetime.now(timezone.utc)
        actual_duration = (end_time - start_time).total_seconds()
        
        exit_code = result.returncode
        
        metadata = {
            "run_id": run_id,
            "run_type": run_type,
            "command": " ".join(cmd),
            "start_ts": start_time.isoformat(),
            "end_ts": end_time.isoformat(),
            "target_duration_sec": duration_sec,
            "actual_duration_sec": actual_duration,
            "exit_code": exit_code
        }
        
        print(f"\n{run_type.upper()} 완료: exit_code={exit_code}, duration={actual_duration:.1f}s")
        
        return exit_code, log_dir, metadata
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] {run_type.upper()} 실행 타임아웃 (limit={duration_sec + 300}s)")
        (log_dir / "stderr.log").write_text(
            f"[ERROR] Timeout after {duration_sec + 300}s",
            encoding="utf-8"
        )
        return 124, log_dir, {
            "run_id": run_id,
            "run_type": run_type,
            "error": "timeout"
        }
    except Exception as e:
        print(f"[ERROR] {run_type.upper()} 실행 중 예외: {e}")
        (log_dir / "stderr.log").write_text(f"[ERROR] {e}", encoding="utf-8")
        return 2, log_dir, {
            "run_id": run_id,
            "run_type": run_type,
            "error": str(e)
        }


def extract_kpi_from_log(log_dir: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gate 로그에서 KPI 추출 (기존 gate_10m_kpi.json 포맷 재사용)
    
    Args:
        log_dir: 로그 디렉토리
        metadata: 실행 메타데이터
    
    Returns:
        KPI 딕셔너리
    """
    gate_log = log_dir / "gate.log"
    
    if not gate_log.exists():
        return {
            **metadata,
            "error": "gate.log not found"
        }
    
    log_content = gate_log.read_text(encoding="utf-8", errors="ignore")
    
    # KPI 추출 (간단한 패턴 매칭, 실제로는 더 정교한 로직 필요)
    kpi = {
        **metadata,
        "round_trips_count": len(re.findall(r"Round trip completed", log_content)),
        "entry_trades": len(re.findall(r"ENTRY|BUY", log_content)),
        "exit_trades": len(re.findall(r"EXIT|SELL", log_content)),
        "pnl_usd": 0.0,  # 로그 파싱으로 추출 (여기서는 임시)
    }
    
    return kpi


def count_errors_in_log(log_file: Path) -> Dict[str, int]:
    """
    로그 파일에서 에러/경고 카운트
    
    Args:
        log_file: 로그 파일 경로
    
    Returns:
        에러 카운트 딕셔너리
    """
    if not log_file.exists():
        return {"ERROR": 0, "Traceback": 0, "WARNING": 0}
    
    content = log_file.read_text(encoding="utf-8", errors="ignore")
    
    return {
        "ERROR": len(re.findall(r"\bERROR\b", content, re.IGNORECASE)),
        "Traceback": len(re.findall(r"Traceback", content)),
        "WARNING": len(re.findall(r"\bWARNING\b", content, re.IGNORECASE))
    }


def extract_log_tail(log_file: Path, tail_lines: int) -> str:
    """
    로그 파일의 마지막 N줄 추출
    
    Args:
        log_file: 로그 파일 경로
        tail_lines: 추출할 라인 수
    
    Returns:
        로그 tail 문자열
    """
    if not log_file.exists():
        return "[LOG FILE NOT FOUND]"
    
    lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
    
    return "\n".join(tail)


def judge_decision(kpi: Dict[str, Any], error_counts: Dict[str, int], target_duration: int) -> Dict[str, Any]:
    """
    KPI + 에러 카운트 기반 판정 (D94 안정성 Gate SSOT)
    
    D94 판정 규칙 (안정성만 검증, 성능은 D95로 이관):
    - Critical (FAIL 즉시): exit_code=0, duration 충족, ERROR=0, kill_switch=false
    - Semi-Critical (INFO 기록): round_trips >= 1 (최소 통과선, 0이어도 PASS)
    - Variable (INFO만): win_rate, PnL, exit_reason 분포
    
    Args:
        kpi: KPI 딕셔너리
        error_counts: 에러 카운트
        target_duration: 목표 실행 시간 (초)
    
    Returns:
        판정 결과 딕셔너리
    """
    decision = "PASS"
    reasons = []
    critical_checks = {}
    semi_checks = {}
    info_notes = []
    
    # Critical: exit_code
    if kpi.get("exit_code", 0) != 0:
        decision = "FAIL"
        reasons.append(f"❌ exit_code={kpi.get('exit_code')} (expected 0)")
        critical_checks["exit_code"] = False
    else:
        reasons.append("✅ exit_code=0 (Critical: PASS)")
        critical_checks["exit_code"] = True
    
    # Critical: duration
    actual_duration = kpi.get("actual_duration_seconds", kpi.get("actual_duration_sec", 0))
    min_duration = target_duration - 60
    if actual_duration < min_duration:
        decision = "FAIL"
        reasons.append(f"❌ duration={actual_duration:.1f}s < {min_duration}s (target={target_duration}s)")
        critical_checks["duration"] = False
    else:
        reasons.append(f"✅ duration={actual_duration:.1f}s >= {min_duration}s (Critical: PASS)")
        critical_checks["duration"] = True
    
    # Critical: ERROR count (0이어야 함)
    error_count = error_counts.get("ERROR", 0)
    if error_count > 0:
        decision = "FAIL"
        reasons.append(f"❌ ERROR count={error_count} > 0 (안정성 FAIL)")
        critical_checks["error_free"] = False
    else:
        reasons.append("✅ ERROR count=0 (Critical: PASS)")
        critical_checks["error_free"] = True
    
    # Critical: kill_switch
    kill_switch = kpi.get("kill_switch_triggered", False)
    if kill_switch:
        decision = "FAIL"
        reasons.append("❌ kill_switch_triggered=true (Critical: FAIL)")
        critical_checks["kill_switch"] = False
    else:
        critical_checks["kill_switch"] = True
    
    # Semi-Critical: round_trips (INFO만, PASS 판정에 영향 없음)
    round_trips = kpi.get("round_trips_completed", kpi.get("round_trips_count", 0))
    if round_trips < 1:
        info_notes.append(f"ℹ️  round_trips={round_trips} (시장 조건/Zone threshold 영향, D95에서 성능 검증)")
        semi_checks["round_trips"] = "INFO_LOW"
    else:
        info_notes.append(f"✅ round_trips={round_trips} >= 1 (Semi-Critical: OK)")
        semi_checks["round_trips"] = "OK"
    
    # Variable: win_rate (INFO만)
    win_rate = kpi.get("win_rate_pct", 0.0)
    info_notes.append(f"ℹ️  win_rate={win_rate:.1f}% (Variable: INFO, D95 성능 Gate에서 검증)")
    
    # Variable: PnL (INFO만)
    pnl = kpi.get("total_pnl_usd", 0.0)
    info_notes.append(f"ℹ️  PnL=${pnl:.2f} (Variable: INFO, 시장 종속)")
    
    return {
        "decision": decision,
        "reasons": reasons,
        "info_notes": info_notes,
        "tolerances": {
            "duration_min": min_duration,
            "round_trips_min": 1,
            "error_count_max": 0
        },
        "critical_checks": critical_checks,
        "semi_checks": semi_checks,
        "error_counts": error_counts
    }


def save_evidence(
    out_dir: Path,
    kpi: Dict[str, Any],
    decision: Dict[str, Any],
    log_file: Path,
    tail_lines: int
) -> None:
    """
    Evidence 파일 저장
    
    Args:
        out_dir: 출력 디렉토리
        kpi: KPI 딕셔너리
        decision: 판정 결과
        log_file: 로그 파일 경로
        tail_lines: tail 라인 수
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    run_type = kpi.get("run_type", "unknown")
    
    # KPI JSON
    kpi_file = out_dir / f"d94_{run_type}_kpi.json"
    kpi_file.write_text(
        json.dumps(kpi, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"[INFO] KPI 저장: {kpi_file}")
    
    # Decision JSON
    decision_file = out_dir / "d94_decision.json"
    decision_file.write_text(
        json.dumps(decision, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"[INFO] 판정 저장: {decision_file}")
    
    # Log tail + error counts
    error_counts = count_errors_in_log(log_file)
    log_tail = extract_log_tail(log_file, tail_lines)
    
    tail_content = f"""D94 Long-run PAPER Gate - Log Tail
{'='*80}

Run Type: {run_type}
Run ID: {kpi.get('run_id', 'unknown')}
Duration: {kpi.get('actual_duration_sec', 0):.1f}s

Error Counts:
- ERROR: {error_counts.get('ERROR', 0)}
- Traceback: {error_counts.get('Traceback', 0)}
- WARNING: {error_counts.get('WARNING', 0)}

{'='*80}
Log Tail (last {tail_lines} lines):
{'='*80}

{log_tail}
"""
    
    tail_file = out_dir / "d94_log_tail.txt"
    tail_file.write_text(tail_content, encoding="utf-8")
    print(f"[INFO] 로그 tail 저장: {tail_file}")


def main() -> int:
    """
    메인 실행 로직
    
    Returns:
        0: PASS / PASS_WITH_WARNINGS
        2: FAIL
    """
    args = parse_args()
    
    print("="*80)
    print("D94: 1h+ Long-run PAPER 안정성 Gate Runner")
    print("="*80)
    
    # Secrets check
    print("\n[STEP 0] 필수 시크릿 검증 중...")
    secrets_ok, missing = check_required_secrets()
    if not secrets_ok:
        print(f"[FAIL] 필수 시크릿 누락: {missing}")
        return 2
    print("[OK] 모든 필수 시크릿 설정됨")
    
    out_dir = Path(args.out_dir)
    
    # Smoke run (선택)
    if args.smoke:
        smoke_duration = 1200  # 20분
        exit_code, log_dir, metadata = run_paper_longrun(smoke_duration, "smoke")
        
        if exit_code != 0:
            print(f"\n[FAIL] Smoke 실행 실패 (exit_code={exit_code})")
            return 2
        
        # Smoke KPI 추출 및 저장
        kpi_smoke = extract_kpi_from_log(log_dir, metadata)
        error_counts_smoke = count_errors_in_log(log_dir / "gate.log")
        decision_smoke = judge_decision(kpi_smoke, error_counts_smoke, smoke_duration)
        
        save_evidence(out_dir, kpi_smoke, decision_smoke, log_dir / "gate.log", args.log_tail_lines)
        
        if decision_smoke["decision"] == "FAIL":
            print(f"\n[FAIL] Smoke 판정 실패: {decision_smoke['reasons']}")
            return 2
        
        print(f"\n[OK] Smoke 판정: {decision_smoke['decision']}")
        print("Baseline 실행으로 진행...")
        time.sleep(10)  # 환경 안정화
    
    # Baseline run (필수)
    exit_code, log_dir, metadata = run_paper_longrun(args.duration_sec, "baseline")
    
    if exit_code != 0:
        print(f"\n[FAIL] Baseline 실행 실패 (exit_code={exit_code})")
        return 2
    
    # Baseline KPI 추출 및 저장
    kpi_baseline = extract_kpi_from_log(log_dir, metadata)
    error_counts_baseline = count_errors_in_log(log_dir / "gate.log")
    decision_baseline = judge_decision(kpi_baseline, error_counts_baseline, args.duration_sec)
    
    save_evidence(out_dir, kpi_baseline, decision_baseline, log_dir / "gate.log", args.log_tail_lines)
    
    # 최종 판정
    decision = decision_baseline["decision"]
    
    print(f"\n{'='*80}")
    print(f"최종 판정: {decision}")
    print(f"사유: {decision_baseline['reasons']}")
    print(f"{'='*80}")
    
    if decision == "PASS":
        print("\n✅ [PASS] D94 Long-run PAPER 안정성 Gate 성공")
        return 0
    elif decision == "PASS_WITH_WARNINGS":
        print("\n⚠️  [PASS_WITH_WARNINGS] D94 안정성 Gate 통과 (경고 있음)")
        print(f"경고: {decision_baseline.get('reasons', [])}")
        return 0
    else:
        print("\n❌ [FAIL] D94 Long-run PAPER 안정성 Gate 실패")
        return 2


if __name__ == "__main__":
    sys.exit(main())
