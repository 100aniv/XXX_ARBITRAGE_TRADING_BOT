"""
D205-18-4-FIX-2: F5 SIGTERM Handler Smoke Test
"""
import signal
import pytest
from pathlib import Path

def test_f5_sigterm_handler_registration():
    """F5: SIGTERM Handler가 올바르게 등록되는지 검증"""
    from arbitrage.v2.core.orchestrator import PaperOrchestrator
    from arbitrage.v2.core.metrics import PaperMetrics
    from arbitrage.v2.core.monitor import EvidenceCollector
    from arbitrage.v2.harness.paper_runner import PaperRunnerConfig
    
    # Mock 객체
    config = PaperRunnerConfig(duration_minutes=1, db_mode="off")
    kpi = PaperMetrics()
    evidence_dir = Path("logs/evidence/test_f5_sigterm")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    collector = EvidenceCollector(str(evidence_dir), "test_f5")
    
    class MockSource:
        def generate(self, i):
            return None
    
    class MockExecutor:
        def execute(self, *args, **kwargs):
            return None
    
    class MockLedger:
        def get_counts(self):
            return {"orders": 0, "fills": 0, "trades": 0}
    
    # Orchestrator 생성 (signal handler 등록됨)
    orch = PaperOrchestrator(
        config=config,
        opportunity_source=MockSource(),
        executor=MockExecutor(),
        ledger_writer=MockLedger(),
        kpi=kpi,
        evidence_collector=collector,
        admin_control=None,
        run_id="test_f5"
    )
    
    # 검증
    assert hasattr(orch, "_sigterm_received"), "F5: _sigterm_received 플래그 존재"
    assert orch._sigterm_received == False, "F5: 초기값 False"
    
    # Signal handler 등록 확인
    sigterm_handler = signal.getsignal(signal.SIGTERM)
    sigint_handler = signal.getsignal(signal.SIGINT)
    
    assert sigterm_handler is not None, "F5: SIGTERM handler 등록"
    assert sigint_handler is not None, "F5: SIGINT handler 등록"
    assert callable(sigterm_handler), "F5: SIGTERM handler callable"
    
    print("F5 SIGTERM Handler Registration: PASS")


def test_f5_sigterm_flag_set():
    """F5: SIGTERM 시 _sigterm_received 플래그 설정 검증"""
    from arbitrage.v2.core.orchestrator import PaperOrchestrator
    from arbitrage.v2.core.metrics import PaperMetrics
    from arbitrage.v2.core.monitor import EvidenceCollector
    from arbitrage.v2.harness.paper_runner import PaperRunnerConfig
    
    config = PaperRunnerConfig(duration_minutes=1, db_mode="off")
    kpi = PaperMetrics()
    evidence_dir = Path("logs/evidence/test_f5_sigterm_flag")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    collector = EvidenceCollector(str(evidence_dir), "test_f5_flag")
    
    class MockSource:
        def generate(self, i):
            return None
    
    class MockExecutor:
        def execute(self, *args, **kwargs):
            return None
    
    class MockLedger:
        def get_counts(self):
            return {"orders": 0, "fills": 0, "trades": 0}
    
    orch = PaperOrchestrator(
        config=config,
        opportunity_source=MockSource(),
        executor=MockExecutor(),
        ledger_writer=MockLedger(),
        kpi=kpi,
        evidence_collector=collector,
        admin_control=None,
        run_id="test_f5_flag"
    )
    
    # 초기 상태
    assert orch._sigterm_received == False
    assert orch._stop_requested == False
    
    # Signal handler 수동 호출 (SIGTERM 시뮬레이션)
    handler = signal.getsignal(signal.SIGTERM)
    handler(signal.SIGTERM, None)
    
    # 플래그 확인
    assert orch._sigterm_received == True, "F5: SIGTERM 시 플래그 True"
    assert orch._stop_requested == True, "F5: SIGTERM 시 stop_requested도 True"
    
    print("F5 SIGTERM Flag Set: PASS")


if __name__ == "__main__":
    test_f5_sigterm_handler_registration()
    test_f5_sigterm_flag_set()
    print("All F5 tests PASSED")
