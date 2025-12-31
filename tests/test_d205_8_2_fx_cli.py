"""
D205-8-2: FX CLI Injection Test (회귀 방지)

AC-1: CLI --fx-krw-per-usdt 1300 → decisions.ndjson에 1300.0 기록
AC-2: 회귀 방지 자동 검증

SSOT: D_ROADMAP.md → D205-8-2
"""

import json
import pytest
from pathlib import Path
from scripts.run_d205_5_record_replay import main


class TestFxCliInjection:
    """FX CLI 주입 검증 테스트"""
    
    def test_fx_cli_replay_injection(self, tmp_path):
        """
        AC-1: CLI --fx-krw-per-usdt 1300 → decisions.ndjson에 1300.0 기록
        
        검증:
        1. CLI replay 실행 (fx=1300)
        2. decisions.ndjson에 fx_krw_per_usdt_used == 1300.0
        3. quote_mode에 "@1300.0" 포함
        
        회귀 방지: dd61f84에서 fx 전달 누락 버그 재발 방지
        """
        # 최소 market.ndjson 생성 (1 tick, no network)
        market_file = tmp_path / "market.ndjson"
        market_data = {
            "timestamp": "2025-12-31T12:00:00",
            "symbol": "BTC/KRW",
            "upbit_bid": 100000000.0,
            "upbit_ask": 100050000.0,
            "binance_bid": 69000.0,
            "binance_ask": 70000.0,
            "upbit_quote": "KRW",
            "binance_quote": "USDT",
        }
        market_file.write_text(json.dumps(market_data) + "\n", encoding="utf-8")
        
        out_dir = tmp_path / "out"
        
        # CLI replay 실행 (fx=1300)
        main(argv=[
            "--mode", "replay",
            "--input-file", str(market_file),
            "--out-evidence-dir", str(out_dir),
            "--fx-krw-per-usdt", "1300",
        ])
        
        # 검증: decisions.ndjson 존재
        decisions_file = out_dir / "decisions.ndjson"
        assert decisions_file.exists(), "decisions.ndjson not created"
        
        # 검증: fx=1300 기록
        decision_lines = decisions_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(decision_lines) >= 1, "No decisions recorded"
        
        decision = json.loads(decision_lines[0])
        
        # AC-1: fx_krw_per_usdt_used == 1300.0
        assert "fx_krw_per_usdt_used" in decision, "fx_krw_per_usdt_used field missing"
        assert decision["fx_krw_per_usdt_used"] == 1300.0, (
            f"Expected fx=1300.0, got {decision['fx_krw_per_usdt_used']} "
            "(FX CLI plumbing broken, check main() → RecordReplayRunner)"
        )
        
        # AC-1: quote_mode에 "@1300.0" 포함
        assert "quote_mode" in decision, "quote_mode field missing"
        assert "@1300.0" in decision["quote_mode"], (
            f"Expected '@1300.0' in quote_mode, got {decision['quote_mode']}"
        )
    
    def test_fx_cli_default_value(self, tmp_path):
        """
        FX CLI 기본값 검증 (--fx-krw-per-usdt 생략 시)
        
        검증: 기본값 1450.0 사용
        """
        # market.ndjson 생성
        market_file = tmp_path / "market.ndjson"
        market_data = {
            "timestamp": "2025-12-31T12:00:00",
            "symbol": "BTC/KRW",
            "upbit_bid": 100000000.0,
            "upbit_ask": 100050000.0,
            "binance_bid": 69000.0,
            "binance_ask": 70000.0,
            "upbit_quote": "KRW",
            "binance_quote": "USDT",
        }
        market_file.write_text(json.dumps(market_data) + "\n", encoding="utf-8")
        
        out_dir = tmp_path / "out_default"
        
        # CLI replay 실행 (fx 생략)
        main(argv=[
            "--mode", "replay",
            "--input-file", str(market_file),
            "--out-evidence-dir", str(out_dir),
        ])
        
        # 검증: 기본값 1450.0
        decisions_file = out_dir / "decisions.ndjson"
        assert decisions_file.exists()
        
        decision = json.loads(decisions_file.read_text(encoding="utf-8").strip().split("\n")[0])
        assert decision["fx_krw_per_usdt_used"] == 1450.0, (
            f"Expected default fx=1450.0, got {decision['fx_krw_per_usdt_used']}"
        )
