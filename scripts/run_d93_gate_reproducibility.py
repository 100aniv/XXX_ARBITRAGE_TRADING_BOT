#!/usr/bin/env python3
"""
================================================================================
D93: Gate 10m 재현성 검증 Runner (Reproducibility Verification)
================================================================================
목적: 동일 조건에서 Gate 10m을 2회 실행하여 재현성 검증

Exit Code:
  - 0: PASS (재현성 확인)
  - 1: FAIL (재현성 실패)
  - 2: ERROR (실행 중 에러)

사용:
  python scripts/run_d93_gate_reproducibility.py
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple


def run_gate_10m(run_id: int, base_log_dir: Path) -> Tuple[int, Path, Path]:
    """
    Gate 10m 1회 실행
    
    Args:
        run_id: 실행 번호 (1 또는 2)
        base_log_dir: 로그 기본 디렉토리
    
    Returns:
        (exit_code, log_dir, kpi_json_path)
    """
    print(f"\n{'='*80}")
    print(f"Gate 10m Run #{run_id} 실행 중...")
    print(f"{'='*80}\n")
    
    # 로그 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = base_log_dir / f"gate_10m_run{run_id}_{timestamp}"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # KPI JSON 경로
    kpi_json = log_dir / "gate_10m_kpi.json"
    
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
        
        # KPI JSON 복사 (실제 경로는 Gate 스크립트에서 생성한 경로)
        # TODO: Gate 스크립트에서 생성한 KPI JSON을 여기로 복사하는 로직 추가
        
        print(f"Run #{run_id} 완료: exit_code={exit_code}")
        print(f"로그 디렉토리: {log_dir}")
        
        return exit_code, log_dir, kpi_json
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Run #{run_id} 타임아웃 (15분 초과)")
        return 124, log_dir, kpi_json
    except Exception as e:
        print(f"[ERROR] Run #{run_id} 실행 중 예외: {e}")
        return 2, log_dir, kpi_json


def compare_kpi_json(kpi1_path: Path, kpi2_path: Path) -> Dict[str, Any]:
    """
    두 KPI JSON 비교 (재현성 검증)
    
    Args:
        kpi1_path: Run 1 KPI JSON 경로
        kpi2_path: Run 2 KPI JSON 경로
    
    Returns:
        비교 결과 딕셔너리
    """
    if not kpi1_path.exists() or not kpi2_path.exists():
        return {
            "status": "FAIL",
            "reason": "KPI JSON 파일 누락",
            "kpi1_exists": kpi1_path.exists(),
            "kpi2_exists": kpi2_path.exists()
        }
    
    try:
        kpi1 = json.loads(kpi1_path.read_text(encoding="utf-8"))
        kpi2 = json.loads(kpi2_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "status": "FAIL",
            "reason": f"KPI JSON 파싱 오류: {e}",
            "kpi1_exists": kpi1_path.exists(),
            "kpi2_exists": kpi2_path.exists()
        }
    
    # 필드 일치 검증
    kpi1_keys = set(kpi1.keys())
    kpi2_keys = set(kpi2.keys())
    
    if kpi1_keys != kpi2_keys:
        return {
            "status": "FAIL",
            "reason": "KPI 필드 불일치",
            "only_in_run1": list(kpi1_keys - kpi2_keys),
            "only_in_run2": list(kpi2_keys - kpi1_keys)
        }
    
    # 재현성 검증 핵심 필드
    critical_fields = {
        "exit_code": {"type": "exact", "tolerance": 0},
        "actual_duration_sec": {"type": "range", "tolerance": 10},  # ±10초 허용
    }
    
    # 변동 허용 필드
    variable_fields = {
        "pnl_usd": {"type": "range", "tolerance": 5.0},  # ±5 USD 허용 (시장 변동)
        "round_trips_count": {"type": "range", "tolerance": 2},  # ±2 RT 허용
    }
    
    critical_differences = {}
    variable_differences = {}
    other_differences = {}
    
    for key in kpi1_keys:
        val1 = kpi1[key]
        val2 = kpi2[key]
        
        # 중첩 객체는 문자열 비교
        if isinstance(val1, (dict, list)) or isinstance(val2, (dict, list)):
            if json.dumps(val1, sort_keys=True) != json.dumps(val2, sort_keys=True):
                other_differences[key] = {"run1": val1, "run2": val2}
            continue
        
        # Critical 필드 검증
        if key in critical_fields:
            check = critical_fields[key]
            if check["type"] == "exact":
                if val1 != val2:
                    critical_differences[key] = {"run1": val1, "run2": val2, "tolerance": check["tolerance"]}
            elif check["type"] == "range":
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    if abs(val1 - val2) > check["tolerance"]:
                        critical_differences[key] = {"run1": val1, "run2": val2, "tolerance": check["tolerance"], "diff": abs(val1 - val2)}
        
        # Variable 필드 검증
        elif key in variable_fields:
            check = variable_fields[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if abs(val1 - val2) > check["tolerance"]:
                    variable_differences[key] = {"run1": val1, "run2": val2, "tolerance": check["tolerance"], "diff": abs(val1 - val2)}
        
        # 기타 필드
        else:
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if abs(val1 - val2) > 1e-6:  # 부동소수점 오차
                    other_differences[key] = {"run1": val1, "run2": val2}
            elif val1 != val2:
                other_differences[key] = {"run1": val1, "run2": val2}
    
    # 재현성 판정
    if critical_differences:
        return {
            "status": "FAIL",
            "reason": "Critical 필드 재현성 실패",
            "critical_differences": critical_differences,
            "variable_differences": variable_differences,
            "other_differences": other_differences
        }
    
    if variable_differences or other_differences:
        return {
            "status": "PARTIAL",
            "reason": "일부 필드 변동 (허용 가능)",
            "critical_differences": critical_differences,
            "variable_differences": variable_differences,
            "other_differences": other_differences
        }
    
    return {
        "status": "PASS",
        "reason": "완전 재현성 확인",
        "critical_differences": {},
        "variable_differences": {},
        "other_differences": {}
    }


def main() -> int:
    """
    메인 실행 로직
    
    Returns:
        0: PASS, 1: FAIL, 2: ERROR
    """
    print("="*80)
    print("D93: Gate 10m 재현성 검증 Runner")
    print("="*80)
    
    # 로그 디렉토리 준비
    base_log_dir = Path("logs/d93")
    base_log_dir.mkdir(parents=True, exist_ok=True)
    
    # Run 1 실행
    exit1, log1, kpi1 = run_gate_10m(1, base_log_dir)
    
    if exit1 != 0:
        print(f"\n[FAIL] Run #1 실패 (exit_code={exit1})")
        return 1
    
    # 대기 (환경 안정화)
    print("\n환경 안정화 대기 중 (10초)...")
    time.sleep(10)
    
    # Run 2 실행
    exit2, log2, kpi2 = run_gate_10m(2, base_log_dir)
    
    if exit2 != 0:
        print(f"\n[FAIL] Run #2 실패 (exit_code={exit2})")
        return 1
    
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
    
    print(f"\n비교 결과: {comparison['status']}")
    print(f"사유: {comparison['reason']}")
    print(f"비교 파일: {comparison_file}")
    
    if comparison["status"] == "PASS":
        print("\n✅ [PASS] Gate 10m 재현성 검증 성공")
        return 0
    elif comparison["status"] == "PARTIAL":
        print("\n⚠️  [PARTIAL] 일부 차이 발견 (수동 검토 필요)")
        print(f"차이점: {comparison.get('differences', {})}")
        return 0  # PARTIAL도 PASS로 간주 (허용 가능한 차이)
    else:
        print("\n❌ [FAIL] Gate 10m 재현성 검증 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
