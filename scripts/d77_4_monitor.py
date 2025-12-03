#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-4 Real-time Monitor - 완전 자동화 4대 원칙 (3)

실행 중 실시간 모니터링 및 자동 중단:
- 로그 스트림 ERROR/CRITICAL/Traceback 패턴 감지
- Prometheus /metrics 주기적 폴링
- 즉시 중단 조건 발동 시 Runner 프로세스 종료
"""

import json
import logging
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class D77Monitor:
    """D77-4 실시간 모니터 (병렬 실행)"""
    
    # 즉시 중단 조건 (Critical)
    STOP_CONDITIONS = {
        "crash": {"pattern": r"Traceback \(most recent call last\):", "count_threshold": 1},
        "dlq": {"metric": "alert_dlq_total", "threshold": 0, "operator": ">"},
        "notifier_down": {"metric": "notifier_available", "threshold": 0.5, "operator": "<"},
        "latency_p99": {"metric": "cross_loop_latency_seconds", "quantile": 0.99, "threshold": 0.1, "duration": 300},  # 100ms, 5분 지속
        "cpu_high": {"metric": "process_cpu_usage_percent", "threshold": 80, "duration": 600},  # 80%, 10분 지속
    }
    
    def __init__(
        self,
        project_root: Path,
        run_id: str,
        runner_pid: int,
        log_file: Path,
        metrics_url: str = "http://localhost:9100/metrics",
        check_interval: int = 10
    ):
        self.project_root = project_root
        self.run_id = run_id
        self.runner_pid = runner_pid
        self.log_file = log_file
        self.metrics_url = metrics_url
        self.check_interval = check_interval
        
        self.log_dir = project_root / "logs" / "d77-4" / run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._setup_logging()
        
        # 상태 추적
        self.start_time = time.time()
        self.stop_reason = None
        self.metrics_history = []
        self.log_patterns = {
            "ERROR": 0,
            "CRITICAL": 0,
            "Traceback": 0,
            "DLQ": 0
        }
    
    def _setup_logging(self):
        """로깅 핸들러 추가"""
        log_file = self.log_dir / "monitor.log"
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    def monitor_until_stop(self, max_duration: int = 3600) -> Dict:
        """모니터링 시작 (max_duration 초 또는 중단 조건 발생 시까지)
        
        Args:
            max_duration: 최대 모니터링 시간 (초)
        
        Returns:
            모니터링 결과 딕셔너리
        """
        logger.info(f"[D77-4 Monitor] 시작 (PID={self.runner_pid}, interval={self.check_interval}s)")
        
        # 로그 파일 tail 포인터 초기화
        log_position = 0
        if self.log_file.exists():
            log_position = self.log_file.stat().st_size
        
        iterations = 0
        latency_violations = []
        cpu_violations = []
        
        while True:
            elapsed = time.time() - self.start_time
            if elapsed > max_duration:
                logger.info(f"최대 모니터링 시간 도달 ({max_duration}s)")
                break
            
            # Runner 프로세스 생존 확인
            if not self._check_runner_alive():
                self.stop_reason = "runner_exited"
                logger.warning("Runner 프로세스 종료 감지")
                break
            
            # 로그 스트림 체크
            log_position = self._check_log_stream(log_position)
            
            # Prometheus /metrics 체크
            metrics = self._fetch_metrics()
            if metrics:
                self.metrics_history.append({
                    "timestamp": time.time(),
                    "metrics": metrics
                })
            
            # 중단 조건 체크
            stop_reason = self._check_stop_conditions(metrics, latency_violations, cpu_violations)
            if stop_reason:
                self.stop_reason = stop_reason
                logger.error(f"중단 조건 발동: {stop_reason}")
                self._terminate_runner()
                break
            
            iterations += 1
            time.sleep(self.check_interval)
        
        # 모니터링 요약 저장
        summary = self._generate_summary(elapsed, iterations)
        self._save_summary(summary)
        
        logger.info(f"[D77-4 Monitor] 종료 (총 {elapsed:.1f}s, {iterations}회 체크)")
        return summary
    
    def _check_runner_alive(self) -> bool:
        """Runner 프로세스 생존 확인"""
        if not psutil:
            return True  # psutil 없으면 낙관적 가정
        
        try:
            proc = psutil.Process(self.runner_pid)
            return proc.is_running()
        except psutil.NoSuchProcess:
            return False
    
    def _check_log_stream(self, last_position: int) -> int:
        """로그 파일에서 새 라인 읽고 패턴 감지
        
        Args:
            last_position: 마지막 읽은 위치
        
        Returns:
            새 위치
        """
        if not self.log_file.exists():
            return last_position
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_position)
                new_lines = f.readlines()
                new_position = f.tell()
            
            for line in new_lines:
                for pattern_name, count in self.log_patterns.items():
                    if pattern_name in line:
                        self.log_patterns[pattern_name] += 1
                        logger.debug(f"패턴 발견: {pattern_name} (총 {self.log_patterns[pattern_name]}회)")
            
            return new_position
        except Exception as e:
            logger.warning(f"로그 스트림 체크 예외: {e}")
            return last_position
    
    def _fetch_metrics(self) -> Optional[Dict]:
        """Prometheus /metrics 엔드포인트 폴링
        
        Returns:
            메트릭 딕셔너리 (실패 시 None)
        """
        if not requests:
            return None
        
        try:
            resp = requests.get(self.metrics_url, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"/metrics 응답 실패: {resp.status_code}")
                return None
            
            # 간단한 파싱 (TYPE/HELP 제외하고 메트릭만 추출)
            metrics = {}
            for line in resp.text.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    try:
                        metric_value = float(parts[1])
                        metrics[metric_name] = metric_value
                    except ValueError:
                        pass
            
            return metrics
        except requests.RequestException as e:
            logger.warning(f"/metrics 요청 예외: {e}")
            return None
    
    def _check_stop_conditions(
        self,
        metrics: Optional[Dict],
        latency_violations: List[float],
        cpu_violations: List[float]
    ) -> Optional[str]:
        """중단 조건 체크
        
        Args:
            metrics: 현재 메트릭
            latency_violations: Latency 위반 타임스탬프 리스트
            cpu_violations: CPU 위반 타임스탬프 리스트
        
        Returns:
            중단 이유 (없으면 None)
        """
        # Crash 체크
        if self.log_patterns["Traceback"] >= self.STOP_CONDITIONS["crash"]["count_threshold"]:
            return "crash_detected"
        
        if not metrics:
            return None
        
        # DLQ 체크
        dlq_count = metrics.get("alert_dlq_total", 0)
        if dlq_count > self.STOP_CONDITIONS["dlq"]["threshold"]:
            return f"dlq_count={int(dlq_count)}"
        
        # Notifier Down 체크
        notifier_avail = metrics.get("notifier_available", 1.0)
        if notifier_avail < self.STOP_CONDITIONS["notifier_down"]["threshold"]:
            return f"notifier_down={notifier_avail:.2f}"
        
        # Loop Latency p99 체크 (5분 지속)
        latency_p99 = metrics.get("cross_loop_latency_seconds_p99", 0)
        if latency_p99 > self.STOP_CONDITIONS["latency_p99"]["threshold"]:
            latency_violations.append(time.time())
        else:
            latency_violations.clear()
        
        if latency_violations:
            duration = latency_violations[-1] - latency_violations[0]
            if duration >= self.STOP_CONDITIONS["latency_p99"]["duration"]:
                return f"latency_p99={latency_p99*1000:.1f}ms_for_{duration:.0f}s"
        
        # CPU 높음 체크 (10분 지속)
        cpu_pct = metrics.get("process_cpu_usage_percent", 0)
        if cpu_pct > self.STOP_CONDITIONS["cpu_high"]["threshold"]:
            cpu_violations.append(time.time())
        else:
            cpu_violations.clear()
        
        if cpu_violations:
            duration = cpu_violations[-1] - cpu_violations[0]
            if duration >= self.STOP_CONDITIONS["cpu_high"]["duration"]:
                return f"cpu_high={cpu_pct:.1f}%_for_{duration:.0f}s"
        
        return None
    
    def _terminate_runner(self):
        """Runner 프로세스 종료"""
        if not psutil:
            logger.warning("psutil 없음, 프로세스 종료 불가")
            return
        
        try:
            proc = psutil.Process(self.runner_pid)
            logger.info(f"Runner 프로세스 종료 시그널 전송: PID={self.runner_pid}")
            
            # Windows: SIGTERM 대신 terminate() 사용
            proc.terminate()
            try:
                proc.wait(timeout=10)
                logger.info("Runner 프로세스 정상 종료")
            except psutil.TimeoutExpired:
                proc.kill()
                logger.warning("Runner 프로세스 강제 종료 (kill)")
        except psutil.NoSuchProcess:
            logger.warning("Runner 프로세스 이미 종료됨")
        except Exception as e:
            logger.error(f"Runner 프로세스 종료 예외: {e}")
    
    def _generate_summary(self, elapsed: float, iterations: int) -> Dict:
        """모니터링 요약 생성"""
        return {
            "run_id": self.run_id,
            "runner_pid": self.runner_pid,
            "duration_seconds": elapsed,
            "check_iterations": iterations,
            "check_interval": self.check_interval,
            "stop_reason": self.stop_reason,
            "log_patterns": self.log_patterns.copy(),
            "metrics_samples": len(self.metrics_history),
            "final_metrics": self.metrics_history[-1]["metrics"] if self.metrics_history else {},
        }
    
    def _save_summary(self, summary: Dict):
        """모니터링 요약 JSON 저장"""
        output_path = self.log_dir / "monitor_summary.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"모니터링 요약 저장: {output_path}")


def main():
    """CLI 엔트리포인트 (테스트용)"""
    import argparse
    
    parser = argparse.ArgumentParser(description="D77-4 Real-time Monitor")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runner-pid", type=int, required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--metrics-url", default="http://localhost:9100/metrics")
    parser.add_argument("--check-interval", type=int, default=10)
    parser.add_argument("--max-duration", type=int, default=3600)
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    log_file = Path(args.log_file)
    
    monitor = D77Monitor(
        project_root=project_root,
        run_id=args.run_id,
        runner_pid=args.runner_pid,
        log_file=log_file,
        metrics_url=args.metrics_url,
        check_interval=args.check_interval
    )
    
    summary = monitor.monitor_until_stop(max_duration=args.max_duration)
    
    print(f"\n{'='*60}")
    print(f"D77-4 Monitor Summary")
    print(f"{'='*60}")
    print(f"Run ID: {summary['run_id']}")
    print(f"Duration: {summary['duration_seconds']:.1f}s")
    print(f"Stop Reason: {summary['stop_reason'] or 'normal'}")
    print(f"Log Patterns: ERROR={summary['log_patterns']['ERROR']}, "
          f"CRITICAL={summary['log_patterns']['CRITICAL']}, "
          f"Traceback={summary['log_patterns']['Traceback']}")
    print(f"{'='*60}\n")
    
    sys.exit(0 if not summary['stop_reason'] or summary['stop_reason'] == 'runner_exited' else 1)


if __name__ == "__main__":
    main()
