#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health Check Script (PHASE D – MODULE D2)
==========================================

시스템 헬스 체크 및 모니터링 스크립트.

사용법:
    python scripts/run_health_check.py
    python scripts/run_health_check.py --config config/base.yml
    python scripts/run_health_check.py --verbose

옵션:
    --config: 설정 파일 경로 (기본값: config/base.yml)
    --verbose: 상세 로그 출력
"""

import sys
import logging
import argparse
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.health import (
    check_redis,
    check_postgres,
    check_csv_storage,
    aggregate_status,
    format_health_report
)


def load_config(config_path: str) -> dict:
    """YAML 설정 파일 로드
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        설정 딕셔너리
    """
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Arbitrage-Lite Health Check (PHASE D – MODULE D2)"
    )
    parser.add_argument(
        "--config",
        default="config/base.yml",
        help="설정 파일 경로 (기본값: config/base.yml)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 로그 출력"
    )
    
    args = parser.parse_args()
    
    # 로깅 설정
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # 설정 로드
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return 1
    
    # 헬스 체크 실행
    statuses = [
        check_redis(config),
        check_postgres(config),
        check_csv_storage(config),
    ]
    
    # 리포트 출력
    print(format_health_report(statuses))
    
    # 종료 코드 결정
    overall = aggregate_status(statuses)
    if overall == "ERROR":
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
