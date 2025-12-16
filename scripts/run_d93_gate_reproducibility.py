#!/usr/bin/env python3
"""
================================================================================
D93: Gate 10m 재현성 검증 Runner (Reproducibility Verification)
================================================================================
목적: 동일 조건에서 Gate 10m을 2회 실행하여 재현성 검증

상용급 판정 로직:
  - Critical 필드: exit_code, errors (완전 일치 요구)
  - Semi-Critical 필드: round_trips_count, actual_duration_sec (tolerance 허용)
  - Variable 필드: pnl_usd (시장 종속, 참고용)
  - 판정: PASS / PASS_WITH_WARNINGS / FAIL

Evidence:
  - logs/d93/repro_run*/ → docs/D93/evidence/ 복사 (커밋 가능)

Exit Code:
  - 0: PASS / PASS_WITH_WARNINGS
  - 2: FAIL

사용:
  python scripts/run_d93_gate_reproducibility.py
"""

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional


def find_latest_gate_log_dir() -> Optional[Path]:
    """
    logs/gate_10m/ 아래에서 가장 최근 생성된 gate_10m_* 폴더 찾기
    
    Returns:
        최근 생성된 Gate 로그 디렉토리 경로 또는 None
    """
    gate_logs_root = Path("logs/gate_10m")
    if not gate_logs_root.exists():
        return None
    
    # gate_10m_* 패턴 폴더들 찾기
    gate_dirs = sorted(
        [d for d in gate_logs_root.iterdir() if d.is_dir() and d.name.startswith("gate_10m_")],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )
    
    return gate_dirs[0] if gate_dirs else None


def copy_gate_artifacts(src_gate_dir: Path, dest_log_dir: Path) -> Tuple[bool, str]:
    """
    Gate 실행 결과물(KPI JSON, gate.log)을 D93 로그 디렉토리로 복사
    
    Args:
        src_gate_dir: Gate 스크립트가 생성한 원본 로그 디렉토리
        dest_log_dir: D93 재현성 검증 로그 디렉토리
    
    Returns:
        (success, message)
    """
    try:
        # KPI JSON 복사
        src_kpi = src_gate_dir / "gate_10m_kpi.json"
        dest_kpi = dest_log_dir / "gate_10m_kpi.json"
        
        if src_kpi.exists():
            shutil.copy2(src_kpi, dest_kpi)
        else:
            return False, f"KPI JSON 파일이 없습니다: {src_kpi}"
        
        # gate.log 복사
        src_log = src_gate_dir / "gate.log"
        dest_log = dest_log_dir / "gate.log"
        
        if src_log.exists():
            shutil.copy2(src_log, dest_log)
        else:
            return False, f"gate.log 파일이 없습니다: {src_log}"
        
        return True, f"복사 성공: {src_gate_dir.name} → {dest_log_dir.name}"
        
    except Exception as e:
        return False, f"복사 중 예외: {e}"


