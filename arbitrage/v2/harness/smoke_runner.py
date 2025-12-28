"""
SmokeRunner - V2 Smoke Test Harness

Replaces script-centric experiments with engine-based validation.
"""

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import logging
from typing import Dict, List

from arbitrage.v2.core import (
    ArbitrageEngine,
    EngineConfig,
    OrderIntent,
    OrderSide,
    OrderType,
)
from arbitrage.v2.adapters import MockAdapter, UpbitAdapter


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SmokeConfig:
    """
    Configuration for smoke test.
    
    Attributes:
        output_dir: Directory to save evidence
        test_upbit: Whether to test Upbit adapter
        test_mock: Whether to test Mock adapter
        read_only: READ_ONLY flag (always True in V2)
    """
    output_dir: str
    test_upbit: bool = True
    test_mock: bool = True
    read_only: bool = True


class SmokeRunner:
    """
    V2 Smoke Test Runner.
    
    Purpose:
    - Validate Engine → OrderIntent → Adapter flow
    - Test payload translation (Upbit, Mock)
    - Collect evidence (JSON logs)
    - Permanently block real orders (READ_ONLY enforced)
    
    This replaces run_d107_smoke.py, run_v2_test.py, etc.
    """
    
    def __init__(self, config: SmokeConfig):
        """
        Initialize smoke runner.
        
        Args:
            config: Smoke test configuration
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.evidence = {
            "start_time": datetime.now().isoformat(),
            "config": {
                "test_upbit": config.test_upbit,
                "test_mock": config.test_mock,
                "read_only": config.read_only,
            },
            "test_results": [],
            "errors": [],
        }
        
        logger.info(f"[V2 Smoke] Initialized with output: {self.output_dir}")
    
    def run(self):
        """
        Run smoke tests.
        
        Test Cases:
        1. Mock Adapter - MARKET BUY
        2. Mock Adapter - MARKET SELL
        3. Upbit Adapter - MARKET BUY payload validation
        4. Upbit Adapter - MARKET SELL payload validation
        5. Engine integration
        """
        logger.info("[V2 Smoke] ========================================")
        logger.info("[V2 Smoke] V2 KICKOFF SMOKE TEST")
        logger.info("[V2 Smoke] ========================================")
        
        if not self.config.read_only:
            logger.error("[V2 Smoke] ❌ READ_ONLY=False is FORBIDDEN in V2")
            self.evidence["errors"].append("READ_ONLY=False attempted")
            self._save_evidence()
            raise ValueError("V2 smoke test requires READ_ONLY=True")
        
        if self.config.test_mock:
            self._test_mock_adapter()
        
        if self.config.test_upbit:
            self._test_upbit_adapter()
        
        self._test_engine_integration()
        
        self.evidence["end_time"] = datetime.now().isoformat()
        self.evidence["status"] = "PASS" if not self.evidence["errors"] else "FAIL"
        
        self._save_evidence()
        self._print_summary()
    
    def _test_mock_adapter(self):
        """Test MockAdapter"""
        logger.info("[V2 Smoke] Testing MockAdapter...")
        
        adapter = MockAdapter(exchange_name="mock")
        
        # Test 1: MARKET BUY
        try:
            intent = OrderIntent(
                exchange="mock",
                symbol="BTC/KRW",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quote_amount=5000.0
            )
            
            result = adapter.execute(intent)
            
            self.evidence["test_results"].append({
                "test": "mock_market_buy",
                "success": result.success,
                "order_id": result.order_id,
                "intent": repr(intent),
            })
            
            logger.info(f"[V2 Smoke] ✅ Mock MARKET BUY: {result.order_id}")
        
        except Exception as e:
            logger.error(f"[V2 Smoke] ❌ Mock MARKET BUY failed: {e}")
            self.evidence["errors"].append(f"mock_market_buy: {str(e)}")
        
        # Test 2: MARKET SELL
        try:
            intent = OrderIntent(
                exchange="mock",
                symbol="BTC/KRW",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                base_qty=0.001
            )
            
            result = adapter.execute(intent)
            
            self.evidence["test_results"].append({
                "test": "mock_market_sell",
                "success": result.success,
                "order_id": result.order_id,
                "intent": repr(intent),
            })
            
            logger.info(f"[V2 Smoke] ✅ Mock MARKET SELL: {result.order_id}")
        
        except Exception as e:
            logger.error(f"[V2 Smoke] ❌ Mock MARKET SELL failed: {e}")
            self.evidence["errors"].append(f"mock_market_sell: {str(e)}")
    
    def _test_upbit_adapter(self):
        """Test UpbitAdapter (payload validation only)"""
        logger.info("[V2 Smoke] Testing UpbitAdapter (READ_ONLY)...")
        
        adapter = UpbitAdapter(read_only=True)
        
        # Test 3: MARKET BUY payload
        try:
            intent = OrderIntent(
                exchange="upbit",
                symbol="BTC/KRW",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quote_amount=5000.0
            )
            
            payload = adapter.translate_intent(intent)
            
            assert "price" in payload, "Upbit MARKET BUY must have 'price'"
            assert "volume" not in payload, "Upbit MARKET BUY must NOT have 'volume'"
            assert payload["market"] == "KRW-BTC", "Symbol transformation failed"
            
            result = adapter.execute(intent)
            
            self.evidence["test_results"].append({
                "test": "upbit_market_buy_payload",
                "success": True,
                "payload": payload,
                "order_id": result.order_id,
                "intent": repr(intent),
            })
            
            logger.info(f"[V2 Smoke] ✅ Upbit MARKET BUY payload: {payload}")
        
        except Exception as e:
            logger.error(f"[V2 Smoke] ❌ Upbit MARKET BUY failed: {e}")
            self.evidence["errors"].append(f"upbit_market_buy: {str(e)}")
        
        # Test 4: MARKET SELL payload
        try:
            intent = OrderIntent(
                exchange="upbit",
                symbol="BTC/KRW",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                base_qty=0.001
            )
            
            payload = adapter.translate_intent(intent)
            
            assert "volume" in payload, "Upbit MARKET SELL must have 'volume'"
            assert "price" not in payload, "Upbit MARKET SELL must NOT have 'price'"
            assert payload["market"] == "KRW-BTC", "Symbol transformation failed"
            
            result = adapter.execute(intent)
            
            self.evidence["test_results"].append({
                "test": "upbit_market_sell_payload",
                "success": True,
                "payload": payload,
                "order_id": result.order_id,
                "intent": repr(intent),
            })
            
            logger.info(f"[V2 Smoke] ✅ Upbit MARKET SELL payload: {payload}")
        
        except Exception as e:
            logger.error(f"[V2 Smoke] ❌ Upbit MARKET SELL failed: {e}")
            self.evidence["errors"].append(f"upbit_market_sell: {str(e)}")
    
    def _test_engine_integration(self):
        """Test Engine integration"""
        logger.info("[V2 Smoke] Testing Engine integration...")
        
        try:
            adapters = {
                "mock": MockAdapter(),
                "upbit": UpbitAdapter(read_only=True),
            }
            
            config = EngineConfig(
                min_spread_bps=30.0,
                max_position_usd=1000.0,
                enable_execution=False,
                adapters=adapters
            )
            
            engine = ArbitrageEngine(config)
            
            results = engine.run_cycle()
            
            self.evidence["test_results"].append({
                "test": "engine_integration",
                "success": True,
                "num_results": len(results),
            })
            
            logger.info(f"[V2 Smoke] ✅ Engine integration: {len(results)} results")
        
        except Exception as e:
            logger.error(f"[V2 Smoke] ❌ Engine integration failed: {e}")
            self.evidence["errors"].append(f"engine_integration: {str(e)}")
    
    def _save_evidence(self):
        """Save evidence to JSON"""
        evidence_path = self.output_dir / "smoke_evidence.json"
        with open(evidence_path, 'w') as f:
            json.dump(self.evidence, f, indent=2)
        
        logger.info(f"[V2 Smoke] Evidence saved: {evidence_path}")
    
    def _print_summary(self):
        """Print test summary"""
        logger.info("[V2 Smoke] ========================================")
        logger.info("[V2 Smoke] SMOKE TEST SUMMARY")
        logger.info("[V2 Smoke] ========================================")
        
        total_tests = len(self.evidence["test_results"])
        passed = sum(1 for t in self.evidence["test_results"] if t.get("success"))
        failed = len(self.evidence["errors"])
        
        logger.info(f"[V2 Smoke] Total Tests: {total_tests}")
        logger.info(f"[V2 Smoke] Passed: {passed}")
        logger.info(f"[V2 Smoke] Failed: {failed}")
        
        if failed > 0:
            logger.error("[V2 Smoke] ❌ SMOKE TEST FAILED")
            for error in self.evidence["errors"]:
                logger.error(f"[V2 Smoke]   - {error}")
        else:
            logger.info("[V2 Smoke] ✅ SMOKE TEST PASSED")
        
        logger.info(f"[V2 Smoke] Evidence: {self.output_dir / 'smoke_evidence.json'}")
        logger.info("[V2 Smoke] ========================================")


def main():
    """Command-line entry point"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"logs/evidence/v2_smoke_{timestamp}"
    
    config = SmokeConfig(
        output_dir=output_dir,
        test_upbit=True,
        test_mock=True,
        read_only=True
    )
    
    runner = SmokeRunner(config)
    runner.run()


if __name__ == '__main__':
    main()
