"""
D68 - Parameter Tuner
전략 파라미터 자동 튜닝 엔진
"""

import logging
import time
import itertools
import random
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import psycopg2
from psycopg2.extras import Json

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderBookSnapshot

logger = logging.getLogger(__name__)


@dataclass
class TuningConfig:
    """튜닝 설정"""
    # 파라미터 범위 정의
    param_ranges: Dict[str, List[float]]  # e.g., {'min_spread_bps': [20, 30, 40]}
    
    # 튜닝 모드
    mode: str = "grid"  # "grid" | "random"
    random_samples: int = 10  # random 모드일 때 샘플 수
    
    # 테스트 설정
    test_mode: str = "paper"  # "paper" | "backtest"
    campaign_id: str = "C1"  # 테스트할 캠페인 패턴
    duration_seconds: int = 120  # 각 테스트 실행 시간
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    
    # PostgreSQL 연결 정보 (arbitrage 전용 infra 스택)
    db_host: str = "localhost"
    db_port: int = 5432  # arbitrage-postgres 포트
    db_name: str = "arbitrage"  # arbitrage DB
    db_user: str = "arbitrage"  # arbitrage 사용자
    db_password: str = "arbitrage"  # arbitrage 비밀번호
    
    # 세션 정보
    session_id: Optional[str] = None  # None이면 자동 생성
    notes: str = ""


@dataclass
class TuningResult:
    """단일 튜닝 실행 결과"""
    run_id: Optional[int] = None
    session_id: str = ""
    param_set: Dict[str, Any] = field(default_factory=dict)
    
    # 성능 메트릭
    total_pnl: float = 0.0
    total_trades: int = 0
    total_entries: int = 0
    total_exits: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    winrate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    # 실행 정보
    campaign_id: str = ""
    duration_seconds: int = 0
    test_mode: str = ""
    symbols: str = ""
    notes: str = ""
    error_message: str = ""
    
    created_at: Optional[str] = None


