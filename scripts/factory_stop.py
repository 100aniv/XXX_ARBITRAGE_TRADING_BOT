#!/usr/bin/env python3
"""Factory Stop (안전 종료).

실행 중인 factory worker 컨테이너를 즉시 종료.
Docker 컨테이너 기반 + 로컬 프로세스 기반 양쪽 지원.

Usage:
    python3 scripts/factory_stop.py
    just factory_stop
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER_NAME_PREFIX = "arbitrage-factory-worker"


def stop_docker_containers() -> int:
    """factory worker Docker 컨테이너 중지."""
    stopped = 0
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME_PREFIX}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"[STOP] docker ps 실패: {result.stderr.strip()}")
            return 0

        containers = [c.strip() for c in result.stdout.strip().splitlines() if c.strip()]
        if not containers:
            print("[STOP] 실행 중인 factory worker 컨테이너 없음")
            return 0

        for name in containers:
            print(f"[STOP] 컨테이너 종료 중: {name}")
            stop_result = subprocess.run(
                ["docker", "stop", name, "--time", "10"],
                capture_output=True, text=True, timeout=30,
            )
            if stop_result.returncode == 0:
                print(f"[STOP] 컨테이너 종료 완료: {name}")
                stopped += 1
            else:
                print(f"[STOP] 컨테이너 종료 실패: {name} - {stop_result.stderr.strip()}")
    except FileNotFoundError:
        print("[STOP] docker CLI 없음 (Docker 미설치 또는 PATH 미등록)")
    except subprocess.TimeoutExpired:
        print("[STOP] docker 명령 타임아웃")
    return stopped


def stop_supervisor_process() -> int:
    """factory_supervisor.py 프로세스 종료 (로컬 모드)."""
    stopped = 0
    try:
        result = subprocess.run(
            ["pgrep", "-f", "factory_supervisor.py"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
        if not pids:
            print("[STOP] 실행 중인 factory_supervisor 프로세스 없음")
            return 0

        for pid in pids:
            print(f"[STOP] supervisor 프로세스 종료 중: PID {pid}")
            kill_result = subprocess.run(
                ["kill", "-TERM", pid],
                capture_output=True, text=True, timeout=5,
            )
            if kill_result.returncode == 0:
                print(f"[STOP] PID {pid} SIGTERM 전송 완료")
                stopped += 1
            else:
                print(f"[STOP] PID {pid} 종료 실패: {kill_result.stderr.strip()}")
    except FileNotFoundError:
        print("[STOP] pgrep 없음 (procps 미설치)")
    except subprocess.TimeoutExpired:
        print("[STOP] pgrep/kill 타임아웃")
    return stopped


def main() -> int:
    print("=" * 50)
    print("  FACTORY STOP (안전 종료)")
    print("=" * 50)

    docker_stopped = stop_docker_containers()
    proc_stopped = stop_supervisor_process()

    total = docker_stopped + proc_stopped
    if total > 0:
        print(f"\n[STOP] 총 {total}개 프로세스/컨테이너 종료 완료")
    else:
        print("\n[STOP] 종료할 대상 없음 (이미 중지 상태)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
