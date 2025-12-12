#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D92-5: 10분 스모크 테스트 자동 실행 및 AC 자동 판정

목적:
- 10분 스모크 테스트를 자동으로 실행
- 종료 후 KPI를 자동으로 파싱
- AC 기준으로 PASS/FAIL 자동 판정
- 사용자 개입 0
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run_smoke_test(stage_id: str = "d92-5", duration_minutes: int = 10) -> dict:
    """
    10분 스모크 테스트 실행
    
    Args:
        stage_id: Stage ID
        duration_minutes: 실행 시간 (분)
    
    Returns:
        실행 결과 딕셔너리
    """
    print("=" * 80)
    print(f"[D92-5] 10분 스모크 테스트 시작")
    print(f"  Stage ID: {stage_id}")
    print(f"  Duration: {duration_minutes} minutes")
    print("=" * 80)
    
    # 환경 변수 설정
    env = os.environ.copy()
    env["ARBITRAGE_ENV"] = "paper"
    
    # 실행 명령어
    cmd = [
        "python",
        "scripts/run_d92_1_topn_longrun.py",
        "--top-n", "10",
        "--duration-minutes", str(duration_minutes),
        "--mode", "advisory",
        "--stage-id", stage_id,
    ]
    
    print(f"[D92-5] 실행 명령어: {' '.join(cmd)}")
    print(f"[D92-5] 실행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        # 실행
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=(duration_minutes + 2) * 60,  # 2분 버퍼
        )
        
        elapsed = time.time() - start_time
        
        print(f"[D92-5] 실행 종료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[D92-5] 경과 시간: {elapsed/60:.1f}분")
        print(f"[D92-5] Exit code: {result.returncode}")
        
        if result.returncode != 0:
            print("\n[ERROR] 스모크 테스트 실행 실패:")
            print(result.stderr[-2000:])  # 마지막 2000자
            return {
                "status": "failed",
                "error": "execution_failed",
                "exit_code": result.returncode,
                "stderr": result.stderr[-2000:],
            }
        
        return {
            "status": "success",
            "elapsed_seconds": elapsed,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-500:],
        }
        
    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] 스모크 테스트 타임아웃 ({duration_minutes + 2}분)")
        return {
            "status": "failed",
            "error": "timeout",
        }
    except Exception as e:
        print(f"\n[ERROR] 스모크 테스트 예외: {e}")
        return {
            "status": "failed",
            "error": str(e),
        }


