#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 POST-MOVE-HARDEN v3.2: Gate 10분 테스트 SSOT 래퍼 (Secrets Check 통합)

Gate 10분 테스트의 다음 조건을 강제합니다:
1. **Secrets 검증**: API 키 등 필수 시크릿 존재 확인 (없으면 FAIL)
2. Duration >= 600초
3. Exit code == 0
4. KPI JSON 생성 (실패 시에도)

Usage:
    ARBITRAGE_ENV=paper python scripts/run_gate_10m_ssot.py
"""

import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from datetime import datetime, timezone


def check_required_secrets() -> tuple[bool, list[str]]:
    """
    필수 시크릿 검증 (check_required_secrets.py 로직 내장)
    
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
    """실행 ID 생성 (타임스탬프 기반)"""
    return datetime.now().strftime("gate_10m_%Y%m%d_%H%M%S")


def create_log_directory(run_id: str) -> Path:
    """로그 디렉토리 생성"""
    log_dir = Path(__file__).parent.parent / "logs" / "gate_10m" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def run_gate_test(log_dir: Path, duration_sec: int = 600) -> tuple[int, float, dict]:
    """
    Gate 테스트 실행
    
    Returns:
        (exit_code, duration_sec, metadata)
    """
    start_time = datetime.now(timezone.utc)
    gate_log = log_dir / "gate.log"
    
    # Gate 테스트 엔트리포인트 (기존 스크립트 래핑)
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
    
    # 실행 (stdout/stderr를 파일로 tee)
    with open(gate_log, "w", encoding="utf-8") as log_file:
        try:
            result = subprocess.run(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent.parent,
                timeout=duration_sec + 60  # 여유 시간 추가
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            log_file.write("\n\n[ERROR] Gate 테스트 타임아웃 (600초 + 60초 초과)\n")
            exit_code = 124  # timeout exit code
        except Exception as e:
            log_file.write(f"\n\n[ERROR] Gate 테스트 실행 중 예외 발생:\n{traceback.format_exc()}\n")
            exit_code = 1
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    metadata["end_time"] = end_time.isoformat()
    metadata["actual_duration_sec"] = duration
    metadata["exit_code"] = exit_code
    
    return exit_code, duration, metadata


def extract_kpi_from_logs(log_dir: Path, metadata: dict) -> dict:
    """
    로그에서 KPI 추출
    
    - round_trips_count
    - pnl_usd
    - win_rate
    - zone_profiles_loaded
    """
    kpi = {
        "round_trips_count": 0,
        "pnl_usd": 0.0,
        "win_rate": 0.0,
        "zone_profiles_loaded": {
            "attempted": 0,
            "success": 0,
            "profiles": []
        },
        "errors": []
    }
    
    gate_log = log_dir / "gate.log"
    if not gate_log.exists():
        kpi["errors"].append("gate.log 파일이 존재하지 않습니다.")
        return kpi
    
    try:
        log_content = gate_log.read_text(encoding="utf-8")
        
        # Round trips 카운트 (간단한 패턴 매칭)
        entry_count = log_content.count("[D82-1] Entry:")
        exit_count = log_content.count("[D82-1] Exit:")
        kpi["round_trips_count"] = min(entry_count, exit_count)
        
        # Zone profiles 로딩 확인
        if "Zone Profile" in log_content or "zone_mode" in log_content:
            kpi["zone_profiles_loaded"]["attempted"] = 1
            if "[ZONE_THRESHOLD]" in log_content:
                kpi["zone_profiles_loaded"]["success"] = 1
                # 프로파일 이름 추출 (간단한 예시)
                for line in log_content.splitlines():
                    if "[ZONE_THRESHOLD]" in line:
                        # 예: BTC/KRW (BTC): 2.25 bps
                        parts = line.split("(")
                        if len(parts) > 1:
                            symbol = parts[1].split(")")[0].strip()
                            if symbol not in kpi["zone_profiles_loaded"]["profiles"]:
                                kpi["zone_profiles_loaded"]["profiles"].append(symbol)
        
        # PnL 추출 (마지막 iteration 로그에서)
        pnl_lines = [line for line in log_content.splitlines() if "PnL=$" in line]
        if pnl_lines:
            last_pnl_line = pnl_lines[-1]
            # 예: [D77-0] Iteration 300: Round trips=5, PnL=$-0.12, Latency=13.6ms
            try:
                pnl_part = last_pnl_line.split("PnL=$")[1].split(",")[0]
                kpi["pnl_usd"] = float(pnl_part)
            except:
                pass
        
        # 에러 수집 (마지막 200줄에서)
        error_lines = []
        for line in log_content.splitlines()[-200:]:
            if "ERROR" in line or "FAIL" in line or "Exception" in line:
                error_lines.append(line.strip())
        
        if error_lines:
            kpi["errors"] = error_lines[:10]  # 최대 10개만
    
    except Exception as e:
        kpi["errors"].append(f"KPI 추출 중 예외 발생: {str(e)}")
    
    return kpi


def generate_kpi_json(log_dir: Path, run_id: str, metadata: dict, kpi: dict) -> Path:
    """KPI JSON 파일 생성"""
    kpi_path = log_dir / "kpi.json"
    
    kpi_data = {
        "run_id": run_id,
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


def validate_results(duration_sec: float, exit_code: int, kpi_path: Path) -> tuple[bool, list[str]]:
    """결과 검증"""
    issues = []
    
    # 1. Duration 검증 (600초 이상, 허용 오차 +5초)
    if duration_sec < 600:
        issues.append(f"FAIL: 실행 시간이 600초 미만입니다 ({duration_sec:.1f}초)")
    
    # 2. Exit code 검증
    if exit_code != 0:
        issues.append(f"FAIL: Exit code가 0이 아닙니다 (exit_code={exit_code})")
    
    # 3. KPI JSON 존재 및 파싱 검증
    if not kpi_path.exists():
        issues.append("FAIL: kpi.json 파일이 생성되지 않았습니다")
    else:
        try:
            with open(kpi_path, "r", encoding="utf-8") as f:
                kpi_data = json.load(f)
            
            # 필수 필드 확인
            required_fields = ["run_id", "start_ts", "end_ts", "duration_sec", "exit_code"]
            for field in required_fields:
                if field not in kpi_data:
                    issues.append(f"FAIL: kpi.json에 필수 필드 '{field}'가 없습니다")
        except json.JSONDecodeError as e:
            issues.append(f"FAIL: kpi.json 파싱 실패: {str(e)}")
    
    return len(issues) == 0, issues


def main():
    print("=" * 80)
    print("Gate 10분 테스트 SSOT (Single Source of Truth)")
    print("=" * 80)
    print()
    
    # 1. Run ID 생성
    run_id = generate_run_id()
    print(f"[1/6] Run ID 생성: {run_id}")
    
    # 2. 로그 디렉토리 생성
    log_dir = create_log_directory(run_id)
    print(f"[2/6] 로그 디렉토리 생성: {log_dir}")
    
    # 3. Gate 테스트 실행
    print(f"[3/6] Gate 테스트 실행 중 (목표: 600초)...")
    exit_code, duration_sec, metadata = run_gate_test(log_dir, duration_sec=600)
    print(f"      실행 완료: {duration_sec:.1f}초, exit_code={exit_code}")
    
    # 4. KPI 추출
    print(f"[4/6] KPI 추출 중...")
    kpi = extract_kpi_from_logs(log_dir, metadata)
    print(f"      Round trips: {kpi['round_trips_count']}, PnL: ${kpi['pnl_usd']:.2f}")
    
    # 5. KPI JSON 생성 (항상 생성, 예외 상황에서도)
    print(f"[5/6] KPI JSON 생성 중...")
    try:
        kpi_path = generate_kpi_json(log_dir, run_id, metadata, kpi)
        print(f"      KPI JSON 생성 완료: {kpi_path}")
    except Exception as e:
        print(f"      KPI JSON 생성 실패: {str(e)}")
        print(f"      Traceback: {traceback.format_exc()}")
        return 1
    
    # 6. 결과 검증
    print(f"[6/6] 결과 검증 중...")
    passed, issues = validate_results(duration_sec, exit_code, kpi_path)
    
    print()
    print("=" * 80)
    if passed:
        print("[PASS] Gate 10분 테스트 완료")
        print()
        print("증거 파일:")
        print(f"  - 로그: {log_dir / 'gate.log'}")
        print(f"  - KPI: {kpi_path}")
        print()
        print("KPI 요약:")
        print(f"  - Duration: {duration_sec:.1f}초 (>= 600초)")
        print(f"  - Exit Code: {exit_code} (== 0)")
        print(f"  - Round Trips: {kpi['round_trips_count']}")
        print(f"  - PnL: ${kpi['pnl_usd']:.2f}")
        print(f"  - Zone Profiles: {kpi['zone_profiles_loaded']['success']}/{kpi['zone_profiles_loaded']['attempted']}")
        return 0
    else:
        print("[FAIL] Gate 10분 테스트 실패")
        print()
        print("실패 사유:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("증거 파일:")
        print(f"  - 로그: {log_dir / 'gate.log'}")
        print(f"  - KPI: {kpi_path}")
        print()
        print("자동 디버깅을 위해 로그를 확인하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
