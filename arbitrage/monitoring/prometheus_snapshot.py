# -*- coding: utf-8 -*-
"""
D77-5: Prometheus 메트릭 스냅샷 저장 모듈

Prometheus /metrics 엔드포인트에서 현재 메트릭을 가져와서 파일로 저장.
C5 Acceptance Criteria (Prometheus 정상 동작) 검증용.

Features:
- HTTP GET으로 /metrics 엔드포인트 조회
- 응답을 파일로 저장
- 실패 시 로깅만 하고 예외를 던지지 않음 (graceful degradation)
- 테스트 친화적 설계

Usage:
    from arbitrage.monitoring.prometheus_snapshot import save_prometheus_snapshot
    
    snapshot_path = save_prometheus_snapshot(
        run_id="run_20251203_164441",
        output_dir=Path("logs/d77-4/run_20251203_164441"),
        metrics_url="http://localhost:9100/metrics"
    )
    
    if snapshot_path:
        print(f"Snapshot saved: {snapshot_path}")
    else:
        print("Snapshot failed (metrics server not available)")
"""

import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def save_prometheus_snapshot(
    run_id: str,
    output_dir: Path,
    metrics_url: str = "http://localhost:9100/metrics",
    timeout: int = 10,
) -> Optional[Path]:
    """
    Prometheus /metrics 엔드포인트에서 현재 메트릭을 가져와서 파일로 저장.
    
    Args:
        run_id: 실행 ID (로깅용)
        output_dir: 출력 디렉토리 경로
        metrics_url: Prometheus metrics 엔드포인트 URL
        timeout: HTTP 요청 타임아웃 (초)
    
    Returns:
        저장된 파일 경로 (성공 시) 또는 None (실패 시)
    
    Note:
        실패 시 예외를 던지지 않고 None을 반환합니다.
        이는 메트릭 수집 실패가 전체 플로우를 중단시키지 않도록 하기 위함입니다.
    """
    logger.info(f"[Prometheus Snapshot] 메트릭 스냅샷 저장 시작 (run_id={run_id})")
    logger.info(f"[Prometheus Snapshot] Metrics URL: {metrics_url}")
    
    try:
        # 출력 디렉토리 생성
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # HTTP GET 요청
        start_time = time.time()
        response = requests.get(metrics_url, timeout=timeout)
        elapsed = time.time() - start_time
        
        logger.info(f"[Prometheus Snapshot] HTTP GET 완료 (status={response.status_code}, elapsed={elapsed:.2f}s)")
        
        # 상태 코드 체크
        if response.status_code != 200:
            logger.warning(
                f"[Prometheus Snapshot] Non-200 status code: {response.status_code}. "
                "Metrics server may not be running."
            )
            return None
        
        # Content-Type 체크 (optional, but good practice)
        content_type = response.headers.get("Content-Type", "")
        if "text/plain" not in content_type and "text" not in content_type:
            logger.warning(
                f"[Prometheus Snapshot] Unexpected Content-Type: {content_type}. "
                "Expected 'text/plain' or similar."
            )
        
        # 응답 본문 가져오기
        metrics_text = response.text
        if not metrics_text or len(metrics_text) == 0:
            logger.warning("[Prometheus Snapshot] Empty response body. No metrics to save.")
            return None
        
        # 파일로 저장
        snapshot_path = output_dir / "prometheus_metrics.prom"
        snapshot_path.write_text(metrics_text, encoding='utf-8')
        
        # 메트릭 개수 세기 (대략적인 추정)
        metric_lines = [line for line in metrics_text.split('\n') if line and not line.startswith('#')]
        metric_count = len(metric_lines)
        
        logger.info(
            f"[Prometheus Snapshot] 스냅샷 저장 완료: {snapshot_path} "
            f"(size={len(metrics_text)} bytes, ~{metric_count} metrics)"
        )
        
        return snapshot_path
    
    except requests.exceptions.Timeout:
        logger.warning(
            f"[Prometheus Snapshot] HTTP 요청 타임아웃 ({timeout}s). "
            "Metrics server may not be responding."
        )
        return None
    
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"[Prometheus Snapshot] 연결 실패: {e}. "
            "Metrics server may not be running."
        )
        return None
    
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Prometheus Snapshot] HTTP 요청 실패: {e}")
        return None
    
    except IOError as e:
        logger.error(f"[Prometheus Snapshot] 파일 저장 실패: {e}")
        return None
    
    except Exception as e:
        logger.error(f"[Prometheus Snapshot] 예상치 못한 오류: {e}", exc_info=True)
        return None
