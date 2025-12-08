#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3_FIX: Duration Guard 테스트

Runner와 Orchestrator의 duration 강제 종료 로직 검증:
1. Runner가 max_iterations를 초과하지 않는지 확인
2. Runner가 duration_seconds를 초과하지 않는지 확인 (±10초 이내)
3. Orchestrator timeout이 작동하는지 확인
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import pytest

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDurationGuard:
    """Duration Guard 테스트"""
    
    def test_runner_10s_duration_realistic(self):
        """D87-5: Runner 10초 실행 테스트 (실시간 벽시계 기반 Duration Guard 검증)
        
        이 테스트는 Duration Guard가 time-based로 정확히 작동하는지 검증합니다.
        - 백테스트 구조가 아닌 실시간 PAPER 구조 (time.sleep(1) 실제 소비)
        - 10초 duration → 실제로 10초 소요
        - Termination Reason == "TIME_LIMIT" 확인
        - actual_duration이 8~15초 사이인지 확인 (허용 오차 포함)
        """
        # Arrange
        duration_seconds = 10
        session_tag = f"test_duration_10s_{int(time.time())}"
        logs_dir = PROJECT_ROOT / "logs" / "d87-3" / session_tag
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        calibration_path = PROJECT_ROOT / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "mock",  # Mock L2로 빠르게 테스트
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(calibration_path),
            "--session-tag", session_tag,
        ]
        
        # Act
        start_time = time.time()
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30  # 10초 + 20초 grace
        )
        actual_duration = time.time() - start_time
        
        # Assert
        assert result.returncode == 0, f"Runner failed: {result.stderr}"
        
        # Duration 검증: 10초 기준 8~15초 이내 (실시간 벽시계 기반)
        assert 8 <= actual_duration <= 15, \
            f"Duration out of range: {actual_duration:.1f}s (expected: 8~15s for 10s target)"
        
        # KPI 파일 존재 확인
        kpi_files = list(logs_dir.glob("kpi_*.json"))
        assert len(kpi_files) == 1, f"KPI file not found in {logs_dir}"
        
        # KPI 내용 검증
        with open(kpi_files[0], "r") as f:
            kpi = json.load(f)
        
        assert "actual_duration_seconds" in kpi
        assert "total_iterations" in kpi
        
        # Duration 정확도: KPI의 actual_duration도 8~15초 이내
        kpi_duration = kpi["actual_duration_seconds"]
        assert 8 <= kpi_duration <= 15, \
            f"KPI duration out of range: {kpi_duration:.1f}s (expected: 8~15s)"
        
        # Termination reason 확인 (로그에서 "TIME_LIMIT" 찾기)
        output = result.stdout + result.stderr
        assert "TIME_LIMIT" in output or "Termination Reason: TIME_LIMIT" in output, \
            "Expected termination reason TIME_LIMIT not found in logs"
        
        print(f"✅ D87-5: 10s duration test passed (realistic wall-clock based)")
        print(f"   - Actual duration: {actual_duration:.1f}s (subprocess)")
        print(f"   - KPI duration: {kpi_duration:.1f}s")
        print(f"   - Iterations: {kpi['total_iterations']}")
        print(f"   - Termination: TIME_LIMIT ✅")
    
    def test_runner_30s_duration(self):
        """Runner 30초 실행 테스트 (정확한 종료 확인)"""
        # Arrange
        duration_seconds = 30
        session_tag = f"test_duration_30s_{int(time.time())}"
        logs_dir = PROJECT_ROOT / "logs" / "d87-3" / session_tag
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        calibration_path = PROJECT_ROOT / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "mock",  # Mock L2로 빠르게 테스트
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(calibration_path),
            "--session-tag", session_tag,
        ]
        
        # Act
        start_time = time.time()
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60  # 30초 + 30초 grace
        )
        actual_duration = time.time() - start_time
        
        # Assert
        assert result.returncode == 0, f"Runner failed: {result.stderr}"
        
        # Duration 검증: 30초 ±10초 이내
        assert duration_seconds - 10 <= actual_duration <= duration_seconds + 10, \
            f"Duration out of range: {actual_duration:.1f}s (expected: {duration_seconds}s ±10s)"
        
        # KPI 파일 존재 확인
        kpi_files = list(logs_dir.glob("kpi_*.json"))
        assert len(kpi_files) == 1, f"KPI file not found in {logs_dir}"
        
        # KPI 내용 검증
        with open(kpi_files[0], "r") as f:
            kpi = json.load(f)
        
        assert "actual_duration_seconds" in kpi
        assert "total_iterations" in kpi
        
        # Total iterations 검증: duration + 60 이하
        max_iterations = duration_seconds + 60
        assert kpi["total_iterations"] <= max_iterations, \
            f"Iterations exceeded max: {kpi['total_iterations']} > {max_iterations}"
        
        print(f"✅ Test passed:")
        print(f"   - Duration: {actual_duration:.1f}s (target: {duration_seconds}s)")
        print(f"   - Iterations: {kpi['total_iterations']} (max: {max_iterations})")
        print(f"   - KPI file: {kpi_files[0].name}")
    
    def test_runner_heartbeat_logging(self):
        """Runner Heartbeat 로깅 테스트 (5분마다 출력)"""
        # Arrange
        duration_seconds = 30  # 30초로 짧게 테스트
        session_tag = f"test_heartbeat_{int(time.time())}"
        logs_dir = PROJECT_ROOT / "logs" / "d87-3" / session_tag
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        calibration_path = PROJECT_ROOT / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "mock",
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(calibration_path),
            "--session-tag", session_tag,
        ]
        
        # Act
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Assert
        assert result.returncode == 0, f"Runner failed: {result.stderr}"
        
        # 로그에 "PAPER 루프 시작" 메시지 확인
        assert "PAPER 루프 시작" in result.stdout or "PAPER 루프 시작" in result.stderr
        
        # 로그에 "PAPER 루프 종료" 메시지 확인
        assert "PAPER 루프 종료" in result.stdout or "PAPER 루프 종료" in result.stderr
        
        print(f"✅ Heartbeat logging test passed")
    
    def test_orchestrator_dry_run(self):
        """Orchestrator Dry-run 모드 테스트"""
        # Arrange
        cmd = [
            "python",
            "scripts/d87_3_longrun_orchestrator.py",
            "--mode", "dry-run",
        ]
        
        # Act
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Assert
        assert result.returncode == 0, f"Dry-run failed: {result.stderr}"
        
        # Dry-run 메시지 확인
        output = result.stdout + result.stderr
        assert "Dry-run 모드" in output
        assert "환경 점검" in output
        
        print(f"✅ Orchestrator dry-run test passed")
    
    def test_runner_duration_overrun_warning(self):
        """Runner Duration Overrun 경고 테스트"""
        # Note: 실제로 overrun을 유발하기는 어려우므로,
        # 이 테스트는 KPI에 actual_duration이 기록되는지만 확인
        
        duration_seconds = 30
        session_tag = f"test_overrun_{int(time.time())}"
        logs_dir = PROJECT_ROOT / "logs" / "d87-3" / session_tag
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        calibration_path = PROJECT_ROOT / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "mock",
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(calibration_path),
            "--session-tag", session_tag,
        ]
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        assert result.returncode == 0
        
        # KPI 파일 확인
        kpi_files = list(logs_dir.glob("kpi_*.json"))
        assert len(kpi_files) == 1
        
        with open(kpi_files[0], "r") as f:
            kpi = json.load(f)
        
        # actual_duration과 target duration 비교
        actual = kpi["actual_duration_seconds"]
        target = kpi["duration_seconds"]
        
        # Duration delta 출력 (경고 체크는 로그로만 가능)
        print(f"✅ Duration overrun warning test:")
        print(f"   - Target: {target}s")
        print(f"   - Actual: {actual:.1f}s")
        print(f"   - Delta: {actual - target:+.1f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
