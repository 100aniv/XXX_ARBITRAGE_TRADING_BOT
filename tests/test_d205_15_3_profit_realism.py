"""
D205-15-3: Profit-Realism Fix 테스트

Directional/Executable KPI + Funding-Adjusted + Evidence Integrity
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


class TestDirectionalExecutableKPI:
    """AC-1, AC-2: Directional/Executable spread KPI 테스트"""
    
    def test_executable_spread_formula(self):
        """executable_spread_bps = (binance_bid - upbit_ask) / upbit_ask * 10000"""
        upbit_ask = 100000.0  # KRW
        binance_bid = 100100.0  # KRW (FX 정규화 후)
        
        executable_spread_bps = ((binance_bid - upbit_ask) / upbit_ask) * 10000
        
        assert executable_spread_bps == pytest.approx(10.0, abs=0.01)
    
    def test_executable_spread_negative_when_not_tradeable(self):
        """Upbit ask > Binance bid이면 음수 (거래 불가)"""
        upbit_ask = 100100.0
        binance_bid = 100000.0
        
        executable_spread_bps = ((binance_bid - upbit_ask) / upbit_ask) * 10000
        
        assert executable_spread_bps < 0
    
    def test_tradeable_rate_calculation(self):
        """tradeable_rate = tradeable_count / total_count"""
        tradeable_flags = [True, True, False, True, False]
        tradeable_count = sum(tradeable_flags)
        tradeable_rate = tradeable_count / len(tradeable_flags)
        
        assert tradeable_rate == pytest.approx(0.6, abs=0.001)
    
    def test_tradeable_rate_not_100_percent(self):
        """방향성 반영 시 tradeable_rate는 100%가 아님"""
        # 실제 시장에서는 항상 tradeable하지 않음
        tradeable_flags = [True, False, False, True, False, True, False, False, True, False]
        tradeable_rate = sum(tradeable_flags) / len(tradeable_flags)
        
        assert tradeable_rate != 1.0
        assert 0.0 < tradeable_rate < 1.0


class TestFundingRateProvider:
    """AC-3, AC-4: Funding Rate Provider 테스트"""
    
    def test_funding_rate_info_creation(self):
        """FundingRateInfo 데이터클래스 생성"""
        from arbitrage.v2.funding.provider import FundingRateInfo
        
        info = FundingRateInfo(
            symbol="BTCUSDT",
            funding_rate=0.0001,  # 0.01%
            funding_rate_bps=1.0,  # 1 bps
            mark_price=50000.0,
            index_price=49990.0,
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc),
        )
        
        assert info.symbol == "BTCUSDT"
        assert info.funding_rate_bps == 1.0
    
    def test_funding_component_calculation(self):
        """funding_component_bps = funding_rate * horizon / 8"""
        from arbitrage.v2.funding.provider import FundingRateInfo
        
        info = FundingRateInfo(
            symbol="BTCUSDT",
            funding_rate=0.0008,  # 0.08% (8 bps)
            funding_rate_bps=8.0,
            mark_price=50000.0,
            index_price=49990.0,
            next_funding_time=None,
            timestamp=datetime.now(timezone.utc),
        )
        
        # 1시간 기준
        component_1h = info.get_funding_component_bps(horizon_hours=1.0)
        assert component_1h == pytest.approx(1.0, abs=0.001)  # 8 * 1/8 = 1
        
        # 8시간 기준 (full funding period)
        component_8h = info.get_funding_component_bps(horizon_hours=8.0)
        assert component_8h == pytest.approx(8.0, abs=0.001)  # 8 * 8/8 = 8
    
    def test_funding_adjusted_edge_calculation(self):
        """funding_adjusted_edge_bps = net_edge - funding_component"""
        from arbitrage.v2.funding.provider import FundingRateProvider, FundingRateInfo
        
        provider = FundingRateProvider()
        
        info = FundingRateInfo(
            symbol="BTCUSDT",
            funding_rate=0.0008,
            funding_rate_bps=8.0,
            mark_price=50000.0,
            index_price=49990.0,
            next_funding_time=None,
            timestamp=datetime.now(timezone.utc),
        )
        
        result = provider.calculate_funding_adjusted_edge(
            net_edge_bps=10.0,
            funding_info=info,
            horizon_hours=1.0,
            is_short=True,
        )
        
        # net_edge(10) - funding_component(1) = 9
        assert result["funding_adjusted_edge_bps"] == pytest.approx(9.0, abs=0.1)
        assert result["funding_component_bps"] == pytest.approx(1.0, abs=0.1)
    
    def test_funding_rate_provider_initialization(self):
        """FundingRateProvider 초기화"""
        from arbitrage.v2.funding.provider import FundingRateProvider
        
        provider = FundingRateProvider(timeout=5.0)
        
        assert provider.timeout == 5.0
        assert provider._session is None  # Lazy init


class TestEvidenceGuardAtomicWrite:
    """AC-5: Evidence Guard Atomic Write 테스트"""
    
    def test_atomic_save_creates_file(self):
        """atomic save가 파일을 정상 생성"""
        from arbitrage.v2.scan.evidence_guard import save_json_with_validation
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.json"
            data = {"test": "data", "number": 123}
            
            save_json_with_validation(file_path, data)
            
            assert file_path.exists()
            with open(file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data
    
    def test_atomic_save_validates_immediately(self):
        """저장 후 즉시 검증 (재파싱)"""
        from arbitrage.v2.scan.evidence_guard import save_json_with_validation
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "validated.json"
            data = {"valid": True, "nested": {"key": "value"}}
            
            # 정상 저장 + 검증
            save_json_with_validation(file_path, data)
            
            # 파일 내용 확인
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 유효한 JSON인지 확인
            parsed = json.loads(content)
            assert parsed == data
    
    def test_atomic_save_no_temp_file_left(self):
        """성공 시 임시 파일이 남지 않음"""
        from arbitrage.v2.scan.evidence_guard import save_json_with_validation
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "clean.json"
            data = {"clean": True}
            
            save_json_with_validation(file_path, data)
            
            # 디렉토리에 .tmp 파일이 없어야 함
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0
    
    def test_validate_json_file_detects_corruption(self):
        """손상된 JSON 감지"""
        from arbitrage.v2.scan.evidence_guard import validate_json_file
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "corrupted.json"
            
            # 손상된 JSON 작성
            with open(file_path, "w", encoding="utf-8") as f:
                f.write('{"incomplete": ')  # 닫히지 않은 JSON
            
            with pytest.raises(ValueError, match="JSON parse error"):
                validate_json_file(file_path)
    
    def test_audit_evidence_directory(self):
        """디렉토리 전체 JSON 검증"""
        from arbitrage.v2.scan.evidence_guard import audit_evidence_directory, save_json_with_validation
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # 유효한 JSON 파일 생성
            save_json_with_validation(tmpdir_path / "valid1.json", {"a": 1})
            save_json_with_validation(tmpdir_path / "valid2.json", {"b": 2})
            
            result = audit_evidence_directory(tmpdir_path)
            
            assert result["total_json_files"] == 2
            assert result["valid_files"] == 2
            assert result["invalid_files"] == 0


class TestMetricsIntegration:
    """metrics.py 통합 테스트"""
    
    def test_metrics_includes_executable_kpi(self):
        """메트릭에 executable KPI가 포함됨"""
        from arbitrage.v2.scan.metrics import ScanMetricsCalculator
        from arbitrage.v2.scan.scanner import ScanConfig
        
        config = ScanConfig(
            fx_krw_per_usdt=1450.0,
            upbit_fee_bps=5.0,
            binance_fee_bps=4.0,
            slippage_bps=15.0,
            fx_conversion_bps=2.0,
            buffer_bps=5.0,
        )
        
        calculator = ScanMetricsCalculator(config)
        
        # 임시 market.ndjson 생성
        with tempfile.TemporaryDirectory() as tmpdir:
            market_file = Path(tmpdir) / "market.ndjson"
            
            # 테스트 tick 데이터
            ticks = [
                {"upbit_bid": 100000, "upbit_ask": 100010, "binance_bid": 100020, "binance_ask": 100030},
                {"upbit_bid": 100005, "upbit_ask": 100015, "binance_bid": 100010, "binance_ask": 100020},
                {"upbit_bid": 100010, "upbit_ask": 100020, "binance_bid": 100000, "binance_ask": 100010},
            ]
            
            with open(market_file, "w") as f:
                for tick in ticks:
                    f.write(json.dumps(tick) + "\n")
            
            metrics = calculator.calculate_symbol_metrics(market_file, "TEST/KRW")
            
            # 기존 KPI 존재
            assert "mean_net_edge_bps" in metrics["metrics"]
            assert "positive_rate" in metrics["metrics"]
            
            # D205-15-3 신규 KPI 존재
            assert "tradeable_rate" in metrics["metrics"]
            assert "tradeable_count" in metrics["metrics"]
            assert "mean_executable_edge_bps" in metrics["metrics"]
            
            # tradeable_rate가 100%가 아님을 검증 (방향성 반영)
            assert metrics["metrics"]["tradeable_rate"] < 1.0
