#!/usr/bin/env python3
"""
Gate 실행 + Evidence 자동 생성

Usage:
    python scripts/run_gate_with_evidence.py doctor
    python scripts/run_gate_with_evidence.py fast
    python scripts/run_gate_with_evidence.py regression
"""

import sys
import subprocess
import os
import re
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.evidence_pack import EvidencePacker


def run_gate_with_evidence(gate_name: str):
    """Gate 실행 + Evidence 생성"""
    if not os.getenv("BOOTSTRAP_FLAG"):
        print("[BOOTSTRAP GUARD] FAIL: BOOTSTRAP_FLAG missing. Run bootstrap_runtime_env.ps1 first.")
        sys.exit(1)
    
    # Evidence 초기화
    packer = EvidencePacker(
        d_number=f"gate_{gate_name}",
        task_name=f"Gate: {gate_name}"
    )
    packer.start()
    
    # Gate 명령 정의
    gate_commands = {
        "doctor": [
            sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"
        ],
        "fast": [
            sys.executable, "-m", "pytest", 
            "-m", "not optional_ml and not optional_live and not live_api and not fx_api",
            "-x", "--tb=short", "-v"
        ],
        "regression": [
            sys.executable, "-m", "pytest",
            "-m", "not optional_ml and not optional_live and not live_api and not fx_api",
            "--tb=short", "-v"
        ]
    }
    
    if gate_name not in gate_commands:
        print(f"❌ Unknown gate: {gate_name}")
        print(f"Available gates: {list(gate_commands.keys())}")
        sys.exit(1)
    
    cmd = gate_commands[gate_name]
    
    # 명령 기록
    cmd_str = ' '.join(cmd)
    packer.add_command(cmd_str, "Gate execution")

    preflight_checks = [
        (
            "check_no_duplicate_pnl",
            [sys.executable, "scripts/check_no_duplicate_pnl.py"],
        ),
        (
            "check_engine_centricity",
            [sys.executable, "scripts/check_engine_centricity.py"],
        ),
    ]
    for check_name, check_cmd in preflight_checks:
        packer.add_command(' '.join(check_cmd), f"Preflight: {check_name}")
    
    print(f"[GATE] Running: {gate_name}")
    print(f"[GATE] Command: {cmd_str}")
    
    # Gate 실행 (stdout/stderr 캡처, 인코딩 명시)
    try:
        env = os.environ.copy()
        env["GATE_NO_SKIP"] = "1"

        gate_log_path = packer.gate_log_path
        for check_name, check_cmd in preflight_checks:
            check_result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=Path.cwd(),
                timeout=120,
                env=env
            )

            with open(gate_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Preflight: {check_name}\n")
                f.write(f"Command: {' '.join(check_cmd)}\n")
                f.write(f"Exit Code: {check_result.returncode}\n")
                f.write(f"{'='*80}\n\n")
                f.write("=== STDOUT ===\n")
                f.write(check_result.stdout)
                f.write("\n\n=== STDERR ===\n")
                f.write(check_result.stderr)
                f.write("\n\n")

            if check_result.returncode != 0:
                status = "FAIL"
                exit_code = 1
                print(f"[FAIL] Preflight {check_name}: FAIL")
                packer.add_gate_result(
                    gate_name,
                    status,
                    f"Preflight failed: {check_name} (exit_code={check_result.returncode})"
                )
                packer.finish(status=status)
                print(f"\n[Evidence] Path: {packer.evidence_dir}")
                print(f"[Evidence] Files: manifest.json, gate.log, git_info.json, cmd_history.txt")
                return exit_code

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # 인코딩 에러 무시
            cwd=Path.cwd(),
            timeout=300,  # 5분 타임아웃
            env=env
        )
        
        # gate.log에 출력 저장
        with open(gate_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Gate: {gate_name}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Exit Code: {result.returncode}\n")
            f.write(f"{'='*80}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n\n=== STDERR ===\n")
            f.write(result.stderr)
            f.write("\n\n")
        
        combined_output = f"{result.stdout}\n{result.stderr}"
        skip_match = re.findall(r"(\d+)\s+skipped", combined_output)
        warn_match = re.findall(r"(\d+)\s+warnings?", combined_output)
        skipped_count = sum(int(value) for value in skip_match) if skip_match else 0
        warnings_count = sum(int(value) for value in warn_match) if warn_match else 0

        # 결과 판정 (SKIP/WARN=FAIL)
        exit_code = result.returncode
        if skipped_count > 0 or warnings_count > 0:
            status = "FAIL"
            exit_code = 1
            print(
                f"[FAIL] Gate {gate_name}: SKIP/WARN=FAIL "
                f"(skipped={skipped_count}, warnings={warnings_count})"
            )
        elif result.returncode == 0:
            status = "PASS"
            print(f"[OK] Gate {gate_name}: PASS")
        else:
            status = "FAIL"
            print(f"[FAIL] Gate {gate_name}: FAIL")
        
        # Evidence 기록
        packer.add_gate_result(
            gate_name,
            status,
            (
                f"Exit code: {exit_code} | skipped={skipped_count} | "
                f"warnings={warnings_count}"
            )
        )
        
        # Evidence 완료
        packer.finish(status=status)
        
        print(f"\n[Evidence] Path: {packer.evidence_dir}")
        print(f"[Evidence] Files: manifest.json, gate.log, git_info.json, cmd_history.txt")
        
        return exit_code
    
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] Gate {gate_name}: Exceeded 5 minutes")
        packer.add_error(f"Gate {gate_name} timeout (5min)")
        packer.finish(status="TIMEOUT")
        return 1
    
    except Exception as e:
        print(f"[ERROR] Gate {gate_name}: {e}")
        packer.add_error(f"Gate {gate_name} error: {e}")
        packer.finish(status="ERROR")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_gate_with_evidence.py <gate_name>")
        print("Gates: doctor, fast, regression")
        sys.exit(1)
    
    gate = sys.argv[1]
    exit_code = run_gate_with_evidence(gate)
    sys.exit(exit_code)
