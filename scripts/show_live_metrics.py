#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D21 Observability — Show Live Metrics

Redis에 저장된 실시간 메트릭을 CLI에서 조회하는 스크립트.

사용법:
    python scripts/show_live_metrics.py [--mode live|paper|shadow] [--env local|docker]

예시:
    # Live 모드 메트릭 조회 (Docker 환경)
    python scripts/show_live_metrics.py --mode live --env docker
    
    # Paper 모드 메트릭 조회 (Local 환경)
    python scripts/show_live_metrics.py --mode paper --env local
"""

import argparse
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.state_manager import StateManager

# 로깅 설정
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsViewer:
    """메트릭 조회 및 표시"""
    
    def __init__(self, mode: str = "live", env: str = "docker"):
        """
        Args:
            mode: 모드 (live, paper, shadow)
            env: 환경 (local, docker)
        """
        self.mode = mode
        self.env = env
        self.namespace = f"{mode}:{env}"
        
        # Redis 정보 읽기
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # StateManager 초기화
        self.state_manager = StateManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            namespace=self.namespace,
            enabled=True,
            key_prefix="arbitrage"
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 조회"""
        metrics = {}
        
        # 핵심 메트릭 조회
        metrics["trades_total"] = self.state_manager.get_stat("trades_total")
        metrics["trades_today"] = self.state_manager.get_stat("trades_today")
        metrics["safety_violations_total"] = self.state_manager.get_stat("safety_violations_total")
        metrics["circuit_breaker_triggers_total"] = self.state_manager.get_stat("circuit_breaker_triggers_total")
        
        # 하트비트 조회
        heartbeat = self.state_manager.get_heartbeat("live_trader")
        metrics["last_heartbeat"] = heartbeat or "N/A"
        
        # 포트폴리오 상태 조회
        portfolio = self.state_manager.get_portfolio_state()
        if portfolio:
            metrics["total_balance"] = portfolio.get("total_balance", "N/A")
            metrics["available_balance"] = portfolio.get("available_balance", "N/A")
            metrics["total_position_value"] = portfolio.get("total_position_value", "N/A")
        
        # 메트릭 해시 조회
        live_metrics = self.state_manager.get_metrics()
        metrics.update(live_metrics)
        
        return metrics
    
    def print_metrics_table(self, metrics: Dict[str, Any]) -> None:
        """메트릭을 테이블 형태로 출력"""
        print(f"\n{'='*70}")
        print(f"[METRICS] namespace={self.namespace}")
        print(f"{'='*70}\n")
        
        # 메트릭 그룹별 출력
        groups = {
            "거래 통계": [
                "trades_total",
                "trades_today"
            ],
            "안전 메트릭": [
                "safety_violations_total",
                "circuit_breaker_triggers_total"
            ],
            "포트폴리오": [
                "total_balance",
                "available_balance",
                "total_position_value"
            ],
            "시스템": [
                "last_heartbeat"
            ]
        }
        
        for group_name, keys in groups.items():
            print(f"[{group_name}]")
            for key in keys:
                value = metrics.get(key, "N/A")
                print(f"  {key:.<40} {value}")
            print()
        
        # 추가 메트릭 (그룹에 속하지 않은 메트릭)
        used_keys = set()
        for keys in groups.values():
            used_keys.update(keys)
        
        additional = {k: v for k, v in metrics.items() if k not in used_keys}
        if additional:
            print(f"[추가 메트릭]")
            for key, value in additional.items():
                print(f"  {key:.<40} {value}")
            print()
        
        print(f"{'='*70}")
        print(f"조회 시간: {datetime.now().isoformat()}")
        print(f"{'='*70}\n")
    
    def print_metrics_json(self, metrics: Dict[str, Any]) -> None:
        """메트릭을 JSON 형태로 출력"""
        output = {
            "namespace": self.namespace,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    
    def print_metrics_log(self, metrics: Dict[str, Any]) -> None:
        """메트릭을 로그 형태로 출력"""
        print(f"\n[METRICS] namespace={self.namespace}")
        for key, value in metrics.items():
            print(f"[METRICS] {key}={value}")
        print()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D21 Observability — Show Live Metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Live 모드 메트릭 조회 (Docker 환경)
  python scripts/show_live_metrics.py --mode live --env docker
  
  # Paper 모드 메트릭 조회 (Local 환경)
  python scripts/show_live_metrics.py --mode paper --env local
  
  # JSON 형태로 출력
  python scripts/show_live_metrics.py --mode live --env docker --format json
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["live", "paper", "shadow"],
        default="live",
        help="모드 (기본값: live)"
    )
    
    parser.add_argument(
        "--env",
        choices=["local", "docker"],
        default="docker",
        help="환경 (기본값: docker)"
    )
    
    parser.add_argument(
        "--format",
        choices=["table", "json", "log"],
        default="table",
        help="출력 형식 (기본값: table)"
    )
    
    args = parser.parse_args()
    
    try:
        # 메트릭 조회
        viewer = MetricsViewer(mode=args.mode, env=args.env)
        metrics = viewer.get_metrics()
        
        # 형식에 따라 출력
        if args.format == "json":
            viewer.print_metrics_json(metrics)
        elif args.format == "log":
            viewer.print_metrics_log(metrics)
        else:  # table
            viewer.print_metrics_table(metrics)
        
        return 0
    
    except Exception as e:
        logger.error(f"메트릭 조회 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