def verify_acceptance_criteria(stage_id: str = "d92-5") -> dict:
    """
    Acceptance Criteria 자동 검증
    
    Args:
        stage_id: Stage ID
    
    Returns:
        검증 결과 딕셔너리
    """
    print("\n" + "=" * 80)
    print("[D92-5] Acceptance Criteria 자동 검증")
    print("=" * 80)
    
    stage_dir = Path(f"logs/{stage_id}")
    
    # 최신 run_dir 찾기
    if not stage_dir.exists():
        return {
            "status": "failed",
            "error": f"Stage directory not found: {stage_dir}",
            "ac_results": {},
        }
    
    run_dirs = [d for d in stage_dir.iterdir() if d.is_dir()]
    if not run_dirs:
        return {
            "status": "failed",
            "error": f"No run directories found in {stage_dir}",
            "ac_results": {},
        }
    
    latest_run_dir = max(run_dirs, key=lambda d: d.stat().st_mtime)
    print(f"[D92-5] 최신 run_dir: {latest_run_dir}")
    
    # KPI 파일 찾기
    kpi_files = list(latest_run_dir.glob("*_kpi_summary.json"))
    if not kpi_files:
        return {
            "status": "failed",
            "error": f"No KPI file found in {latest_run_dir}",
            "ac_results": {},
        }
    
    kpi_file = kpi_files[0]
    print(f"[D92-5] KPI 파일: {kpi_file}")
    
    # KPI 로드
    try:
        with open(kpi_file, "r", encoding="utf-8") as f:
            kpi = json.load(f)
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Failed to load KPI: {e}",
            "ac_results": {},
        }
    
    # AC 검증
    ac_results = {}
    
    # AC-2: 경로 SSOT 검증
    ac_results["AC-2"] = {
        "description": "KPI/Telemetry/Trades가 logs/{stage_id}/{run_id}/ 아래에 생성",
        "passed": str(latest_run_dir).startswith(f"logs\\{stage_id}"),
        "evidence": str(latest_run_dir),
    }
    
    # AC-3: run_id가 stage_id prefix 포함
    run_id = kpi.get("session_id", "")
    ac_results["AC-3"] = {
        "description": "run_id가 stage_id prefix 포함",
        "passed": run_id.startswith(stage_id),
        "evidence": f"run_id={run_id}",
    }
    
    # AC-5: KPI에 total_pnl_krw/usd/fx_rate 존재
    has_pnl_krw = "total_pnl_krw" in kpi
    has_pnl_usd = "total_pnl_usd" in kpi
    has_fx_rate = "fx_rate" in kpi
    
    ac_results["AC-5"] = {
        "description": "KPI에 total_pnl_krw/usd/fx_rate 존재",
        "passed": has_pnl_krw and has_pnl_usd and has_fx_rate,
        "evidence": {
            "total_pnl_krw": kpi.get("total_pnl_krw"),
            "total_pnl_usd": kpi.get("total_pnl_usd"),
            "fx_rate": kpi.get("fx_rate"),
        },
    }
    
    # AC-5 (Zone Profiles): zone_profiles_loaded 존재
    zone_profiles_loaded = kpi.get("zone_profiles_loaded", {})
    ac_results["AC-5-ZoneProfiles"] = {
        "description": "KPI에 zone_profiles_loaded (path/sha256/mtime) 존재",
        "passed": bool(zone_profiles_loaded.get("path")),
        "evidence": zone_profiles_loaded,
    }
    
    # Exit reasons 분포
    exit_reasons = kpi.get("exit_reasons", {})
    print(f"\n[KPI] Exit Reasons:")
    for reason, count in exit_reasons.items():
        print(f"  {reason}: {count}")
    
    # 전체 PASS 여부
    all_passed = all(ac["passed"] for ac in ac_results.values())
    
    print(f"\n[D92-5] AC 검증 결과:")
    for ac_id, ac_data in ac_results.items():
        status = "✅ PASS" if ac_data["passed"] else "❌ FAIL"
        print(f"  {ac_id}: {status} - {ac_data['description']}")
    
    return {
        "status": "passed" if all_passed else "failed",
        "run_dir": str(latest_run_dir),
        "kpi_file": str(kpi_file),
        "kpi_summary": {
            "session_id": kpi.get("session_id"),
            "duration_minutes": kpi.get("duration_minutes"),
            "total_trades": kpi.get("total_trades"),
            "round_trips_completed": kpi.get("round_trips_completed"),
            "total_pnl_krw": kpi.get("total_pnl_krw"),
            "total_pnl_usd": kpi.get("total_pnl_usd"),
            "fx_rate": kpi.get("fx_rate"),
            "exit_reasons": exit_reasons,
        },
        "ac_results": ac_results,
    }


def main():
    """메인 함수"""
    print("[D92-5] 10분 스모크 테스트 + AC 자동 판정")
    print("=" * 80)
    
    # 1. 스모크 테스트 실행
    smoke_result = run_smoke_test(stage_id="d92-5", duration_minutes=10)
    
    if smoke_result["status"] != "success":
        print(f"\n❌ 스모크 테스트 실패: {smoke_result.get('error')}")
        sys.exit(1)
    
    print(f"\n✅ 스모크 테스트 완료 ({smoke_result['elapsed_seconds']/60:.1f}분)")
    
    # 2. AC 검증
    ac_result = verify_acceptance_criteria(stage_id="d92-5")
    
    if ac_result["status"] != "passed":
        print(f"\n❌ AC 검증 실패")
        print(json.dumps(ac_result, indent=2, ensure_ascii=False))
        sys.exit(1)
    
    print(f"\n✅ AC 검증 완료 (PASS)")
    
    # 3. 최종 결과 출력
    print("\n" + "=" * 80)
    print("[D92-5] 10분 스모크 + AC 검증 최종 결과")
    print("=" * 80)
    print(f"Run Dir: {ac_result['run_dir']}")
    print(f"KPI File: {ac_result['kpi_file']}")
    print(f"\n[KPI Summary]")
    for key, value in ac_result['kpi_summary'].items():
        print(f"  {key}: {value}")
    
    print("\n✅ D92-5 스모크 테스트 + AC 검증 완료")
    sys.exit(0)


if __name__ == "__main__":
    main()
