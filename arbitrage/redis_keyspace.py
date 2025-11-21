"""
Redis Keyspace Normalization (D72-2)

표준화된 Redis key 생성 및 관리.
모든 Redis 연산은 반드시 이 모듈의 KeyBuilder를 사용해야 함.

Key Format:
    arbitrage:{env}:{session_id}:{domain}:{symbol}:{field}

Example:
    arbitrage:development:session_123:state:BTC:position
    arbitrage:production:session_456:metrics:ETH:pnl
"""

from enum import Enum
from typing import Optional, Dict, Any
import re


class KeyDomain(Enum):
    """Redis key domain categories"""
    STATE = "state"              # Session/position state
    METRICS = "metrics"          # Performance metrics
    GUARD = "guard"              # RiskGuard state
    COOLDOWN = "cooldown"        # Trade cooldown
    PORTFOLIO = "portfolio"      # Portfolio aggregation
    SNAPSHOT = "snapshot"        # State snapshots
    WS = "ws"                    # WebSocket metadata


class TTLPolicy:
    """TTL policies for different key domains (seconds)"""
    
    # No TTL (persistent until explicit delete)
    STATE = None
    SNAPSHOT = None
    PORTFOLIO = None
    GUARD = None
    
    # Short TTL (transient data)
    COOLDOWN = 600          # 10 minutes
    WS_LATENCY = 30         # 30 seconds
    WS_TICK = 30            # 30 seconds
    METRICS_REALTIME = 60   # 1 minute
    
    # Medium TTL (cached data)
    METRICS_AGGREGATED = 3600  # 1 hour
    
    @classmethod
    def get_ttl(cls, domain: KeyDomain, field: Optional[str] = None) -> Optional[int]:
        """
        Get TTL for a given domain and field
        
        Args:
            domain: Key domain
            field: Specific field name (for granular TTL)
        
        Returns:
            TTL in seconds, or None for no expiration
        """
        if domain == KeyDomain.STATE:
            return cls.STATE
        elif domain == KeyDomain.SNAPSHOT:
            return cls.SNAPSHOT
        elif domain == KeyDomain.PORTFOLIO:
            return cls.PORTFOLIO
        elif domain == KeyDomain.GUARD:
            return cls.GUARD
        elif domain == KeyDomain.COOLDOWN:
            return cls.COOLDOWN
        elif domain == KeyDomain.WS:
            if field and 'latency' in field:
                return cls.WS_LATENCY
            elif field and 'tick' in field:
                return cls.WS_TICK
            return cls.WS_TICK
        elif domain == KeyDomain.METRICS:
            if field and 'realtime' in field:
                return cls.METRICS_REALTIME
            return cls.METRICS_AGGREGATED
        
        return None


