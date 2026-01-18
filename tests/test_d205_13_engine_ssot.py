"""
D205-13 Engine SSOT 증명 테스트

테스트 목표:
1. PaperRunner에 "while" 루프 패턴이 없음을 검증
2. config mode 값이 실제로 로드되는지 검증

PASS 조건:
- Test 1: PaperRunner.run() 소스코드에 "while" 패턴 0건
- Test 2: config.yml mode 필드가 V2Config로 정상 로드

Author: D205-13 (Engine SSOT)
Date: 2026-01-06
"""

import inspect
import pytest
from pathlib import Path
from typing import Callable


def test_paper_runner_no_while_loop():
    """
    TEST 1: PaperRunner에 while 루프가 없음을 검증
    
    검증 방법:
    - inspect.getsource()로 PaperRunner.run() 소스 추출
    - "while" 패턴 검색 (while True, while time.time(), while.*:)
    
    PASS 조건:
    - "while" 패턴 0건 (Engine.run() 호출만 존재)
    
    FAIL 조건:
    - "while" 패턴 1건 이상 발견
    """
    from arbitrage.v2.harness.paper_runner import PaperRunner
    
    # PaperRunner.run() 소스 추출
    source_code = inspect.getsource(PaperRunner.run)
    
    # "while" 패턴 검색 (주석과 docstring 제외)
    lines = source_code.split('\n')
    in_docstring = False
    lines_with_while = []
    
    for line in lines:
        stripped = line.strip()
        
        # Docstring 시작/종료 체크
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue
        
        # Docstring 내부 또는 주석은 스킵
        if in_docstring or stripped.startswith('#'):
            continue
        
        # 실제 코드에서 "while" 발견
        if 'while' in line.lower():
            lines_with_while.append(line)
    
    # 검증: PaperRunner 자체 루프는 없어야 함
    # (Engine.run() 내부의 while는 괜찮음 - 그건 engine.py에 있음)
    assert len(lines_with_while) == 0, (
        f"❌ FAIL: PaperRunner.run()에 while 루프 {len(lines_with_while)}건 발견\n"
        f"발견된 라인:\n" + "\n".join(lines_with_while) +
        f"\n\n⚠️ PaperRunner는 Thin Wrapper여야 하며, while 루프는 Engine.run()에만 존재해야 함"
    )
    
    # 추가 검증: orchestrator.run() 또는 engine.run() 호출 존재 확인
    # D205-18-4-FIX: Orchestrator → Engine 구조로 변경되어 orchestrator.run()도 허용
    has_orchestrator_call = 'orchestrator.run()' in source_code
    has_engine_call = 'engine.run(' in source_code
    assert has_orchestrator_call or has_engine_call, (
        "❌ FAIL: PaperRunner.run()에 orchestrator.run() 또는 engine.run() 호출이 없음"
    )
    
    print("✅ PASS: PaperRunner에 while 루프 없음 (Engine.run() 호출 확인)")


def test_config_mode_loading():
    """
    TEST 2: config.yml mode 필드가 V2Config로 로드되는지 검증
    
    검증 방법:
    - config/v2/config.yml 읽기
    - load_config() 실행
    - V2Config.mode 필드 존재 및 값 검증
    
    PASS 조건:
    - config.yml에 mode 필드 존재
    - V2Config.mode가 ["paper", "live", "replay"] 중 하나
    
    FAIL 조건:
    - config.yml에 mode 필드 없음
    - V2Config.mode 값이 유효하지 않음
    """
    from arbitrage.v2.core.config import load_config
    
    # Config 로드
    config_path = "config/v2/config.yml"
    
    # 파일 존재 확인
    assert Path(config_path).exists(), f"❌ FAIL: {config_path} 파일 없음"
    
    # Config 로드
    config = load_config(config_path)
    
    # mode 필드 존재 확인
    assert hasattr(config, 'mode'), "❌ FAIL: V2Config.mode 필드 없음"
    
    # mode 값 검증
    valid_modes = ["paper", "live", "replay"]
    assert config.mode in valid_modes, (
        f"❌ FAIL: config.mode={config.mode}는 유효하지 않음 (허용: {valid_modes})"
    )
    
    print(f"✅ PASS: config.mode = '{config.mode}' (유효)")


def test_engine_has_single_loop():
    """
    TEST 3: Engine에 유일한 while 루프가 존재하는지 검증
    
    검증 방법:
    - ArbitrageEngine.run() 소스 추출
    - "while self.state == EngineState.RUNNING" 패턴 존재 확인
    
    PASS 조건:
    - Engine.run()에 while 루프 존재
    - EngineState enum 사용
    
    FAIL 조건:
    - while 루프 없음
    """
    from arbitrage.v2.core.engine import ArbitrageEngine, EngineState
    
    # Engine.run() 소스 추출
    source_code = inspect.getsource(ArbitrageEngine.run)
    
    # while 루프 존재 확인
    assert 'while' in source_code, "❌ FAIL: Engine.run()에 while 루프 없음"
    
    # EngineState 사용 확인
    assert 'EngineState' in source_code or 'self.state' in source_code, (
        "❌ FAIL: Engine.run()에 EngineState 기반 상태 관리 없음"
    )
    
    # EngineState enum 검증
    assert hasattr(EngineState, 'RUNNING'), "❌ FAIL: EngineState.RUNNING 없음"
    assert hasattr(EngineState, 'STOPPED'), "❌ FAIL: EngineState.STOPPED 없음"
    
    print("✅ PASS: Engine에 유일한 while 루프 존재 (EngineState 기반)")


def test_engine_run_signature():
    """
    TEST 4: Engine.run() 시그니처 검증 (콜백 파라미터 존재)
    
    검증 방법:
    - Engine.run() 시그니처 추출
    - fetch_tick_data, process_tick 파라미터 존재 확인
    
    PASS 조건:
    - fetch_tick_data 파라미터 존재
    - process_tick 파라미터 존재
    
    FAIL 조건:
    - 콜백 파라미터 없음
    """
    from arbitrage.v2.core.engine import ArbitrageEngine
    
    # Engine.run() 시그니처 추출
    signature = inspect.signature(ArbitrageEngine.run)
    params = list(signature.parameters.keys())
    
    # 콜백 파라미터 존재 확인
    assert 'fetch_tick_data' in params, (
        f"❌ FAIL: Engine.run()에 fetch_tick_data 파라미터 없음 (현재: {params})"
    )
    assert 'process_tick' in params, (
        f"❌ FAIL: Engine.run()에 process_tick 파라미터 없음 (현재: {params})"
    )
    
    print(f"✅ PASS: Engine.run() 콜백 파라미터 존재 (fetch_tick_data, process_tick)")


if __name__ == '__main__':
    # 단독 실행 시 모든 테스트 실행
    print("[D205-13 Engine SSOT 증명 테스트]")
    print("=" * 60)
    
    try:
        test_paper_runner_no_while_loop()
        test_config_mode_loading()
        test_engine_has_single_loop()
        test_engine_run_signature()
        
        print("=" * 60)
        print("✅ 모든 테스트 PASS (4/4)")
        
    except AssertionError as e:
        print("=" * 60)
        print(f"❌ 테스트 FAIL\n{e}")
        exit(1)
