"""
D205-5: Record/Replay 테스트

목표:
- MarketTick/DecisionRecord 스키마 검증
- Recorder 기록 검증
- ReplayRunner 재현성 검증
- Input hash 결정론 검증

네트워크 호출 없음 (Mock/Fixture 기반)
"""

import pytest
import json
import hashlib
from pathlib import Path
from datetime import datetime
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.replay.schemas import MarketTick, DecisionRecord
from arbitrage.v2.replay.recorder import MarketRecorder
from arbitrage.v2.replay.replay_runner import ReplayRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestMarketTick:
    """MarketTick 스키마 테스트"""
    
    def test_initialization(self):
        """MarketTick 초기화 검증"""
        tick = MarketTick(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            upbit_bid=100000.0,
            upbit_ask=100100.0,
            binance_bid=99900.0,
            binance_ask=100000.0,
        )
        
        assert tick.timestamp == "2025-12-31T00:00:00"
        assert tick.symbol == "BTC/KRW"
        assert tick.upbit_bid == 100000.0
        assert tick.upbit_ask == 100100.0
        assert tick.binance_bid == 99900.0
        assert tick.binance_ask == 100000.0
    
    def test_to_dict(self):
        """MarketTick to_dict 검증"""
        tick = MarketTick(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            upbit_bid=100000.0,
            upbit_ask=100100.0,
            binance_bid=99900.0,
            binance_ask=100000.0,
        )
        
        data = tick.to_dict()
        
        assert isinstance(data, dict)
        assert data["timestamp"] == "2025-12-31T00:00:00"
        assert data["symbol"] == "BTC/KRW"
        assert data["upbit_bid"] == 100000.0
    
    def test_from_dict(self):
        """MarketTick from_dict 검증"""
        data = {
            "timestamp": "2025-12-31T00:00:00",
            "symbol": "BTC/KRW",
            "upbit_bid": 100000.0,
            "upbit_ask": 100100.0,
            "binance_bid": 99900.0,
            "binance_ask": 100000.0,
        }
        
        tick = MarketTick.from_dict(data)
        
        assert tick.timestamp == "2025-12-31T00:00:00"
        assert tick.symbol == "BTC/KRW"
        assert tick.upbit_bid == 100000.0


class TestDecisionRecord:
    """DecisionRecord 스키마 테스트"""
    
    def test_initialization(self):
        """DecisionRecord 초기화 검증"""
        decision = DecisionRecord(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            spread_bps=100.0,
            break_even_bps=50.0,
            edge_bps=50.0,
            profitable=True,
            gate_reasons=[],
            latency_ms=10.5,
        )
        
        assert decision.timestamp == "2025-12-31T00:00:00"
        assert decision.symbol == "BTC/KRW"
        assert decision.spread_bps == 100.0
        assert decision.break_even_bps == 50.0
        assert decision.edge_bps == 50.0
        assert decision.profitable is True
        assert decision.gate_reasons == []
        assert decision.latency_ms == 10.5
    
    def test_to_dict(self):
        """DecisionRecord to_dict 검증"""
        decision = DecisionRecord(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            spread_bps=100.0,
            break_even_bps=50.0,
            edge_bps=50.0,
            profitable=True,
            gate_reasons=[],
            latency_ms=10.5,
        )
        
        data = decision.to_dict()
        
        assert isinstance(data, dict)
        assert data["timestamp"] == "2025-12-31T00:00:00"
        assert data["spread_bps"] == 100.0
        assert data["profitable"] is True
    
    def test_from_dict(self):
        """DecisionRecord from_dict 검증"""
        data = {
            "timestamp": "2025-12-31T00:00:00",
            "symbol": "BTC/KRW",
            "spread_bps": 100.0,
            "break_even_bps": 50.0,
            "edge_bps": 50.0,
            "profitable": True,
            "gate_reasons": [],
            "latency_ms": 10.5,
        }
        
        decision = DecisionRecord.from_dict(data)
        
        assert decision.timestamp == "2025-12-31T00:00:00"
        assert decision.profitable is True


class TestMarketRecorder:
    """MarketRecorder 테스트"""
    
    def test_record_single_tick(self):
        """단일 tick 기록 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "market.ndjson"
            recorder = MarketRecorder(output_path)
            
            tick = MarketTick(
                timestamp="2025-12-31T00:00:00",
                symbol="BTC/KRW",
                upbit_bid=100000.0,
                upbit_ask=100100.0,
                binance_bid=99900.0,
                binance_ask=100000.0,
            )
            
            recorder.record_tick(tick)
            recorder.close()
            
            # 파일 검증
            assert output_path.exists()
            
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                
                data = json.loads(lines[0])
                assert data["symbol"] == "BTC/KRW"
                assert data["upbit_bid"] == 100000.0
    
    def test_record_multiple_ticks(self):
        """다중 tick 기록 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "market.ndjson"
            recorder = MarketRecorder(output_path)
            
            for i in range(5):
                tick = MarketTick(
                    timestamp=f"2025-12-31T00:00:0{i}",
                    symbol="BTC/KRW",
                    upbit_bid=100000.0 + i,
                    upbit_ask=100100.0 + i,
                    binance_bid=99900.0 + i,
                    binance_ask=100000.0 + i,
                )
                recorder.record_tick(tick)
            
            recorder.close()
            
            # 파일 검증
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 5
                
                # 첫 번째 tick 검증
                data = json.loads(lines[0])
                assert data["upbit_bid"] == 100000.0
                
                # 마지막 tick 검증
                data = json.loads(lines[4])
                assert data["upbit_bid"] == 100004.0


