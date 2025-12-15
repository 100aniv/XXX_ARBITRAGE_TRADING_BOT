#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 POST-MOVE-HARDEN v3.2: Gate 10분 테스트 SSOT 래퍼 (Secrets Check 통합)

Gate 10분 테스트의 다음 조건을 강제합니다:
1. **Secrets 검증**: API 키 등 필수 시크릿 존재 확인 (없으면 exit 2)
2. Duration >= 600초
3. Exit code == 0
4. KPI JSON 생성 (실패 시에도)

Usage:
    ARBITRAGE_ENV=paper python scripts/run_gate_10m_ssot_v3_2.py
"""

import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from datetime import datetime, timezone


def check_required_secrets() -> tuple:
    """
    필수 시크릿 검증
    
    Returns:
        (all_present, missing_vars)
    """
    env_name = os.getenv("ARBITRAGE_ENV", "paper")
    env_file = Path(__file__).parent.parent / f".env.{env_name}"
    
    try:
        from dotenv import load_dotenv
        if env_file.exists():
            load_dotenv(env_file, override=True)
            print(f"[INFO] Loaded {env_file}")
        else:
            return False, [f"{env_file} 파일이 없습니다"]
    except ImportError:
        return False, ["python-dotenv 패키지가 필요합니다"]
    
    missing = []
    
    # Exchange API Keys
    has_upbit = bool(os.getenv("UPBIT_ACCESS_KEY") and os.getenv("UPBIT_SECRET_KEY"))
    has_binance = bool(os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET"))
    
    if not has_upbit and not has_binance:
        missing.append("UPBIT_ACCESS_KEY + UPBIT_SECRET_KEY (또는 BINANCE_API_KEY + BINANCE_API_SECRET)")
    
    # PostgreSQL
    if not os.getenv("POSTGRES_DSN") and not os.getenv("POSTGRES_HOST"):
        missing.append("POSTGRES_DSN (또는 POSTGRES_HOST)")
    
    # Redis
    if not os.getenv("REDIS_URL") and not os.getenv("REDIS_HOST"):
        missing.append("REDIS_URL (또는 REDIS_HOST)")
    
    return len(missing) == 0, missing


def create_run_directories() -> Path:
    """Run ID 생성 및 로그 디렉토리 생성"""
    run_id = datetime.now().strftime("gate_10m_%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent.parent / "logs" / "gate_10m" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def run_gate_test(log_dir: Path, duration_sec: int = 600) -> tuple:
    """
    Gate 테스트 실행
    
    Returns:
        (exit_code, duration_sec, metadata)
    """
    start_time = datetime.now(timezone.utc)
    gate_log = log_dir / "gate.log"
    
    cmd = [
        sys.executable,
        "scripts/run_d77_0_topn_arbitrage_paper.py",
        "--universe", "top20",
        "--run-duration-seconds", str(duration_sec),
        "--data-source", "real",
        "--monitoring-enabled",
        "--zone-profile-file", "config/arbitrage/zone_profiles_v2.yaml"
    ]
    
    metadata = {
        "command": " ".join(cmd),
        "start_time": start_time.isoformat(),
        "target_duration_sec": duration_sec
    }
    
    with open(gate_log, "w", encoding="utf-8") as log_file:
        try:
            result = subprocess.run(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent.parent,
                timeout=duration_sec + 60
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            log_file.write("\n\n[ERROR] Gate 테스트 타임아웃\n")
            exit_code = 124
        except Exception as e:
            log_file.write(f"\n\n[ERROR] 예외 발생:\n{traceback.format_exc()}\n")
            exit_code = 1
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    metadata["end_time"] = end_time.isoformat()
    metadata["actual_duration_sec"] = duration
    metadata["exit_code"] = exit_code
    
    return exit_code, duration, metadata


def extract_kpi_from_logs(log_dir: Path) -> dict:
    """로그에서 KPI 추출"""
    kpi = {
        "round_trips_count": 0,
        "pnl_usd": 0.0,
        "zone_profiles_loaded": {"attempted": 0, "success": 0, "profiles": []},
        "errors": []
    }
    
    gate_log = log_dir / "gate.log"
    if not gate_log.exists():
        kpi["errors"].append("gate.log 파일이 존재하지 않습니다")
        return kpi
    
    try:
        log_content = gate_log.read_text(encoding="utf-8", errors="replace")
        
        # Round trips 카운트
        entry_count = log_content.count("[D82-1] Entry:")
        exit_count = log_content.count("[D82-1] Exit:")
        kpi["round_trips_count"] = min(entry_count, exit_count)
        
        # Zone profiles
        if "Zone Profile" in log_content:
            kpi["zone_profiles_loaded"]["attempted"] = 1
            if "[ZONE_THRESHOLD]" in log_content:
                kpi["zone_profiles_loaded"]["success"] = 1
        
        # PnL 추출
        pnl_lines = [line for line in log_content.splitlines() if "PnL=$" in line]
        if pnl_lines:
            try:
                pnl_part = pnl_lines[-1].split("PnL=$")[1].split(",")[0]
                kpi["pnl_usd"] = float(pnl_part)
            except:
                pass
        
        # 에러 수집
        error_lines = [line.strip() for line in log_content.splitlines()[-200:] 
                       if "ERROR" in line or "FAIL" in line]
        if error_lines:
            kpi["errors"] = error_lines[:10]
    
    except Exception as e:
        kpi["errors"].append(f"KPI 추출 중 예외: {str(e)}")
    
    return kpi


def generate_kpi_json(log_dir: Path, metadata: dict, kpi: dict) -> Path:
    """KPI JSON 파일 생성"""
    kpi_path = log_dir / "gate_10m_kpi.json"
    
    kpi_data = {
        "run_id": log_dir.name,
        "start_ts": metadata.get("start_time"),
        "end_ts": metadata.get("end_time"),
        "duration_sec": metadata.get("actual_duration_sec", 0),
        "exit_code": metadata.get("exit_code", 1),
        "command": metadata.get("command", ""),
        **kpi
    }
    
    with open(kpi_path, "w", encoding="utf-8") as f:
        json.dump(kpi_data, f, indent=2, ensure_ascii=False)
    
    return kpi_path


def validate_gate_results(exit_code: int, duration: float, kpi: dict) -> tuple:
    """결과 검증"""
    violations = []
    
    if duration < 600:
        violations.append(f"실행 시간 부족: {duration:.1f}초 < 600초")
    
    if exit_code != 0:
        violations.append(f"Exit code 실패: {exit_code} != 0")
    
    if kpi["round_trips_count"] == 0:
        violations.append("Round trips가 0입니다 (거래 없음)")
    
    return len(violations) == 0, violations


def main():
    """Main entry point"""
    print("=" * 70)
    print("D92 v3.2: Gate 10분 테스트 SSOT (Secrets Check 통합)")
    print("=" * 70)
    print()
    
    # STEP 0: 필수 시크릿 검증
    print("[STEP 0/4] 필수 시크릿 검증 중...")
    secrets_ok, missing = check_required_secrets()
    
    if not secrets_ok:
        print("[FAIL] 필수 시크릿이 누락되었습니다:")
        for var in missing:
            print(f"  - {var}")
        print()
        env_name = os.getenv("ARBITRAGE_ENV", "paper")
        env_file = Path(__file__).parent.parent / f".env.{env_name}"
        print(f"해결 방법: {env_file} 파일에 위 변수를 설정하세요.")
        print()
        print("[CRITICAL] Gate 테스트 실행 중단 (Exit Code 2)")
        return 2
    
    print("[OK] 모든 필수 시크릿 설정됨")
    print()
    
    # STEP 1: 디렉토리 생성
    print("[STEP 1/4] 로그 디렉토리 생성 중...")
    log_dir = create_run_directories()
    print(f"[OK] {log_dir}")
    print()
    
    # STEP 2: Gate 테스트 실행
    print("[STEP 2/4] Gate 10m 테스트 실행 중 (600초)...")
    exit_code, duration, metadata = run_gate_test(log_dir, duration_sec=600)
    print(f"[OK] 실행 완료: {duration:.1f}초, exit_code={exit_code}")
    print()
    
    # STEP 3: KPI 추출 및 저장
    print("[STEP 3/4] KPI 추출 및 저장 중...")
    kpi = extract_kpi_from_logs(log_dir)
    kpi_file = generate_kpi_json(log_dir, metadata, kpi)
    print(f"[OK] KPI 저장: {kpi_file}")
    print()
    
    # STEP 4: 최종 검증
    print("[STEP 4/4] 최종 검증 중...")
    passed, violations = validate_gate_results(exit_code, duration, kpi)
    
    print()
    print("=" * 70)
    if passed:
        print("[PASS] Gate 10분 테스트 완료")
        print()
        print("KPI 요약:")
        print(f"  - Duration: {duration:.1f}초")
        print(f"  - Exit Code: {exit_code}")
        print(f"  - Round Trips: {kpi['round_trips_count']}")
        print(f"  - PnL: ${kpi['pnl_usd']:.2f}")
        print()
        print("증거 파일:")
        print(f"  - 로그: {log_dir / 'gate.log'}")
        print(f"  - KPI: {kpi_file}")
        return 0
    else:
        print("[FAIL] Gate 10분 테스트 실패")
        print()
        print("실패 사유:")
        for v in violations:
            print(f"  - {v}")
        print()
        print("증거 파일:")
        print(f"  - 로그: {log_dir / 'gate.log'}")
        print(f"  - KPI: {kpi_file}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
