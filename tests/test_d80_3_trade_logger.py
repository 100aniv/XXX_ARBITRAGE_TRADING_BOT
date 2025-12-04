# -*- coding: utf-8 -*-
"""
D80-3: Trade Logger Unit Tests
트레이드 로거 유닛 테스트

테스트 항목:
1. TradeLogger 초기화 및 로그 디렉토리 생성
2. 단일 트레이드 로깅
3. Universe별 로그 분리
4. TradeLogEntry JSON 직렬화
5. 잘못된 데이터 처리
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from arbitrage.logging.trade_logger import (
    TradeLogEntry,
    TradeLogger,
    create_mock_trade_entry
)


class TestTradeLogger:
    """TradeLogger 테스트 suite"""
    
    def test_trade_logger_init(self, tmp_path):
        """
        TradeLogger 초기화 테스트
        
        검증:
        - 로그 디렉토리 생성
        - 로그 파일 경로 올바름
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_001",
            universe_mode="TOP_20",
            session_id="test_session_001"
        )
        
        assert logger.run_id == "test_run_001"
        assert logger.universe_mode == "TOP_20"
        assert logger.session_id == "test_session_001"
        assert logger.trade_count == 0
        
        # 로그 파일 경로 검증
        expected_log_file = tmp_path / "logs" / "test_run_001" / "top20_trade_log.jsonl"
        assert logger.log_file == expected_log_file
        assert logger.log_file.parent.exists()
    
    def test_trade_logger_log_single_trade(self, tmp_path):
        """
        단일 트레이드 로깅 테스트
        
        검증:
        - JSONL 파일 생성
        - 로그 내용 정확성
        - trade_count 증가
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_002",
            universe_mode="TOP_20"
        )
        
        # Mock trade entry 생성
        entry = create_mock_trade_entry(
            trade_id="rt_001",
            session_id="test_session_002",
            universe_mode="TOP_20",
            symbol="BTC/USDT"
        )
        
        # 로그 기록
        logger.log_trade(entry)
        
        # 검증
        assert logger.trade_count == 1
        assert logger.log_file.exists()
        
        # 파일 내용 확인
        with open(logger.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        
        logged_entry = json.loads(lines[0])
        assert logged_entry["trade_id"] == "rt_001"
        assert logged_entry["symbol"] == "BTC/USDT"
        assert logged_entry["entry_spread_bps"] == 45.0
        assert logged_entry["gross_pnl_usd"] == 19.90
    
    def test_trade_logger_multiple_trades(self, tmp_path):
        """
        여러 트레이드 로깅 테스트
        
        검증:
        - 여러 로그가 순차적으로 append됨
        - trade_count 정확성
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_003",
            universe_mode="TOP_50"
        )
        
        # 5개 트레이드 로깅
        for i in range(5):
            entry = create_mock_trade_entry(
                trade_id=f"rt_{i+1:03d}",
                session_id="test_session_003",
                universe_mode="TOP_50",
                symbol=f"TEST{i}/USDT"
            )
            logger.log_trade(entry)
        
        # 검증
        assert logger.trade_count == 5
        
        # 파일 내용 확인
        with open(logger.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) == 5
        
        # 각 라인이 유효한 JSON인지 확인
        for i, line in enumerate(lines):
            logged_entry = json.loads(line)
            assert logged_entry["trade_id"] == f"rt_{i+1:03d}"
            assert logged_entry["symbol"] == f"TEST{i}/USDT"
    
    def test_trade_logger_universe_separation(self, tmp_path):
        """
        Universe별 로그 분리 테스트
        
        검증:
        - Top20, Top50 로그 파일이 분리됨
        - 각 파일에 올바른 데이터가 기록됨
        """
        # Top20 logger
        logger_top20 = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_004",
            universe_mode="TOP_20"
        )
        
        # Top50 logger
        logger_top50 = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_004",
            universe_mode="TOP_50"
        )
        
        # Top20 트레이드 로깅
        entry_top20 = create_mock_trade_entry(
            trade_id="rt_top20_001",
            session_id="test_session_004",
            universe_mode="TOP_20"
        )
        logger_top20.log_trade(entry_top20)
        
        # Top50 트레이드 로깅
        entry_top50 = create_mock_trade_entry(
            trade_id="rt_top50_001",
            session_id="test_session_004",
            universe_mode="TOP_50"
        )
        logger_top50.log_trade(entry_top50)
        
        # 검증: 파일이 분리되어 생성됨
        expected_log_top20 = tmp_path / "logs" / "test_run_004" / "top20_trade_log.jsonl"
        expected_log_top50 = tmp_path / "logs" / "test_run_004" / "top50_trade_log.jsonl"
        
        assert expected_log_top20.exists()
        assert expected_log_top50.exists()
        
        # 각 파일 내용 확인
        with open(expected_log_top20, "r") as f:
            top20_data = json.loads(f.readline())
            assert top20_data["trade_id"] == "rt_top20_001"
            assert top20_data["universe_mode"] == "TOP_20"
        
        with open(expected_log_top50, "r") as f:
            top50_data = json.loads(f.readline())
            assert top50_data["trade_id"] == "rt_top50_001"
            assert top50_data["universe_mode"] == "TOP_50"
    
    def test_trade_log_entry_serialization(self):
        """
        TradeLogEntry JSON 직렬화 테스트
        
        검증:
        - asdict() 결과가 JSON으로 변환 가능
        - 필수 필드가 모두 포함됨
        """
        entry = create_mock_trade_entry(
            trade_id="rt_serialize_001",
            session_id="test_session_005",
            universe_mode="TOP_20"
        )
        
        # asdict() 변환
        entry_dict = entry.__dict__
        
        # JSON 직렬화 가능 여부 확인
        json_str = json.dumps(entry_dict)
        assert json_str is not None
        
        # 역직렬화 확인
        deserialized = json.loads(json_str)
        
        # 필수 필드 확인
        required_fields = [
            "timestamp", "session_id", "trade_id", "universe_mode",
            "symbol", "entry_spread_bps", "exit_spread_bps",
            "gross_pnl_usd", "net_pnl_usd", "trade_result"
        ]
        
        for field in required_fields:
            assert field in deserialized
            assert deserialized[field] is not None
    
    def test_trade_logger_save_metadata(self, tmp_path):
        """
        메타데이터 저장 테스트
        
        검증:
        - metadata.json 파일 생성
        - 메타데이터 내용 정확성
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_006",
            universe_mode="TOP_20",
            session_id="test_session_006"
        )
        
        # 몇 개 트레이드 로깅
        for i in range(3):
            entry = create_mock_trade_entry(
                trade_id=f"rt_{i+1:03d}",
                session_id="test_session_006",
                universe_mode="TOP_20"
            )
            logger.log_trade(entry)
        
        # 메타데이터 저장
        metadata = {
            "start_time": "2025-12-04T00:00:00Z",
            "end_time": "2025-12-04T00:03:00Z",
            "duration_seconds": 180
        }
        logger.save_metadata(metadata)
        
        # 검증
        metadata_file = logger.log_file.parent / "metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)
        
        # 기본 메타데이터 포함 확인
        assert saved_metadata["run_id"] == "test_run_006"
        assert saved_metadata["universe_mode"] == "TOP_20"
        assert saved_metadata["session_id"] == "test_session_006"
        assert saved_metadata["total_trades_logged"] == 3
        assert saved_metadata["version"] == "D80-3"
        
        # 커스텀 메타데이터 포함 확인
        assert saved_metadata["start_time"] == "2025-12-04T00:00:00Z"
        assert saved_metadata["duration_seconds"] == 180
    
    def test_trade_logger_get_trade_count(self, tmp_path):
        """
        트레이드 카운트 조회 테스트
        
        검증:
        - get_trade_count() 정확성
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_007",
            universe_mode="TOP_20"
        )
        
        assert logger.get_trade_count() == 0
        
        # 10개 트레이드 로깅
        for i in range(10):
            entry = create_mock_trade_entry(
                trade_id=f"rt_{i+1:03d}",
                session_id="test_session_007",
                universe_mode="TOP_20"
            )
            logger.log_trade(entry)
        
        assert logger.get_trade_count() == 10
    
    def test_trade_logger_close(self, tmp_path):
        """
        TradeLogger 종료 테스트
        
        검증:
        - close() 호출 시 에러 없음
        - 로그 파일 정상 유지
        """
        logger = TradeLogger(
            base_dir=tmp_path / "logs",
            run_id="test_run_008",
            universe_mode="TOP_20"
        )
        
        entry = create_mock_trade_entry(
            trade_id="rt_001",
            session_id="test_session_008",
            universe_mode="TOP_20"
        )
        logger.log_trade(entry)
        
        # close() 호출
        logger.close()
        
        # 로그 파일 여전히 존재하고 읽기 가능
        assert logger.log_file.exists()
        
        with open(logger.log_file, "r") as f:
            lines = f.readlines()
        
        assert len(lines) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