class KeyBuilder:
    """
    Centralized Redis key builder
    
    모든 Redis key 생성은 반드시 이 클래스를 통해야 함.
    """
    
    PREFIX = "arbitrage"
    SEPARATOR = ":"
    
    # Key pattern validation
    # Format: arbitrage:env:session_id:domain[:symbol[:field]]
    # Three valid forms:
    # 1. arbitrage:env:session:domain
    # 2. arbitrage:env:session:domain:symbol
    # 3. arbitrage:env:session:domain:symbol:field
    KEY_PATTERN = re.compile(
        r'^arbitrage:(development|staging|production):([^:]+):(state|metrics|guard|cooldown|portfolio|snapshot|ws)(?::([^:]*)(?::(.+))?)?$'
    )
    
    def __init__(self, env: str, session_id: str):
        """
        Initialize KeyBuilder
        
        Args:
            env: Environment (development/staging/production)
            session_id: Session identifier
        """
        if env not in ['development', 'staging', 'production']:
            raise ValueError(f"Invalid environment: {env}")
        
        if not session_id or ':' in session_id:
            raise ValueError(f"Invalid session_id: {session_id}")
        
        self.env = env
        self.session_id = session_id
    
    def build(
        self,
        domain: KeyDomain,
        symbol: str = "",
        field: str = ""
    ) -> str:
        """
        Build a standardized Redis key
        
        Args:
            domain: Key domain
            symbol: Symbol name (optional, e.g., 'BTC', 'ETH')
            field: Field name (e.g., 'position', 'pnl')
        
        Returns:
            Standardized key string
        
        Example:
            >>> kb = KeyBuilder('development', 'session_123')
            >>> kb.build(KeyDomain.STATE, 'BTC', 'position')
            'arbitrage:development:session_123:state:BTC:position'
        """
        parts = [
            self.PREFIX,
            self.env,
            self.session_id,
            domain.value
        ]
        
        # Add symbol and field only if provided
        if symbol or field:  # At least one is provided
            parts.append(symbol if symbol else "")  # Can be empty string
            if field:
                parts.append(field)
        
        key = self.SEPARATOR.join(parts)
        return key
    
    def build_session_key(self) -> str:
        """Build session metadata key"""
        return self.build(KeyDomain.STATE, field="session")
    
    def build_position_key(self, symbol: str) -> str:
        """Build position state key"""
        return self.build(KeyDomain.STATE, symbol=symbol, field="position")
    
    def build_orders_key(self, symbol: str) -> str:
        """Build active orders key"""
        return self.build(KeyDomain.STATE, symbol=symbol, field="orders")
    
    def build_metrics_key(self, symbol: str, metric: str) -> str:
        """Build metrics key"""
        return self.build(KeyDomain.METRICS, symbol=symbol, field=metric)
    
    def build_portfolio_key(self) -> str:
        """Build portfolio aggregation key"""
        return self.build(KeyDomain.PORTFOLIO, field="total")
    
    def build_guard_key(self) -> str:
        """Build RiskGuard state key"""
        return self.build(KeyDomain.GUARD, field="state")
    
    def build_cooldown_key(self, symbol: str) -> str:
        """Build trade cooldown key"""
        return self.build(KeyDomain.COOLDOWN, symbol=symbol, field="trade")
    
    def build_snapshot_key(self, snapshot_id: str) -> str:
        """Build snapshot key"""
        return self.build(KeyDomain.SNAPSHOT, field=snapshot_id)
    
    def build_ws_key(self, exchange: str, metric: str) -> str:
        """Build WebSocket metadata key"""
        return self.build(KeyDomain.WS, symbol=exchange, field=metric)
    
    @classmethod
    def validate_key(cls, key: str) -> bool:
        """
        Validate if a key follows the standard format
        
        Args:
            key: Redis key to validate
        
        Returns:
            True if valid, False otherwise
        """
        return bool(cls.KEY_PATTERN.match(key))
    
    @classmethod
    def parse_key(cls, key: str) -> Optional[Dict[str, str]]:
        """
        Parse a standardized key into components
        
        Args:
            key: Redis key to parse
        
        Returns:
            Dict with env, session_id, domain, symbol, field
            or None if invalid
        """
        match = cls.KEY_PATTERN.match(key)
        if not match:
            return None
        
        return {
            'env': match.group(1),
            'session_id': match.group(2),
            'domain': match.group(3),
            'symbol': match.group(4),
            'field': match.group(5)
        }
    
    def get_ttl(self, domain: KeyDomain, field: Optional[str] = None) -> Optional[int]:
        """Get TTL for a domain/field combination"""
        return TTLPolicy.get_ttl(domain, field)
    
    def get_all_session_keys_pattern(self) -> str:
        """Get pattern to match all keys for this session"""
        return f"{self.PREFIX}:{self.env}:{self.session_id}:*"
    
    def get_domain_keys_pattern(self, domain: KeyDomain) -> str:
        """Get pattern to match all keys for a specific domain"""
        return f"{self.PREFIX}:{self.env}:{self.session_id}:{domain.value}:*"


class KeyspaceValidator:
    """Validate Redis keyspace compliance"""
    
    @staticmethod
    def audit_keys(redis_client, expected_pattern: str = "arbitrage:*") -> Dict[str, Any]:
        """
        Audit all Redis keys for compliance
        
        Args:
            redis_client: Redis client instance
            expected_pattern: Pattern to scan
        
        Returns:
            Audit report with compliance statistics
        """
        all_keys = redis_client.keys(expected_pattern)
        
        valid_keys = []
        invalid_keys = []
        
        for key in all_keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if KeyBuilder.validate_key(key_str):
                valid_keys.append(key_str)
            else:
                invalid_keys.append(key_str)
        
        # Parse valid keys for statistics
        domain_breakdown = {}
        env_breakdown = {}
        
        for key in valid_keys:
            parsed = KeyBuilder.parse_key(key)
            if parsed:
                domain = parsed['domain']
                env = parsed['env']
                
                domain_breakdown[domain] = domain_breakdown.get(domain, 0) + 1
                env_breakdown[env] = env_breakdown.get(env, 0) + 1
        
        return {
            'total_keys': len(all_keys),
            'valid_keys': len(valid_keys),
            'invalid_keys': len(invalid_keys),
            'compliance_rate': len(valid_keys) / len(all_keys) * 100 if all_keys else 100.0,
            'invalid_key_list': invalid_keys[:20],  # First 20 invalid keys
            'domain_breakdown': domain_breakdown,
            'env_breakdown': env_breakdown
        }
