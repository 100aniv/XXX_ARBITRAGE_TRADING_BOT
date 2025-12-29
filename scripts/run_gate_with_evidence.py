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
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.evidence_pack import EvidencePacker


def run_gate_with_evidence(gate_name: str):
    """Gate 실행 + Evidence 생성"""
    
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
            "-m", "not live_api and not fx_api",
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
    
    print(f"[GATE] Running: {gate_name}")
    print(f"[GATE] Command: {cmd_str}")
    
    # Gate 실행 (stdout/stderr 캡처, 인코딩 명시)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # 인코딩 에러 무시
            cwd=Path.cwd(),
            timeout=300  # 5분 타임아웃
        )
        
        # gate.log에 출력 저장
        gate_log_path = packer.gate_log_path
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
        
        # 결과 판정
        if result.returncode == 0:
            status = "PASS"
            print(f"[OK] Gate {gate_name}: PASS")
        else:
            status = "FAIL"
            print(f"[FAIL] Gate {gate_name}: FAIL")
        
        # Evidence 기록
        packer.add_gate_result(
            gate_name,
            status,
            f"Exit code: {result.returncode}"
        )
        
        # Evidence 완료
        packer.finish(status=status)
        
        print(f"\n[Evidence] Path: {packer.evidence_dir}")
        print(f"[Evidence] Files: manifest.json, gate.log, git_info.json, cmd_history.txt")
        
        return result.returncode
    
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