class TestReplayRunner:
    """ReplayRunner 테스트"""
    
    def test_load_ticks(self):
        """Tick 로딩 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # market.ndjson 생성
            input_path = Path(tmpdir) / "market.ndjson"
            with open(input_path, "w") as f:
                for i in range(3):
                    tick = MarketTick(
                        timestamp=f"2025-12-31T00:00:0{i}",
                        symbol="BTC/KRW",
                        upbit_bid=100000.0,
                        upbit_ask=100100.0,
                        binance_bid=99900.0,
                        binance_ask=100000.0,
                    )
                    f.write(json.dumps(tick.to_dict()) + "\n")
            
            # ReplayRunner 실행
            output_dir = Path(tmpdir) / "replay_output"
            
            fee_a = FeeStructure("upbit", 5.0, 25.0)
            fee_b = FeeStructure("binance", 10.0, 25.0)
            fee_model = FeeModel(fee_a, fee_b)
            params = BreakEvenParams(fee_model, 10.0, 5.0)
            
            runner = ReplayRunner(input_path, output_dir, params)
            result = runner.run()
            
            assert result["status"] == "PASS"
            assert result["ticks_count"] == 3
            assert len(result["input_hash"]) == 16
    
    def test_input_hash_determinism(self):
        """Input hash 결정론 검증 (동일 입력 → 동일 hash)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # market.ndjson 생성
            input_path = Path(tmpdir) / "market.ndjson"
            content = ""
            for i in range(3):
                tick = MarketTick(
                    timestamp=f"2025-12-31T00:00:0{i}",
                    symbol="BTC/KRW",
                    upbit_bid=100000.0,
                    upbit_ask=100100.0,
                    binance_bid=99900.0,
                    binance_ask=100000.0,
                )
                content += json.dumps(tick.to_dict()) + "\n"
            
            with open(input_path, "w") as f:
                f.write(content)
            
            # ReplayRunner 2회 실행
            fee_a = FeeStructure("upbit", 5.0, 25.0)
            fee_b = FeeStructure("binance", 10.0, 25.0)
            fee_model = FeeModel(fee_a, fee_b)
            params = BreakEvenParams(fee_model, 10.0, 5.0)
            
            output_dir_1 = Path(tmpdir) / "replay_output_1"
            runner_1 = ReplayRunner(input_path, output_dir_1, params)
            result_1 = runner_1.run()
            
            output_dir_2 = Path(tmpdir) / "replay_output_2"
            runner_2 = ReplayRunner(input_path, output_dir_2, params)
            result_2 = runner_2.run()
            
            # 동일 hash 검증
            assert result_1["input_hash"] == result_2["input_hash"]
    
    def test_replay_output_files(self):
        """Replay 출력 파일 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # market.ndjson 생성 (spread > break_even)
            input_path = Path(tmpdir) / "market.ndjson"
            with open(input_path, "w") as f:
                tick = MarketTick(
                    timestamp="2025-12-31T00:00:00",
                    symbol="BTC/KRW",
                    upbit_bid=101000.0,  # 1% 높음
                    upbit_ask=101100.0,
                    binance_bid=99900.0,
                    binance_ask=100000.0,
                )
                f.write(json.dumps(tick.to_dict()) + "\n")
            
            # ReplayRunner 실행
            output_dir = Path(tmpdir) / "replay_output"
            
            fee_a = FeeStructure("upbit", 5.0, 25.0)
            fee_b = FeeStructure("binance", 10.0, 25.0)
            fee_model = FeeModel(fee_a, fee_b)
            params = BreakEvenParams(fee_model, 10.0, 5.0)
            
            runner = ReplayRunner(input_path, output_dir, params)
            result = runner.run()
            
            # 출력 파일 검증
            assert (output_dir / "decisions.ndjson").exists()
            assert (output_dir / "manifest.json").exists()
            
            # decisions.ndjson 검증
            with open(output_dir / "decisions.ndjson", "r") as f:
                lines = f.readlines()
                assert len(lines) >= 1  # 최소 1개 decision
                
                data = json.loads(lines[0])
                assert "spread_bps" in data
                assert "edge_bps" in data
                assert "profitable" in data


class TestRecordReplayIntegration:
    """Record → Replay 통합 테스트"""
    
    def test_record_then_replay(self):
        """Record → Replay 전체 플로우 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Record (fixture 데이터 생성)
            record_dir = Path(tmpdir) / "record"
            market_file = record_dir / "market.ndjson"
            record_dir.mkdir()
            
            recorder = MarketRecorder(market_file)
            for i in range(5):
                tick = MarketTick(
                    timestamp=f"2025-12-31T00:00:0{i}",
                    symbol="BTC/KRW",
                    upbit_bid=100000.0 + i * 100,
                    upbit_ask=100100.0 + i * 100,
                    binance_bid=99900.0 + i * 100,
                    binance_ask=100000.0 + i * 100,
                )
                recorder.record_tick(tick)
            recorder.close()
            
            # Step 2: Replay
            replay_dir = Path(tmpdir) / "replay"
            
            fee_a = FeeStructure("upbit", 5.0, 25.0)
            fee_b = FeeStructure("binance", 10.0, 25.0)
            fee_model = FeeModel(fee_a, fee_b)
            params = BreakEvenParams(fee_model, 10.0, 5.0)
            
            runner = ReplayRunner(market_file, replay_dir, params)
            result = runner.run()
            
            # 검증
            assert result["status"] == "PASS"
            assert result["ticks_count"] == 5
            assert (replay_dir / "decisions.ndjson").exists()
            assert (replay_dir / "manifest.json").exists()
