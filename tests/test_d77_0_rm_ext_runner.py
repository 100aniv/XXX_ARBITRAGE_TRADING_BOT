#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-0-RM-EXT Runner 테스트

run_d77_0_rm_ext.py 래퍼 스크립트의 동작을 검증:
- CLI 인자 파싱
- Preset 시나리오 설정
- 명령어 구성
- Dry-run 모드
"""

import subprocess
import sys
from pathlib import Path

import pytest

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
WRAPPER_SCRIPT = PROJECT_ROOT / "scripts" / "run_d77_0_rm_ext.py"


class TestD77RMExtRunner:
    """D77-0-RM-EXT 래퍼 스크립트 테스트"""
    
    def test_wrapper_script_exists(self):
        """래퍼 스크립트 파일이 존재하는지 확인"""
        assert WRAPPER_SCRIPT.exists(), f"Wrapper script not found: {WRAPPER_SCRIPT}"
    
    def test_smoke_scenario_dry_run(self):
        """Smoke 시나리오 dry-run 테스트"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "smoke",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Smoke scenario failed: {result.stderr}"
        assert "Universe: top20" in result.stdout
        assert "Duration: 3 minutes" in result.stdout
        assert "--data-source real" in result.stdout
        assert "[DRY-RUN]" in result.stdout
    
    def test_primary_scenario_dry_run(self):
        """Primary 시나리오 dry-run 테스트"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "primary",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Primary scenario failed: {result.stderr}"
        assert "Universe: top20" in result.stdout
        assert "Duration: 60 minutes" in result.stdout
        assert "--data-source real" in result.stdout
        assert "[DRY-RUN]" in result.stdout
    
    def test_extended_scenario_dry_run(self):
        """Extended 시나리오 dry-run 테스트"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "extended",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Extended scenario failed: {result.stderr}"
        assert "Universe: top50" in result.stdout
        assert "Duration: 60 minutes" in result.stdout
        assert "--data-source real" in result.stdout
        assert "[DRY-RUN]" in result.stdout
    
    def test_custom_scenario_dry_run(self):
        """Custom 시나리오 dry-run 테스트"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "custom",
            "--universe", "top20",
            "--duration-minutes", "120",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Custom scenario failed: {result.stderr}"
        assert "Universe: top20" in result.stdout
        assert "Duration: 120 minutes" in result.stdout
        assert "--data-source real" in result.stdout
        assert "[DRY-RUN]" in result.stdout
    
    def test_custom_scenario_missing_args(self):
        """Custom 시나리오에서 필수 인자 누락 시 에러"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "custom",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 1, "Custom scenario should fail without required args"
        assert "[ERROR]" in result.stdout
        assert "필수" in result.stdout or "required" in result.stdout.lower()
    
    def test_command_construction(self):
        """명령어 구성이 올바른지 확인"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "smoke",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 기대되는 명령어 요소들
        expected_elements = [
            "run_d77_0_topn_arbitrage_paper.py",
            "--universe top20",
            "--duration-minutes 3",
            "--data-source real",
            "--monitoring-enabled",
            "--kpi-output-path"
        ]
        
        for element in expected_elements:
            assert element in result.stdout, f"Missing command element: {element}"
    
    def test_log_directory_structure(self):
        """로그 디렉토리 구조가 올바른지 확인"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--scenario", "smoke",
            "--dry-run"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 로그 경로에 d77-0-rm-ext 포함 확인
        assert "logs/d77-0-rm-ext" in result.stdout or "logs\\d77-0-rm-ext" in result.stdout
        assert "run_" in result.stdout  # run_YYYYMMDD_HHMMSS 형식
        assert "smoke_3m_kpi.json" in result.stdout  # KPI 파일명
    
    def test_help_message(self):
        """--help 옵션 동작 확인"""
        cmd = [
            sys.executable,
            str(WRAPPER_SCRIPT),
            "--help"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0, "Help should exit with 0"
        assert "--scenario" in result.stdout
        assert "smoke" in result.stdout
        assert "primary" in result.stdout
        assert "extended" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
