"""
Logging & Monitoring MVP for D72-4

Central logging system with multiple backends:
- File logging
- Console logging
- Redis Stream (real-time)
- PostgreSQL (persistent storage)

Usage:
    from arbitrage.logging_manager import LoggingManager, LogLevel, LogCategory
    
    logger = LoggingManager.get_instance()
    logger.log(
        level=LogLevel.INFO,
        component="ArbitrageEngine",
        category=LogCategory.TRADE,
        message="Trade executed",
        payload={"symbol": "BTCUSDT", "price": 50000}
    )
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field

import redis
import psycopg2
from psycopg2.extras import Json


class LogLevel(str, Enum):
    """Log severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log event categories"""
    ENGINE = "engine"
    TRADE = "trade"
    GUARD = "guard"
    RISK = "risk"
    EXCHANGE = "exchange"
    POSITION = "position"
    SYNC = "sync"
    WEBSOCKET = "websocket"
    METRICS = "metrics"
    SYSTEM = "system"


@dataclass
class LogRecord:
    """Structured log record"""
    timestamp: str
    level: str
    component: str
    category: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class FileLogger:
    """File-based logger"""
    
    def __init__(self, log_dir: str = "logs", env: str = "development"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.env = env
        
        # Create rotating log file
        self.log_file = self.log_dir / f"arbitrage_{env}.log"
        
        # Setup Python logger
        self.logger = logging.getLogger(f"arbitrage_{env}")
        self.logger.setLevel(logging.DEBUG if env == "development" else logging.INFO)
        
        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        
        self.logger.addHandler(fh)
    
    def log(self, record: LogRecord):
        """Write log record to file"""
        log_level = getattr(logging, record.level, logging.INFO)
        self.logger.log(
            log_level,
            f"[{record.component}] [{record.category}] {record.message} | {json.dumps(record.payload)}"
        )


class ConsoleLogger:
    """Console logger with color support"""
    
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m", # Magenta
        "RESET": "\033[0m"
    }
    
    def __init__(self, env: str = "development"):
        self.env = env
        self.enabled = env in ["development", "staging"]
    
    def log(self, record: LogRecord):
        """Print log to console"""
        if not self.enabled:
            return
        
        color = self.COLORS.get(record.level, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        
        timestamp = datetime.fromisoformat(record.timestamp).strftime("%H:%M:%S")
        
        print(
            f"{color}[{timestamp}] [{record.level:8s}] "
            f"[{record.component:20s}] [{record.category:10s}] "
            f"{record.message}{reset}"
        )
        
        if record.payload and self.env == "development":
            print(f"  └─ {json.dumps(record.payload, indent=2)}")


class RedisLogger:
    """Redis Stream logger for real-time monitoring"""
    
    def __init__(self, redis_client: redis.Redis, env: str = "development"):
        self.redis = redis_client
        self.env = env
        self.stream_key = f"arbitrage:logs:{env}"
        self.metrics_key = f"arbitrage:metrics:{env}"
        self.ttl = 120  # 2 minutes
    
    def log(self, record: LogRecord):
        """Write log to Redis Stream"""
        try:
            # Convert record to dict and serialize payload
            data = record.to_dict()
            # Serialize payload to JSON string
            if isinstance(data.get('payload'), dict):
                data['payload'] = json.dumps(data['payload'])
            
            # Add to stream
            self.redis.xadd(
                self.stream_key,
                data,
                maxlen=1000  # Keep last 1000 entries
            )
            
            # Update metrics if this is a metrics event
            if record.category == LogCategory.METRICS:
                self._update_metrics(record)
        except Exception as e:
            # Silent fail - don't break application if Redis is down
            print(f"[RedisLogger] Failed to write log: {e}")
    
    def _update_metrics(self, record: LogRecord):
        """Update rolling metrics"""
        if record.session_id:
            metrics_key = f"{self.metrics_key}:{record.session_id}"
        else:
            metrics_key = self.metrics_key
        
        # Store as hash with TTL
        self.redis.hset(metrics_key, mapping=record.payload)
        self.redis.expire(metrics_key, self.ttl)
    
    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs from stream"""
        try:
            entries = self.redis.xrevrange(self.stream_key, count=count)
            logs = []
            for msg_id, data in entries:
                log_data = {k.decode(): v.decode() for k, v in data.items()}
                if 'payload' in log_data:
                    log_data['payload'] = json.loads(log_data['payload'])
                logs.append(log_data)
            return logs
        except Exception as e:
            print(f"[RedisLogger] Failed to read logs: {e}")
            return []
    
    def get_metrics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current metrics"""
        try:
            if session_id:
                metrics_key = f"{self.metrics_key}:{session_id}"
            else:
                metrics_key = self.metrics_key
            
            metrics = self.redis.hgetall(metrics_key)
            return {k.decode(): v.decode() for k, v in metrics.items()}
        except Exception as e:
            print(f"[RedisLogger] Failed to read metrics: {e}")
            return {}


class PostgresLogger:
    """PostgreSQL logger for persistent storage"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
        except Exception as e:
            print(f"[PostgresLogger] Failed to connect to database: {e}")
    
    def log(self, record: LogRecord):
        """Write log to PostgreSQL"""
        if not self.conn:
            self._connect()
        
        if not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO system_logs 
                    (created_at, level, component, category, message, json_payload, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.timestamp,
                        record.level,
                        record.component,
                        record.category,
                        record.message,
                        Json(record.payload),
                        record.session_id
                    )
                )
            self.conn.commit()
        except Exception as e:
            print(f"[PostgresLogger] Failed to write log: {e}")
            self.conn.rollback()
            # Try to reconnect
            self._connect()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class LoggingManager:
    """
    Central logging manager (Singleton)
    
    Manages multiple logging backends and routing logic.
    """
    
    _instance: Optional['LoggingManager'] = None
    
    def __init__(
        self,
        env: str = "development",
        redis_config: Optional[Dict[str, Any]] = None,
        db_config: Optional[Dict[str, Any]] = None,
        log_dir: str = "logs"
    ):
        if LoggingManager._instance is not None:
            raise RuntimeError("LoggingManager is a singleton. Use get_instance()")
        
        self.env = env
        self.session_id: Optional[str] = None
        
        # Determine log level based on environment
        self.min_level = self._get_min_level(env)
        
        # Initialize loggers
        self.file_logger = FileLogger(log_dir, env)
        self.console_logger = ConsoleLogger(env)
        
        # Redis logger (optional)
        self.redis_logger: Optional[RedisLogger] = None
        if redis_config:
            try:
                redis_client = redis.Redis(**redis_config, decode_responses=False)
                redis_client.ping()
                self.redis_logger = RedisLogger(redis_client, env)
            except Exception as e:
                print(f"[LoggingManager] Redis logger disabled: {e}")
        
        # Postgres logger (optional)
        self.postgres_logger: Optional[PostgresLogger] = None
        if db_config:
            try:
                self.postgres_logger = PostgresLogger(db_config)
            except Exception as e:
                print(f"[LoggingManager] Postgres logger disabled: {e}")
        
        LoggingManager._instance = self
    
    @classmethod
    def get_instance(cls) -> 'LoggingManager':
        """Get singleton instance"""
        if cls._instance is None:
            raise RuntimeError("LoggingManager not initialized. Call initialize() first.")
        return cls._instance
    
    @classmethod
    def initialize(
        cls,
        env: str = "development",
        redis_config: Optional[Dict[str, Any]] = None,
        db_config: Optional[Dict[str, Any]] = None,
        log_dir: str = "logs"
    ) -> 'LoggingManager':
        """Initialize singleton instance"""
        if cls._instance is None:
            cls(env, redis_config, db_config, log_dir)
        return cls._instance
    
    def set_session_id(self, session_id: str):
        """Set current session ID for all logs"""
        self.session_id = session_id
    
    def _get_min_level(self, env: str) -> int:
        """Get minimum log level based on environment"""
        level_map = {
            "development": 10,  # DEBUG
            "staging": 20,      # INFO
            "production": 30    # WARNING
        }
        return level_map.get(env, 20)
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if log level meets minimum threshold"""
        level_values = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50
        }
        return level_values.get(level, 20) >= self.min_level
    
    def log(
        self,
        level: LogLevel,
        component: str,
        category: LogCategory,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """
        Log an event
        
        Args:
            level: Log severity level
            component: Component name (e.g., "ArbitrageEngine")
            category: Event category
            message: Human-readable message
            payload: Additional structured data
            session_id: Optional session ID (overrides default)
        """
        if not self._should_log(level):
            return
        
        # Create log record
        record = LogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.value,
            component=component,
            category=category.value,
            message=message,
            payload=payload or {},
            session_id=session_id or self.session_id
        )
        
        # Route to all loggers
        self.file_logger.log(record)
        self.console_logger.log(record)
        
        if self.redis_logger:
            self.redis_logger.log(record)
        
        if self.postgres_logger and level in [LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]:
            # Only persist warnings and errors to database
            self.postgres_logger.log(record)
    
    def debug(self, component: str, category: LogCategory, message: str, **kwargs):
        """Log debug message"""
        self.log(LogLevel.DEBUG, component, category, message, kwargs)
    
    def info(self, component: str, category: LogCategory, message: str, **kwargs):
        """Log info message"""
        self.log(LogLevel.INFO, component, category, message, kwargs)
    
    def warning(self, component: str, category: LogCategory, message: str, **kwargs):
        """Log warning message"""
        self.log(LogLevel.WARNING, component, category, message, kwargs)
    
    def error(self, component: str, category: LogCategory, message: str, **kwargs):
        """Log error message"""
        self.log(LogLevel.ERROR, component, category, message, kwargs)
    
    def critical(self, component: str, category: LogCategory, message: str, **kwargs):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, component, category, message, kwargs)
    
    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs from Redis"""
        if self.redis_logger:
            return self.redis_logger.get_recent_logs(count)
        return []
    
    def get_metrics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current metrics from Redis"""
        if self.redis_logger:
            return self.redis_logger.get_metrics(session_id)
        return {}
    
    def shutdown(self):
        """Shutdown all loggers"""
        if self.postgres_logger:
            self.postgres_logger.close()
        
        LoggingManager._instance = None
