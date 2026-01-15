"""
V2 Config Loader

config/v2/config.yml을 로드하고 dataclass로 검증합니다.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExchangeConfig:
    """거래소 설정"""
    name: str
    enabled: bool
    taker_fee_bps: float
    maker_fee_bps: float
    min_order_krw: Optional[float] = None
    min_notional_usdt: Optional[float] = None
    market_order_rules: Optional[Dict] = None
    rate_limit: Optional[Dict] = None


@dataclass
class UniverseConfig:
    """거래 대상 설정"""
    symbols_top_n: int
    allowlist: List[str] = field(default_factory=list)
    denylist: List[str] = field(default_factory=list)


@dataclass
class ThresholdConfig:
    """Threshold 계산 설정"""
    use_exchange_fees: bool
    slippage_bps: float
    buffer_bps: float


@dataclass
class OrderSizePolicyConfig:
    """주문 크기 정책 설정"""
    mode: str  # "fixed_quote" or "risk_based"
    fixed_quote: Optional[Dict] = None


@dataclass
class StrategyConfig:
    """전략 파라미터"""
    threshold: ThresholdConfig
    order_size_policy: OrderSizePolicyConfig


@dataclass
class ExecutionConfig:
    """실행 설정"""
    cycle_interval_seconds: float
    max_concurrent_orders: int
    dry_run: bool


@dataclass
class ExecutionEnvironmentConfig:
    """실행 환경 설정 (D206 Taxonomy)"""
    environment: str  # backtest | paper | live
    profile: str  # smoke | baseline | longrun | acceptance | extended
    rigor: str  # quick | ssot


@dataclass
class SafetyConfig:
    """안전 장치 설정"""
    max_daily_loss_krw: float
    max_position_usd: float
    cooldown_after_loss_seconds: int
    emergency_stop: Dict


@dataclass
class ReportingConfig:
    """리포팅 설정"""
    pnl_windows: List[str]
    snapshot_path: str
    report_interval_seconds: int


@dataclass
class MonitoringConfig:
    """모니터링 설정"""
    prometheus_enabled: bool
    metrics_endpoint: str
    health_check_interval_seconds: int


@dataclass
class LoggingConfig:
    """로깅 설정"""
    level: str
    file_path: str
    rotation: Dict


@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    enabled: bool
    host: Optional[str] = None
    port: Optional[int] = None
    name: Optional[str] = None


@dataclass
class CacheConfig:
    """캐시 설정"""
    redis_enabled: bool
    market_data_ttl_ms: int


@dataclass
class TuningConfig:
    """파라미터 튜닝 설정 (D205-14)"""
    enabled: bool
    param_ranges: Dict = field(default_factory=dict)
    sweep: Optional[Dict] = None
    objective: Optional[Dict] = None


@dataclass
class ProfitCoreConfig:
    """
    Profit Core 설정 (Config SSOT)
    
    D206-1 AC-1: 파라미터 SSOT화
    - default_price_krw: Upbit BTC/KRW 기준 가격 (REQUIRED)
    - default_price_usdt: Binance BTC/USDT 기준 가격 (REQUIRED)
    - price_sanity_min_krw: Upbit 가격 하한 (이상치 탐지)
    - price_sanity_max_krw: Upbit 가격 상한
    """
    default_price_krw: float
    default_price_usdt: float
    price_sanity_min_krw: float = 0.0
    price_sanity_max_krw: float = float('inf')
    enable_sanity_check: bool = True
    
    def __post_init__(self):
        """SSOT 무결성 검증 (config.yml 필수)"""
        if self.default_price_krw <= 0:
            raise ValueError(f"ProfitCoreConfig: default_price_krw must be > 0, got {self.default_price_krw}")
        if self.default_price_usdt <= 0:
            raise ValueError(f"ProfitCoreConfig: default_price_usdt must be > 0, got {self.default_price_usdt}")


@dataclass
class TunerConfig:
    """
    Tuner 설정 (Config SSOT)
    
    D206-1 AC-4: 튜너 훅 설계
    """
    enabled: bool = False
    tuner_type: str = "static"
    param_overrides: Optional[Dict[str, Any]] = None


@dataclass
class MetaConfig:
    """메타 정보"""
    version: str
    config_name: str
    created_at: str
    description: str


@dataclass
class V2Config:
    """V2 전체 설정"""
    mode: str  # paper, live, replay (D205-13, Legacy - use execution_env.environment)
    execution_env: ExecutionEnvironmentConfig  # D206 Taxonomy (environment/profile/rigor)
    execution: ExecutionConfig  # D206-0: Execution settings (cycle_interval, concurrent_orders, dry_run)
    exchanges: Dict[str, ExchangeConfig]
    universe: UniverseConfig
    strategy: StrategyConfig
    cycle_interval_seconds: float  # Legacy (moved from execution block)
    max_concurrent_orders: int  # Legacy
    dry_run: bool  # Legacy
    safety: SafetyConfig
    reporting: ReportingConfig
    monitoring: MonitoringConfig
    logging: LoggingConfig
    database: DatabaseConfig
    cache: CacheConfig
    tuning: TuningConfig  # D205-14
    profit_core: ProfitCoreConfig  # D206-1: Profit Core (하드코딩 제거)
    tuner: TunerConfig  # D206-1: Tuner Interface
    meta: MetaConfig
    
    def validate(self):
        """설정 검증"""
        # D206 Taxonomy 검증
        valid_environments = ["backtest", "paper", "live"]
        if self.execution_env.environment not in valid_environments:
            raise ValueError(f"execution.environment는 {valid_environments} 중 하나여야 함 (현재: {self.execution_env.environment})")
        
        valid_profiles = ["smoke", "baseline", "longrun", "acceptance", "extended"]
        if self.execution_env.profile not in valid_profiles:
            raise ValueError(f"execution.profile은 {valid_profiles} 중 하나여야 함 (현재: {self.execution_env.profile})")
        
        valid_rigors = ["quick", "ssot"]
        if self.execution_env.rigor not in valid_rigors:
            raise ValueError(f"execution.rigor는 {valid_rigors} 중 하나여야 함 (현재: {self.execution_env.rigor})")
        
        # LIVE 모드 설계 누락 검증 (D206 ADD-ON)
        if self.execution_env.environment == "live":
            logger.warning("[V2 Config] LIVE 환경 설정됨 - LIVE 모드는 D206 이후 구현 예정")
        
        # Mode 검증 (D205-13, Legacy)
        valid_modes = ["paper", "live", "replay"]
        if self.mode not in valid_modes:
            raise ValueError(f"mode는 {valid_modes} 중 하나여야 함 (현재: {self.mode})")
        
        # 거래소 최소 1개 활성화
        enabled_exchanges = [name for name, cfg in self.exchanges.items() if cfg.enabled]
        if not enabled_exchanges:
            raise ValueError("최소 1개 거래소가 활성화되어야 합니다")
        
        # Order size policy 검증
        if self.strategy.order_size_policy.mode == "fixed_quote":
            if not self.strategy.order_size_policy.fixed_quote:
                raise ValueError("fixed_quote 모드는 fixed_quote 설정 필수")
        
        # Threshold 값 양수 확인
        if self.strategy.threshold.slippage_bps < 0:
            raise ValueError("slippage_bps는 0 이상이어야 함")
        if self.strategy.threshold.buffer_bps < 0:
            raise ValueError("buffer_bps는 0 이상이어야 함")
        
        # Safety limits 양수 확인
        if self.safety.max_daily_loss_krw <= 0:
            raise ValueError("max_daily_loss_krw는 양수여야 함")
        if self.safety.max_position_usd <= 0:
            raise ValueError("max_position_usd는 양수여야 함")
        
        logger.info(f"[V2 Config] 검증 완료: env={self.execution_env.environment}, profile={self.execution_env.profile}, rigor={self.execution_env.rigor}, {len(enabled_exchanges)}개 거래소")
    
    def get_break_even_spread_bps(self, exchange_a: str, exchange_b: str) -> float:
        """
        Break-even spread 계산 (bps 단위)
        
        Args:
            exchange_a: 첫 번째 거래소 이름
            exchange_b: 두 번째 거래소 이름
        
        Returns:
            Break-even spread (bps)
        """
        if self.strategy.threshold.use_exchange_fees:
            fee_a = self.exchanges[exchange_a].taker_fee_bps
            fee_b = self.exchanges[exchange_b].taker_fee_bps
        else:
            fee_a = 0.0
            fee_b = 0.0
        
        slippage = self.strategy.threshold.slippage_bps
        buffer = self.strategy.threshold.buffer_bps
        
        break_even = fee_a + fee_b + slippage + buffer
        
        logger.debug(
            f"[V2 Config] Break-even spread: "
            f"{fee_a:.2f} (fee_a) + {fee_b:.2f} (fee_b) + "
            f"{slippage:.2f} (slippage) + {buffer:.2f} (buffer) = {break_even:.2f} bps"
        )
        
        return break_even


def load_config(config_path: str = "config/v2/config.yml") -> V2Config:
    """
    config.yml 로드 및 dataclass 변환
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        V2Config 인스턴스
    
    Raises:
        FileNotFoundError: 설정 파일 없음
        ValueError: 설정 검증 실패
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"설정 파일 없음: {config_path}")
    
    # YAML 로드
    with open(path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    # D206 Taxonomy 파싱
    exec_data = raw_config.get('execution', {})
    execution_env = ExecutionEnvironmentConfig(
        environment=exec_data.get('environment', 'paper'),
        profile=exec_data.get('profile', 'smoke'),
        rigor=exec_data.get('rigor', 'quick')
    )
    
    # Mode 파싱 (D205-13, Legacy)
    mode = raw_config.get('mode', 'paper')  # 기본값: paper
    
    # Exchanges 파싱
    exchanges = {}
    for name, ex_data in raw_config['exchanges'].items():
        exchanges[name] = ExchangeConfig(
            name=ex_data['name'],
            enabled=ex_data['enabled'],
            taker_fee_bps=ex_data['taker_fee_bps'],
            maker_fee_bps=ex_data['maker_fee_bps'],
            min_order_krw=ex_data.get('min_order_krw'),
            min_notional_usdt=ex_data.get('min_notional_usdt'),
            market_order_rules=ex_data.get('market_order_rules'),
            rate_limit=ex_data.get('rate_limit'),
        )
    
    # Universe 파싱
    universe = UniverseConfig(
        symbols_top_n=raw_config['universe']['symbols_top_n'],
        allowlist=raw_config['universe'].get('allowlist', []),
        denylist=raw_config['universe'].get('denylist', []),
    )
    
    # Strategy 파싱
    threshold = ThresholdConfig(
        use_exchange_fees=raw_config['strategy']['threshold']['use_exchange_fees'],
        slippage_bps=raw_config['strategy']['threshold']['slippage_bps'],
        buffer_bps=raw_config['strategy']['threshold']['buffer_bps'],
    )
    
    order_size_policy = OrderSizePolicyConfig(
        mode=raw_config['strategy']['order_size_policy']['mode'],
        fixed_quote=raw_config['strategy']['order_size_policy'].get('fixed_quote'),
    )
    
    strategy = StrategyConfig(
        threshold=threshold,
        order_size_policy=order_size_policy,
    )
    
    # Execution 파싱 (선택적 필드, 기본값 사용)
    exec_raw = raw_config.get('execution', {})
    execution = ExecutionConfig(
        cycle_interval_seconds=exec_raw.get('cycle_interval_seconds', 1.0),
        max_concurrent_orders=exec_raw.get('max_concurrent_orders', 5),
        dry_run=exec_raw.get('dry_run', True),
    )
    
    # Safety 파싱
    safety = SafetyConfig(
        max_daily_loss_krw=raw_config['safety']['max_daily_loss_krw'],
        max_position_usd=raw_config['safety']['max_position_usd'],
        cooldown_after_loss_seconds=raw_config['safety']['cooldown_after_loss_seconds'],
        emergency_stop=raw_config['safety']['emergency_stop'],
    )
    
    # Reporting 파싱
    reporting = ReportingConfig(
        pnl_windows=raw_config['reporting']['pnl_windows'],
        snapshot_path=raw_config['reporting']['snapshot_path'],
        report_interval_seconds=raw_config['reporting']['report_interval_seconds'],
    )
    
    # Monitoring 파싱
    monitoring = MonitoringConfig(
        prometheus_enabled=raw_config['monitoring']['prometheus_enabled'],
        metrics_endpoint=raw_config['monitoring']['metrics_endpoint'],
        health_check_interval_seconds=raw_config['monitoring']['health_check_interval_seconds'],
    )
    
    # Logging 파싱
    logging_cfg = LoggingConfig(
        level=raw_config['logging']['level'],
        file_path=raw_config['logging']['file_path'],
        rotation=raw_config['logging']['rotation'],
    )
    
    # Database 파싱
    database = DatabaseConfig(
        enabled=raw_config['database']['enabled'],
        host=raw_config['database'].get('host'),
        port=raw_config['database'].get('port'),
        name=raw_config['database'].get('name'),
    )
    
    # Cache 파싱
    cache = CacheConfig(
        redis_enabled=raw_config['cache']['redis_enabled'],
        market_data_ttl_ms=raw_config['cache']['market_data_ttl_ms'],
    )
    
    # Tuning 파싱 (D205-14)
    tuning_data = raw_config.get('tuning', {})
    tuning = TuningConfig(
        enabled=tuning_data.get('enabled', False),
        param_ranges=tuning_data.get('param_ranges', {}),
        sweep=tuning_data.get('sweep'),
        objective=tuning_data.get('objective'),
    )
    
    # ProfitCore 파싱 (D206-1)
    from arbitrage.v2.core.profit_core import ProfitCoreConfig, TunerConfig
    
    profit_core_data = raw_config.get('profit_core', {})
    profit_core = ProfitCoreConfig(
        default_price_krw=profit_core_data.get('default_price_krw'),
        default_price_usdt=profit_core_data.get('default_price_usdt'),
        price_sanity_min_krw=profit_core_data.get('price_sanity_min_krw', 0.0),
        price_sanity_max_krw=profit_core_data.get('price_sanity_max_krw', float('inf')),
        enable_sanity_check=profit_core_data.get('enable_sanity_check', True),
    )
    
    # Tuner 파싱 (D206-1)
    tuner_data = raw_config.get('tuner', {})
    tuner = TunerConfig(
        enabled=tuner_data.get('enabled', False),
        tuner_type=tuner_data.get('tuner_type', 'static'),
        param_overrides=tuner_data.get('param_overrides'),
    )
    
    # Meta 파싱
    meta = MetaConfig(
        version=raw_config['meta']['version'],
        config_name=raw_config['meta']['config_name'],
        created_at=raw_config['meta']['created_at'],
        description=raw_config['meta']['description'],
    )
    
    # Legacy 필드 추출
    cycle_interval_seconds = raw_config.get('cycle_interval_seconds', 1.0)
    max_concurrent_orders = raw_config.get('max_concurrent_orders', 1)
    dry_run = raw_config.get('dry_run', True)

    # V2Config 인스턴스 생성
    config = V2Config(
        mode=mode,
        execution_env=execution_env,
        execution=execution,
        exchanges=exchanges,
        universe=universe,
        strategy=strategy,
        cycle_interval_seconds=exec_data.get('cycle_interval_seconds', 10.0),
        max_concurrent_orders=exec_data.get('max_concurrent_orders', 5),
        dry_run=exec_data.get('dry_run', True),
        safety=safety,
        reporting=reporting,
        monitoring=monitoring,
        logging=logging_cfg,
        database=database,
        cache=cache,
        tuning=tuning,
        profit_core=profit_core,  # D206-1
        tuner=tuner,  # D206-1
        meta=meta,
    )

    # 검증
    config.validate()

    logger.info(f"[V2 Config] 로드 완료: {config_path}")
    logger.info(f"[V2 Config] Version: {meta.version}, Name: {meta.config_name}")
    
    return config


if __name__ == '__main__':
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    print(f"✅ Config 로드 성공: {config.meta.config_name}")
    print(f"✅ Break-even spread (upbit-binance): {config.get_break_even_spread_bps('upbit', 'binance'):.2f} bps")
