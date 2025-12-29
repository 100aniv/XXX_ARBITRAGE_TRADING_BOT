"""
D202-2: MarketData Sampler Contract 테스트

목표:
- Evidence 파일 구조 검증 (SSOT 규격)
- KPI 계산 함수 단위 테스트
- 디렉토리 생성 규칙 검증
- Mock 기반 (네트워크 호출 없음)

SSOT: docs/v2/design/EVIDENCE_FORMAT.md
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Import sampler (path adjustment)
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.run_d202_2_market_sampler import MarketDataSampler


class TestMarketDataSamplerContract:
    """MarketDataSampler 계약 테스트 (Mock 기반)"""
    
    def test_evidence_directory_creation(self):
        """Evidence 디렉토리 생성 규칙 검증"""
        # Mock providers to avoid network calls
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
                run_id="d202_2_market_sample_20251229_test",
            )
            
            # Evidence 디렉토리가 생성되어야 함
            assert sampler.evidence_dir.exists()
            assert sampler.evidence_dir.name == "d202_2_market_sample_20251229_test"
            # Path parts 검증 (OS-agnostic)
            parts = sampler.evidence_dir.parts
            assert "logs" in parts
            assert "evidence" in parts
    
    def test_run_id_format(self, tmp_path):
        """Run ID 포맷 검증 (SSOT 규격: d202_2_market_sample_YYYYMMDD_HHMM)"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
            )
            
            # run_id가 d202_2_market_sample_ prefix를 가져야 함
            assert sampler.run_id.startswith("d202_2_market_sample_")
            
            # YYYYMMDD_HHMMSS 형식 포함 (정규식 검증)
            import re
            pattern = r"d202_2_market_sample_\d{8}_\d{6}"
            assert re.match(pattern, sampler.run_id)
    
    def test_kpi_tracking_initialization(self):
        """KPI 추적 변수 초기화 검증"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW", "ETH/KRW"],
                duration_sec=30,
            )
            
            # KPI 초기값 검증
            assert sampler.samples_ok == 0
            assert sampler.samples_fail == 0
            assert sampler.parse_errors == 0
            assert sampler.latencies_ms == []
            assert sampler.errors == []
            assert sampler.raw_samples == []
            assert sampler.start_time is None
            assert sampler.end_time is None
    
    def test_percentile_calculation(self):
        """퍼센타일 계산 함수 단위 테스트"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(symbols=["BTC/KRW"], duration_sec=10)
            
            # 빈 리스트
            assert sampler._percentile([], 50) == 0.0
            
            # 단일 값
            assert sampler._percentile([100.0], 50) == 100.0
            
            # 정렬된 값들 (퍼센타일 계산은 idx 기반이므로 근사값)
            data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
            p50 = sampler._percentile(data, 50)
            p95 = sampler._percentile(data, 95)
            p100 = sampler._percentile(data, 100)
            
            # 50% ~ 60% 사이 (중간값 근사)
            assert 50.0 <= p50 <= 60.0
            # 95% ~ 100% 사이
            assert 95.0 <= p95 <= 100.0
            # 최대값
            assert p100 == 100.0
    
    @pytest.mark.asyncio
    async def test_sample_iteration_mock(self):
        """샘플링 iteration Mock 테스트 (네트워크 호출 없음)"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider') as MockUpbit, \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            # Mock ticker 반환
            mock_ticker = MagicMock()
            mock_ticker.bid = 50000000.0
            mock_ticker.ask = 50100000.0
            mock_ticker.last = 50050000.0
            mock_ticker.volume = 123.45
            
            mock_provider = MockUpbit.return_value
            mock_provider.get_ticker.return_value = mock_ticker
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
            )
            
            # 1회 샘플링 실행
            await sampler._sample_iteration()
            
            # 검증
            assert sampler.samples_ok == 1
            assert sampler.samples_fail == 0
            assert len(sampler.latencies_ms) == 1
            assert sampler.latencies_ms[0] >= 0  # latency는 0 이상
    
    @pytest.mark.asyncio
    async def test_sample_iteration_error_handling(self):
        """샘플링 에러 핸들링 테스트"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider') as MockUpbit, \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            # Mock ticker가 Exception 발생
            mock_provider = MockUpbit.return_value
            mock_provider.get_ticker.side_effect = ValueError("Mock error")
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
            )
            
            # 1회 샘플링 실행 (에러 발생해도 crash 안 함)
            await sampler._sample_iteration()
            
            # 검증
            assert sampler.samples_ok == 0
            assert sampler.samples_fail == 1
            assert sampler.parse_errors == 1
            assert len(sampler.errors) == 1
            assert sampler.errors[0]["type"] == "ValueError"
    
    def test_evidence_file_structure(self):
        """Evidence 파일 구조 검증 (SSOT 규격)"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
                run_id="test_evidence_structure",
            )
            
            # Mock 데이터 설정
            sampler.start_time = 1000.0
            sampler.end_time = 1010.0
            sampler.samples_ok = 5
            sampler.samples_fail = 1
            sampler.parse_errors = 1
            sampler.latencies_ms = [10.0, 20.0, 30.0]
            sampler.errors = [{"timestamp": "2025-12-29T00:00:00", "error": "test"}]
            sampler.raw_samples = [{"timestamp": "2025-12-29T00:00:00", "exchange": "upbit"}]
            
            # Evidence 저장 (동기 실행)
            import asyncio
            asyncio.run(sampler._save_evidence())
            
            # 파일 존재 검증
            assert (sampler.evidence_dir / "manifest.json").exists()
            assert (sampler.evidence_dir / "kpi.json").exists()
            assert (sampler.evidence_dir / "errors.ndjson").exists()
            assert (sampler.evidence_dir / "raw_sample.ndjson").exists()
            assert (sampler.evidence_dir / "README.md").exists()
    
    def test_manifest_json_schema(self):
        """manifest.json 스키마 검증"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
                run_id="test_manifest_schema",
            )
            
            sampler.start_time = 1000.0
            sampler.end_time = 1010.0
            sampler.samples_ok = 5
            sampler.latencies_ms = [10.0]
            
            import asyncio
            asyncio.run(sampler._save_evidence())
            
            # manifest.json 읽기
            with open(sampler.evidence_dir / "manifest.json", "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # 필수 필드 검증
            assert "run_id" in manifest
            assert "task" in manifest
            assert "start_time" in manifest
            assert "end_time" in manifest
            assert "duration_sec" in manifest
            assert "env" in manifest
            assert "symbols" in manifest
            assert "git_sha" in manifest
            
            assert manifest["task"] == "D202-2"
            assert manifest["symbols"] == ["BTC/KRW"]
    
    def test_kpi_json_schema(self):
        """kpi.json 스키마 검증"""
        with patch('scripts.run_d202_2_market_sampler.UpbitRestProvider'), \
             patch('scripts.run_d202_2_market_sampler.BinanceRestProvider'):
            
            sampler = MarketDataSampler(
                symbols=["BTC/KRW"],
                duration_sec=10,
                run_id="test_kpi_schema",
            )
            
            sampler.start_time = 1000.0
            sampler.end_time = 1010.0
            sampler.samples_ok = 5
            sampler.samples_fail = 1
            sampler.parse_errors = 1
            sampler.latencies_ms = [10.0, 20.0, 30.0]
            
            import asyncio
            asyncio.run(sampler._save_evidence())
            
            # kpi.json 읽기
            with open(sampler.evidence_dir / "kpi.json", "r", encoding="utf-8") as f:
                kpi = json.load(f)
            
            # 필수 KPI 필드 검증
            assert "uptime_sec" in kpi
            assert "samples_ok" in kpi
            assert "samples_fail" in kpi
            assert "parse_errors_count" in kpi
            assert "latency_ms_p50" in kpi
            assert "latency_ms_p95" in kpi
            assert "latency_ms_max" in kpi
            assert "ws_reconnect_count" in kpi
            assert "ws_disconnect_count" in kpi
            
            # 값 검증
            assert kpi["uptime_sec"] == 10.0
            assert kpi["samples_ok"] == 5
            assert kpi["samples_fail"] == 1
            assert kpi["parse_errors_count"] == 1
            assert kpi["latency_ms_p50"] == 20.0
            assert kpi["latency_ms_max"] == 30.0