class ParameterTuner:
    """
    D68 파라미터 튜너
    
    주요 기능:
    1. 파라미터 조합 생성 (grid/random)
    2. 각 조합마다 Paper campaign 실행
    3. 결과 수집 및 PostgreSQL 저장
    4. 실시간 베스트 결과 추적
    """
    
    def __init__(self, config: TuningConfig):
        """
        Args:
            config: 튜닝 설정
        """
        self.config = config
        
        # 세션 ID 생성
        if not config.session_id:
            self.config.session_id = f"tuning_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # 결과 저장소
        self.results: List[TuningResult] = []
        self.best_result: Optional[TuningResult] = None
        
        # PostgreSQL 연결
        self.db_conn = None
        
        logger.info(f"[D68_TUNER] Initialized with session_id={self.config.session_id}")
    
    def connect_db(self):
        """PostgreSQL 연결 (필수)
        
        D68 Acceptance는 DB 저장을 필수로 요구합니다.
        DB 연결 실패 시 예외를 발생시켜 테스트를 FAIL 처리합니다.
        """
        try:
            self.db_conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                dbname=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password
            )
            logger.info("[D68_TUNER] ✅ Connected to PostgreSQL")
        except Exception as e:
            error_msg = f"[D68_TUNER] ❌ CRITICAL: PostgreSQL connection failed: {e}"
            logger.error(error_msg)
            logger.error("[D68_TUNER] D68 requires PostgreSQL DB for tuning result storage.")
            logger.error("[D68_TUNER] Please ensure Docker PostgreSQL is running: docker compose up -d postgres")
            raise RuntimeError(error_msg)
    
    def close_db(self):
        """PostgreSQL 연결 종료"""
        if self.db_conn:
            self.db_conn.close()
            logger.info("[D68_TUNER] Closed PostgreSQL connection")
    
    def generate_param_combinations(self) -> List[Dict[str, float]]:
        """
        파라미터 조합 생성
        
        Returns:
            파라미터 조합 리스트
        """
        if self.config.mode == "grid":
            # Grid Search: 모든 조합 생성
            param_names = list(self.config.param_ranges.keys())
            param_values = [self.config.param_ranges[name] for name in param_names]
            
            combinations = []
            for values in itertools.product(*param_values):
                combo = dict(zip(param_names, values))
                combinations.append(combo)
            
            logger.info(f"[D68_TUNER] Generated {len(combinations)} grid combinations")
            return combinations
        
        elif self.config.mode == "random":
            # Random Search: 랜덤 샘플링
            combinations = []
            param_names = list(self.config.param_ranges.keys())
            
            for _ in range(self.config.random_samples):
                combo = {}
                for name in param_names:
                    values = self.config.param_ranges[name]
                    combo[name] = random.choice(values)
                combinations.append(combo)
            
            logger.info(f"[D68_TUNER] Generated {len(combinations)} random combinations")
            return combinations
        
        else:
            raise ValueError(f"Unknown tuning mode: {self.config.mode}")
    
    def run_single_test(
        self,
        param_set: Dict[str, float],
        combination_index: int,
        total_combinations: int
    ) -> TuningResult:
        """
        단일 파라미터 조합 테스트 실행
        
        Args:
            param_set: 파라미터 조합
            combination_index: 현재 조합 인덱스 (1-based)
            total_combinations: 전체 조합 수
        
        Returns:
            테스트 결과
        """
        logger.info(
            f"[D68_TUNER] Running test {combination_index}/{total_combinations} "
            f"with params: {param_set}"
        )
        
        result = TuningResult(
            session_id=self.config.session_id,
            param_set=param_set.copy(),
            campaign_id=self.config.campaign_id,
            duration_seconds=self.config.duration_seconds,
            test_mode=self.config.test_mode,
            symbols=",".join(self.config.symbols),
            notes=self.config.notes
        )
        
        try:
            # Paper campaign 실행
            metrics = self._run_paper_campaign(param_set)
            
            # 결과 수집
            result.total_pnl = metrics.get('total_pnl', 0.0)
            result.total_trades = metrics.get('total_trades', 0)
            result.total_entries = metrics.get('total_entries', 0)
            result.total_exits = metrics.get('total_exits', 0)
            result.winning_trades = metrics.get('winning_trades', 0)
            result.losing_trades = metrics.get('losing_trades', 0)
            
            # 계산 메트릭
            if result.total_exits > 0:
                result.winrate = (result.winning_trades / result.total_exits) * 100
                result.avg_pnl_per_trade = result.total_pnl / result.total_exits
            else:
                result.winrate = 0.0
                result.avg_pnl_per_trade = 0.0
            
            result.max_drawdown = metrics.get('max_drawdown', 0.0)
            result.sharpe_ratio = metrics.get('sharpe_ratio', 0.0)
            
            logger.info(
                f"[D68_TUNER] Test {combination_index}/{total_combinations} completed: "
                f"PnL=${result.total_pnl:.2f}, Winrate={result.winrate:.1f}%, "
                f"Trades={result.total_exits}"
            )
            
        except Exception as e:
            logger.error(f"[D68_TUNER] Test {combination_index}/{total_combinations} failed: {e}")
            result.error_message = str(e)
        
        return result
    
    def _run_paper_campaign(self, param_set: Dict[str, float]) -> Dict[str, Any]:
        """
        Paper campaign 실행 (D65/D66/D67 스타일)
        
        Args:
            param_set: 파라미터 조합
        
        Returns:
            메트릭 딕셔너리
        """
        # PaperExchange 초기화
        exchange_a = PaperExchange()
        exchange_b = PaperExchange()
        
        # 초기 호가 설정
        snapshot_a = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(100000.0, 1.0)],
            asks=[(100000.0, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(40000.0, 1.0)],
            asks=[(40000.0, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        # 엔진 설정 (파라미터 적용)
        engine_config = ArbitrageConfig(
            min_spread_bps=param_set.get('min_spread_bps', 30.0),
            taker_fee_a_bps=param_set.get('taker_fee_a_bps', 10.0),
            taker_fee_b_bps=param_set.get('taker_fee_b_bps', 10.0),
            slippage_bps=param_set.get('slippage_bps', 5.0),
            max_position_usd=param_set.get('max_position_usd', 1000.0),
            max_open_trades=1,
            close_on_spread_reversal=True,
            exchange_a_to_b_rate=2.5,
            bid_ask_spread_bps=100.0,
        )
        engine = ArbitrageEngine(engine_config)
        
        # Runner 설정
        risk_limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=10000.0,
            max_open_trades=1,
        )
        
        runner_config = ArbitrageLiveConfig(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            mode="paper",
            data_source="paper",
            paper_spread_injection_interval=5,
            paper_simulation_enabled=True,
            risk_limits=risk_limits,
            max_runtime_seconds=self.config.duration_seconds,
            poll_interval_seconds=1.0
        )
        
        # Runner 초기화
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=runner_config
        )
        
        # Paper campaign 패턴 설정
        runner._paper_campaign_id = self.config.campaign_id
        
        # 실행
        start_time = time.time()
        runner.run_forever()
        elapsed = time.time() - start_time
        
        # 메트릭 수집
        metrics = {
            'total_pnl': runner._total_pnl_usd,
            'total_trades': runner._total_trades_closed,
            'total_entries': runner._total_trades_opened,
            'total_exits': runner._total_trades_closed,
            'winning_trades': runner._total_winning_trades,
            'losing_trades': runner._total_trades_closed - runner._total_winning_trades,
            'max_drawdown': 0.0,  # TODO: 추후 구현
            'sharpe_ratio': 0.0,  # TODO: 추후 구현
            'duration_seconds': int(elapsed)
        }
        
        return metrics
    
    def save_result_to_db(self, result: TuningResult):
        """
        결과를 PostgreSQL에 저장 (필수)
        
        D68 Acceptance는 모든 튜닝 결과가 DB에 저장되어야 합니다.
        DB 저장 실패 시 예외를 발생시킵니다.
        
        Args:
            result: 튜닝 결과
            
        Raises:
            RuntimeError: DB 저장 실패 시
        """
        if not self.db_conn:
            error_msg = "[D68_TUNER] ❌ CRITICAL: No DB connection available for result storage"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            cursor = self.db_conn.cursor()
            
            insert_query = """
                INSERT INTO tuning_results (
                    session_id, param_set, total_pnl, total_trades,
                    total_entries, total_exits, winning_trades, losing_trades,
                    winrate, avg_pnl_per_trade, max_drawdown, sharpe_ratio,
                    campaign_id, duration_seconds, test_mode, symbols,
                    notes, error_message
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING run_id, created_at;
            """
            
            cursor.execute(insert_query, (
                result.session_id,
                Json(result.param_set),
                result.total_pnl,
                result.total_trades,
                result.total_entries,
                result.total_exits,
                result.winning_trades,
                result.losing_trades,
                result.winrate,
                result.avg_pnl_per_trade,
                result.max_drawdown,
                result.sharpe_ratio,
                result.campaign_id,
                result.duration_seconds,
                result.test_mode,
                result.symbols,
                result.notes,
                result.error_message or None
            ))
            
            row = cursor.fetchone()
            result.run_id = row[0]
            result.created_at = row[1].isoformat()
            
            self.db_conn.commit()
            cursor.close()
            
            logger.info(f"[D68_TUNER] ✅ Saved result to DB with run_id={result.run_id}")
            
        except Exception as e:
            error_msg = f"[D68_TUNER] ❌ CRITICAL: Failed to save result to DB: {e}"
            logger.error(error_msg)
            if self.db_conn:
                self.db_conn.rollback()
            raise RuntimeError(error_msg)
    
    def save_results_to_json(self, filepath: str):
        """
        결과를 JSON 파일로 저장
        
        Args:
            filepath: 저장할 파일 경로
        """
        import json
        from datetime import datetime
        
        output_data = {
            'session_id': self.config.session_id,
            'created_at': datetime.now().isoformat(),
            'config': {
                'mode': self.config.mode,
                'campaign_id': self.config.campaign_id,
                'duration_seconds': self.config.duration_seconds,
                'symbols': self.config.symbols,
                'param_ranges': self.config.param_ranges
            },
            'results': []
        }
        
        for result in self.results:
            output_data['results'].append({
                'param_set': result.param_set,
                'total_pnl': result.total_pnl,
                'total_trades': result.total_trades,
                'total_entries': result.total_entries,
                'total_exits': result.total_exits,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'winrate': result.winrate,
                'avg_pnl_per_trade': result.avg_pnl_per_trade,
                'error_message': result.error_message
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D68_TUNER] Results saved to JSON: {filepath}")
    
    def update_best_result(self, result: TuningResult):
        """
        베스트 결과 업데이트
        
        Args:
            result: 새 결과
        """
        # PnL 기준으로 베스트 결정
        if self.best_result is None or result.total_pnl > self.best_result.total_pnl:
            self.best_result = result
            logger.info(
                f"[D68_TUNER] 🏆 New best result! "
                f"PnL=${result.total_pnl:.2f}, Winrate={result.winrate:.1f}%, "
                f"Params={result.param_set}"
            )
    
    def run_tuning(self) -> List[TuningResult]:
        """
        전체 튜닝 실행
        
        Returns:
            모든 테스트 결과 리스트
        """
        logger.info(f"[D68_TUNER] Starting tuning session: {self.config.session_id}")
        logger.info(f"[D68_TUNER] Mode: {self.config.mode}, Campaign: {self.config.campaign_id}")
        
        # DB 연결
        self.connect_db()
        
        try:
            # 파라미터 조합 생성
            combinations = self.generate_param_combinations()
            total_combinations = len(combinations)
            
            logger.info(f"[D68_TUNER] Testing {total_combinations} parameter combinations")
            
            # 각 조합 실행
            for idx, param_set in enumerate(combinations, start=1):
                result = self.run_single_test(param_set, idx, total_combinations)
                
                # 결과 저장
                self.results.append(result)
                self.save_result_to_db(result)
                self.update_best_result(result)
                
                # 진행 상황 출력
                logger.info(
                    f"[D68_TUNER] Progress: {idx}/{total_combinations} "
                    f"({idx/total_combinations*100:.1f}%)"
                )
            
            # 최종 요약
            logger.info(f"[D68_TUNER] Tuning session completed!")
            logger.info(f"[D68_TUNER] Total tests: {total_combinations}")
            if self.best_result:
                logger.info(
                    f"[D68_TUNER] Best result: PnL=${self.best_result.total_pnl:.2f}, "
                    f"Winrate={self.best_result.winrate:.1f}%, "
                    f"Params={self.best_result.param_set}"
                )
            
            # JSON 파일로 결과 저장
            json_path = f"results_{self.config.session_id}.json"
            self.save_results_to_json(json_path)
            
        finally:
            # DB 연결 종료
            self.close_db()
        
        return self.results
    
    def get_top_results(self, n: int = 5, sort_by: str = "total_pnl") -> List[TuningResult]:
        """
        상위 N개 결과 반환
        
        Args:
            n: 반환할 결과 수
            sort_by: 정렬 기준 ('total_pnl' | 'winrate' | 'sharpe_ratio')
        
        Returns:
            상위 N개 결과
        """
        if not self.results:
            return []
        
        sorted_results = sorted(
            self.results,
            key=lambda r: getattr(r, sort_by, 0),
            reverse=True
        )
        
        return sorted_results[:n]
