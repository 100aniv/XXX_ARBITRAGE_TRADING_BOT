#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Service Script (PHASE D – MODULE D3)
=========================================

안전한 daemon-like 루프 (paper mode only).

특징:
- 설정 파일 로드
- 저장소 초기화
- Redis heartbeat 작성 (선택적)
- 메트릭 수집 및 로깅
- Graceful shutdown (Ctrl+C / SIGTERM)

사용법:
    python scripts/run_bot_service.py
    python scripts/run_bot_service.py --config config/base.yml
    python scripts/run_bot_service.py --interval 10 --verbose

옵션:
    --config: 설정 파일 경로 (기본값: config/base.yml)
    --interval: 루프 간격 (초, 기본값: 30)
    --verbose: 상세 로그 출력
"""

import sys
import logging
import argparse
import signal
import time
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.storage import get_storage
from arbitrage.redis_client import get_redis_client
from arbitrage.metrics import get_metrics_collector, format_metrics_summary
from arbitrage.health import check_redis, check_postgres, check_csv_storage


def load_config(config_path: str) -> dict:
    """YAML 설정 파일 로드
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        설정 딕셔너리
    """
    import yaml
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except UnicodeDecodeError:
        # Windows 환경에서 cp949 인코딩 폴백
        with open(config_path, 'r', encoding='cp949') as f:
            return yaml.safe_load(f)


class BotService:
    """봇 서비스 클래스"""
    
    def __init__(self, config: dict, interval: int = 30, verbose: bool = False, once: bool = False):
        """
        Args:
            config: 설정 딕셔너리
            interval: 루프 간격 (초)
            verbose: 상세 로그 출력
            once: 한 번만 실행 후 종료
        """
        self.config = config
        self.interval = interval
        self.once = once
        self.running = False
        
        # 로깅 설정
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        self.logger = logging.getLogger("arbitrage.bot_service")
        
        # 저장소 초기화
        self.storage = None
        self.redis_client = None
        self.metrics_collector = None
        
        # 신호 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """신호 핸들러 (Ctrl+C, SIGTERM)"""
        self.logger.info(f"[BOT] Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def initialize(self) -> bool:
        """서비스 초기화
        
        Returns:
            성공 여부
        """
        try:
            self.logger.info("[BOT] Initializing bot service...")
            
            # 저장소 초기화
            self.storage = get_storage(self.config)
            self.logger.info(f"[BOT] Storage initialized: {type(self.storage).__name__}")
            
            # Redis 클라이언트 초기화
            self.redis_client = get_redis_client(self.config)
            self.logger.info(f"[BOT] Redis client initialized (available={self.redis_client.available})")
            
            # 메트릭 수집기 초기화
            self.metrics_collector = get_metrics_collector(self.storage)
            self.logger.info("[BOT] Metrics collector initialized")
            
            # 환경 정보 로깅
            fx_config = self.config.get("fx", {})
            storage_config = self.config.get("storage", {})
            redis_config = self.config.get("redis", {})
            
            self.logger.info(
                f"[BOT] Config: "
                f"fx_mode={fx_config.get('mode', 'static')} "
                f"storage_backend={storage_config.get('backend', 'csv')} "
                f"redis_enabled={redis_config.get('enabled', False)}"
            )
            
            return True
        except Exception as e:
            self.logger.error(f"[BOT] Initialization failed: {e}", exc_info=True)
            return False
    
    def write_heartbeat(self) -> None:
        """Redis heartbeat 작성"""
        if not self.redis_client or not self.redis_client.available:
            return
        
        try:
            redis_config = self.config.get("redis", {})
            ttl = redis_config.get("health_ttl_seconds", 60)
            self.redis_client.set_heartbeat("bot_service", ttl=ttl)
        except Exception as e:
            self.logger.debug(f"[BOT] Failed to write heartbeat: {e}")
    
    def collect_metrics(self) -> None:
        """메트릭 수집 및 로깅"""
        try:
            if self.metrics_collector:
                snapshot = self.metrics_collector.collect()
                summary = format_metrics_summary(snapshot)
                self.logger.info(summary)
        except Exception as e:
            self.logger.debug(f"[BOT] Failed to collect metrics: {e}")
    
    def run_iteration(self) -> None:
        """한 번의 반복 실행
        
        PHASE D3: 간단한 루프 (실제 거래 로직 없음)
        PHASE D4: 실제 거래 로직 추가
        """
        try:
            # Heartbeat 작성
            self.write_heartbeat()
            
            # 메트릭 수집
            self.collect_metrics()
            
            # 상태 로깅
            symbols = [s.get("name", "?") for s in self.config.get("symbols", [])]
            storage_backend = self.config.get("storage", {}).get("backend", "csv")
            redis_enabled = self.config.get("redis", {}).get("enabled", False)
            
            self.logger.debug(
                f"[BOT] heartbeat - "
                f"symbols={symbols} "
                f"backend={storage_backend} "
                f"redis={'enabled' if redis_enabled else 'disabled'}"
            )
        except Exception as e:
            self.logger.error(f"[BOT] Iteration failed: {e}", exc_info=True)
    
    def run(self) -> int:
        """메인 루프 실행
        
        Returns:
            종료 코드 (0=성공, 1=실패)
        """
        # 초기화
        if not self.initialize():
            self.logger.error("[BOT] Initialization failed, exiting")
            return 1
        
        self.running = True
        iteration_count = 0
        
        mode = "once" if self.once else "loop"
        self.logger.info(
            f"[BOT] Starting bot service ({mode}, interval={self.interval}s, mode=paper)"
        )
        
        try:
            while self.running:
                iteration_count += 1
                
                # 반복 실행
                self.run_iteration()
                
                # --once 옵션이면 한 번만 실행
                if self.once:
                    self.running = False
                    break
                
                # 대기
                if self.running:
                    time.sleep(self.interval)
        
        except KeyboardInterrupt:
            self.logger.info("[BOT] Interrupted by user")
        except Exception as e:
            self.logger.error(f"[BOT] Unexpected error: {e}", exc_info=True)
            return 1
        finally:
            self.logger.info(
                f"[BOT] Shutting down (completed {iteration_count} iterations)"
            )
        
        return 0


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Arbitrage-Lite Bot Service (PHASE D – MODULE D3)"
    )
    parser.add_argument(
        "--config",
        default="config/base.yml",
        help="설정 파일 경로 (기본값: config/base.yml)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="루프 간격 (초, 기본값: 30)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 로그 출력"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="한 번만 실행 후 종료"
    )
    
    args = parser.parse_args()
    
    # 설정 로드
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return 1
    
    # 서비스 실행
    service = BotService(config, interval=args.interval, verbose=args.verbose, once=args.once)
    return service.run()


if __name__ == "__main__":
    sys.exit(main())