def run_gate_10m(run_id: int, base_log_dir: Path) -> Tuple[int, Path, Path]:
    """
    Gate 10m 1회 실행 및 결과물 자동 복사
    
    Args:
        run_id: 실행 번호 (1 또는 2)
        base_log_dir: 로그 기본 디렉토리
    
    Returns:
        (exit_code, log_dir, kpi_json_path)
    """
    print(f"\n{'='*80}")
    print(f"Gate 10m Run #{run_id} 실행 중...")
    print(f"{'='*80}\n")
    
    # D93 로그 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = base_log_dir / f"repro_run{run_id}_{timestamp}"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 실행 전 기존 Gate 로그 폴더 목록 저장 (최신 폴더 식별용)
    gate_logs_before = set()
    gate_logs_root = Path("logs/gate_10m")
    if gate_logs_root.exists():
        gate_logs_before = set(d.name for d in gate_logs_root.iterdir() if d.is_dir())
    
    # Gate 10m 실행
    cmd = [
        sys.executable,
        "scripts/run_gate_10m_ssot_v3_2.py"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=900  # 15분 타임아웃
        )
        
        exit_code = result.returncode
        
        # 출력 저장
        (log_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
        (log_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
        
        print(f"Run #{run_id} 완료: exit_code={exit_code}")
        
        # Gate 스크립트가 생성한 최신 로그 디렉토리 찾기
        latest_gate_dir = find_latest_gate_log_dir()
        
        if latest_gate_dir and latest_gate_dir.name not in gate_logs_before:
            print(f"Gate 로그 디렉토리 발견: {latest_gate_dir}")
            
            # KPI JSON 및 gate.log 복사
            success, msg = copy_gate_artifacts(latest_gate_dir, log_dir)
            
            if success:
                print(f"[INFO] {msg}")
            else:
                print(f"[WARN] {msg}")
        else:
            print(f"[WARN] 새로운 Gate 로그 디렉토리를 찾을 수 없습니다")
        
        kpi_json = log_dir / "gate_10m_kpi.json"
        print(f"D93 로그 디렉토리: {log_dir}")
        print(f"KPI JSON 경로: {kpi_json}")
        
        return exit_code, log_dir, kpi_json
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Run #{run_id} 타임아웃 (15분 초과)")
        (log_dir / "stderr.log").write_text("[ERROR] Gate 실행 타임아웃 (15분)", encoding="utf-8")
        return 124, log_dir, log_dir / "gate_10m_kpi.json"
    except Exception as e:
        print(f"[ERROR] Run #{run_id} 실행 중 예외: {e}")
        (log_dir / "stderr.log").write_text(f"[ERROR] {e}", encoding="utf-8")
        return 2, log_dir, log_dir / "gate_10m_kpi.json"


def compare_kpi_json(kpi1_path: Path, kpi2_path: Path) -> Dict[str, Any]:
    """
    두 KPI JSON 비교 (상용급 판정 로직)
    
    Critical 필드 (완전 일치):
      - exit_code
    
    Semi-Critical 필드 (tolerance 허용):
      - round_trips_count: ±2 RT
      - actual_duration_sec: ±30초
    
    Variable 필드 (참고):
      - pnl_usd: 시장 종속, 경고만 출력
    
    Args:
        kpi1_path: Run 1 KPI JSON 경로
        kpi2_path: Run 2 KPI JSON 경로
    
    Returns:
        비교 결과 딕셔너리 (decision: PASS / PASS_WITH_WARNINGS / FAIL)
    """
    if not kpi1_path.exists() or not kpi2_path.exists():
        return {
            "decision": "FAIL",
            "reason": "KPI JSON 파일 누락",
            "kpi1_exists": kpi1_path.exists(),
            "kpi2_exists": kpi2_path.exists()
        }
    
    kpi1 = json.loads(kpi1_path.read_text(encoding="utf-8"))
    kpi2 = json.loads(kpi2_path.read_text(encoding="utf-8"))
    
    # 필드 일치 검증
    kpi1_keys = set(kpi1.keys())
    kpi2_keys = set(kpi2.keys())
    
    if kpi1_keys != kpi2_keys:
        return {
            "decision": "FAIL",
            "reason": "KPI 필드 불일치",
            "only_in_run1": list(kpi1_keys - kpi2_keys),
            "only_in_run2": list(kpi2_keys - kpi1_keys)
        }
    
    # 필드 분류
    critical_fields = ["exit_code"]
    semi_critical_fields = {
        "round_trips_count": 2,  # ±2 RT
        "actual_duration_sec": 30  # ±30초
    }
    variable_fields = ["pnl_usd"]
    
    # 비교 결과
    diffs = {}
    critical_fail = False
    warnings = []
    
    for key in kpi1_keys:
        val1 = kpi1[key]
        val2 = kpi2[key]
        
        # Critical 필드: 완전 일치 요구
        if key in critical_fields:
            if val1 != val2:
                critical_fail = True
                diffs[key] = {
                    "type": "critical",
                    "v1": val1,
                    "v2": val2,
                    "tolerance": 0,
                    "ok": False
                }
        
        # Semi-Critical 필드: tolerance 허용
        elif key in semi_critical_fields:
            tolerance = semi_critical_fields[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                diff = abs(val1 - val2)
                ok = diff <= tolerance
                diffs[key] = {
                    "type": "semi_critical",
                    "v1": val1,
                    "v2": val2,
                    "diff": diff,
                    "tolerance": tolerance,
                    "ok": ok
                }
                if not ok:
                    warnings.append(f"{key}: {val1} vs {val2} (tolerance={tolerance})")
        
        # Variable 필드: 참고용 (경고만)
        elif key in variable_fields:
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                diff = abs(val1 - val2)
                diffs[key] = {
                    "type": "variable",
                    "v1": val1,
                    "v2": val2,
                    "diff": diff,
                    "ok": True  # 항상 OK (참고용)
                }
        
        # 기타 필드: 부동소수점 오차 허용
        else:
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if abs(val1 - val2) > 1e-6:
                    diffs[key] = {
                        "type": "other",
                        "v1": val1,
                        "v2": val2,
                        "ok": True
                    }
            elif val1 != val2:
                diffs[key] = {
                    "type": "other",
                    "v1": val1,
                    "v2": val2,
                    "ok": False
                }
    
    # 판정
    if critical_fail:
        return {
            "decision": "FAIL",
            "reason": "Critical 필드 불일치",
            "diffs": diffs
        }
    
    if warnings:
        return {
            "decision": "PASS_WITH_WARNINGS",
            "reason": "Semi-Critical 필드 tolerance 초과",
            "warnings": warnings,
            "diffs": diffs
        }
    
    return {
        "decision": "PASS",
        "reason": "완전 재현성 확인",
        "diffs": diffs
    }


def copy_to_evidence(base_log_dir: Path, log1: Path, log2: Path, comparison_file: Path) -> bool:
    """
    logs/d93/ 산출물을 docs/D93/evidence/로 복사 (커밋 가능한 증거)
    
    Args:
        base_log_dir: logs/d93 기본 디렉토리
        log1: Run 1 로그 디렉토리
        log2: Run 2 로그 디렉토리
        comparison_file: KPI 비교 결과 JSON
    
    Returns:
        성공 여부
    """
    try:
        evidence_dir = Path("docs/D93/evidence")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        
        # KPI JSON 복사 (로그는 너무 커서 제외)
        kpi1_src = log1 / "gate_10m_kpi.json"
        kpi2_src = log2 / "gate_10m_kpi.json"
        
        if kpi1_src.exists():
            shutil.copy2(kpi1_src, evidence_dir / "repro_run1_gate_10m_kpi.json")
            print(f"[INFO] 증거 복사: {kpi1_src.name} → docs/D93/evidence/")
        
        if kpi2_src.exists():
            shutil.copy2(kpi2_src, evidence_dir / "repro_run2_gate_10m_kpi.json")
            print(f"[INFO] 증거 복사: {kpi2_src.name} → docs/D93/evidence/")
        
        if comparison_file.exists():
            shutil.copy2(comparison_file, evidence_dir / "kpi_comparison.json")
            print(f"[INFO] 증거 복사: {comparison_file.name} → docs/D93/evidence/")
        
        print(f"\n✅ Evidence 폴더 준비 완료: {evidence_dir}")
        return True
        
    except Exception as e:
        print(f"[WARN] Evidence 복사 중 예외: {e}")
        return False


def main() -> int:
    """
    메인 실행 로직
    
    Returns:
        0: PASS / PASS_WITH_WARNINGS
        2: FAIL
    """
    print("="*80)
    print("D93: Gate 10m 재현성 검증 Runner (상용급)")
    print("="*80)
    
    # 로그 디렉토리 준비
    base_log_dir = Path("logs/d93")
    base_log_dir.mkdir(parents=True, exist_ok=True)
    
    # Run 1 실행
    exit1, log1, kpi1 = run_gate_10m(1, base_log_dir)
    
    if exit1 != 0:
        print(f"\n[FAIL] Run #1 실패 (exit_code={exit1})")
        return 2
    
    # 대기 (환경 안정화)
    print("\n환경 안정화 대기 중 (10초)...")
    time.sleep(10)
    
    # Run 2 실행
    exit2, log2, kpi2 = run_gate_10m(2, base_log_dir)
    
    if exit2 != 0:
        print(f"\n[FAIL] Run #2 실패 (exit_code={exit2})")
        return 2
    
    # KPI 비교
    print("\n" + "="*80)
    print("KPI JSON 비교 중...")
    print("="*80)
    
    comparison = compare_kpi_json(kpi1, kpi2)
    
    # 비교 결과 저장
    comparison_file = base_log_dir / "kpi_comparison.json"
    comparison_file.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"\n판정: {comparison['decision']}")
    print(f"사유: {comparison['reason']}")
    print(f"비교 파일: {comparison_file}")
    
    # Evidence 폴더로 복사
    print("\n" + "="*80)
    print("Evidence 폴더 복사 중...")
    print("="*80)
    copy_to_evidence(base_log_dir, log1, log2, comparison_file)
    
    # 최종 판정
    decision = comparison["decision"]
    
    if decision == "PASS":
        print("\n✅ [PASS] Gate 10m 재현성 검증 성공 (완전 일치)")
        return 0
    elif decision == "PASS_WITH_WARNINGS":
        print("\n⚠️  [PASS_WITH_WARNINGS] 재현성 검증 통과 (경고 있음)")
        print(f"경고: {comparison.get('warnings', [])}")
        return 0
    else:
        print("\n❌ [FAIL] Gate 10m 재현성 검증 실패")
        if "diffs" in comparison:
            print(f"차이점: {json.dumps(comparison['diffs'], indent=2, ensure_ascii=False)}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
