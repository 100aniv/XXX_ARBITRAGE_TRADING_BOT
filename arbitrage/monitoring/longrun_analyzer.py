# -*- coding: utf-8 -*-
"""
D51 Long-run Analyzer

롱런 테스트 결과 분석 및 이상 징후 탐지.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MetricStats:
    """메트릭 통계"""
    count: int = 0
    mean: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    stddev: float = 0.0
    values: List[float] = field(default_factory=list)
    
    def update(self, value: float):
        """값 추가"""
        self.values.append(value)
        self.count += 1
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.mean = sum(self.values) / len(self.values)
        
        if len(self.values) > 1:
            variance = sum((x - self.mean) ** 2 for x in self.values) / len(self.values)
            self.stddev = variance ** 0.5


@dataclass
class AnomalyAlert:
    """이상 징후 알림"""
    severity: str  # "INFO", "WARN", "ERROR"
    category: str  # "LOOP_TIME", "SNAPSHOT", "TRADES", "GUARD", "MEMORY"
    message: str
    timestamp: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class LongrunReport:
    """롱런 분석 리포트"""
    scenario: str
    duration_minutes: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    # 메트릭 통계
    loop_time_stats: MetricStats = field(default_factory=MetricStats)
    trades_opened_stats: MetricStats = field(default_factory=MetricStats)
    spread_bps_stats: MetricStats = field(default_factory=MetricStats)
    
    # 카운트
    snapshot_none_count: int = 0
    guard_rejected_count: int = 0
    guard_stop_count: int = 0
    error_log_count: int = 0
    warning_log_count: int = 0
    
    # D52: WebSocket 특화 메트릭
    ws_latency_stats: MetricStats = field(default_factory=MetricStats)
    ws_reconnect_count: int = 0
    ws_message_gap_count: int = 0
    ws_latency_warn_count: int = 0  # > 500ms 횟수
    ws_latency_error_count: int = 0  # > 2000ms 횟수
    
    # D63: WebSocket Queue Optimization 메트릭
    ws_queue_depth_max: int = 0  # 최대 큐 깊이
    ws_queue_lag_ms_max: float = 0.0  # 최대 큐 지연
    ws_queue_lag_warn_count: int = 0  # > 1000ms 경고 횟수
    ws_queue_lag_stats: MetricStats = field(default_factory=MetricStats)
    
    # 이상 징후
    anomalies: List[AnomalyAlert] = field(default_factory=list)
    
    # 평가
    overall_status: str = "UNKNOWN"  # "OK", "WARN", "FAIL"
    
    def add_anomaly(self, alert: AnomalyAlert):
        """이상 징후 추가"""
        self.anomalies.append(alert)
        
        # 심각도에 따라 전체 상태 업데이트
        if alert.severity == "ERROR":
            self.overall_status = "FAIL"
        elif alert.severity == "WARN" and self.overall_status != "FAIL":
            self.overall_status = "WARN"
        elif self.overall_status == "UNKNOWN":
            self.overall_status = "OK"


class LongrunAnalyzer:
    """롱런 테스트 분석기"""
    
    def __init__(self, scenario: str = "S1"):
        """
        Args:
            scenario: S1, S2, S3
        """
        self.scenario = scenario
        self.thresholds = self._get_thresholds(scenario)
    
    def _get_thresholds(self, scenario: str) -> Dict[str, Any]:
        """시나리오별 임계값 반환"""
        thresholds = {
            "S1": {
                "loop_time_max_ms": 1500,
                "loop_time_mean_max_ms": 1200,
                "snapshot_none_max": 5,
                "error_log_max": 10,
                "warning_log_max": 10,
                "trades_opened_min": 1,
                "memory_increase_max_mb": 100,
            },
            "S2": {
                "loop_time_max_ms": 1500,
                "loop_time_mean_max_ms": 1200,
                "snapshot_none_max": 50,
                "error_log_max": 50,
                "warning_log_max": 50,
                "trades_opened_min": 10,
                "memory_increase_max_mb": 200,
            },
            "S3": {
                "loop_time_max_ms": 2000,
                "loop_time_mean_max_ms": 1300,
                "snapshot_none_max": 200,
                "error_log_max": 200,
                "warning_log_max": 200,
                "trades_opened_min": 50,
                "memory_increase_max_mb": 500,
            },
        }
        return thresholds.get(scenario, thresholds["S1"])
    
    def analyze_metrics_log(self, log_data: List[Dict[str, Any]]) -> LongrunReport:
        """
        메트릭 로그 분석.
        
        Args:
            log_data: 메트릭 데이터 리스트
        
        Returns:
            LongrunReport
        """
        report = LongrunReport(
            scenario=self.scenario,
            duration_minutes=len(log_data),  # 근사값
        )
        
        # 메트릭 데이터 처리
        for entry in log_data:
            # 루프 시간
            if "loop_time_ms" in entry:
                loop_time = entry["loop_time_ms"]
                report.loop_time_stats.update(loop_time)
                
                # 루프 시간 이상 징후
                if loop_time > self.thresholds["loop_time_max_ms"]:
                    report.add_anomaly(AnomalyAlert(
                        severity="WARN",
                        category="LOOP_TIME",
                        message=f"Loop time spike: {loop_time:.2f}ms > {self.thresholds['loop_time_max_ms']}ms",
                        value=loop_time,
                        threshold=self.thresholds["loop_time_max_ms"],
                    ))
            
            # 체결 수
            if "trades_opened" in entry:
                trades = entry["trades_opened"]
                report.trades_opened_stats.update(trades)
            
            # 스프레드
            if "spread_bps" in entry:
                spread = entry["spread_bps"]
                report.spread_bps_stats.update(spread)
            
            # 스냅샷 None
            if entry.get("snapshot_none", False):
                report.snapshot_none_count += 1
            
            # Guard 이벤트
            if entry.get("guard_rejected", False):
                report.guard_rejected_count += 1
            if entry.get("guard_stop", False):
                report.guard_stop_count += 1
            
            # 에러/경고 로그
            if entry.get("error_log", False):
                report.error_log_count += 1
            if entry.get("warning_log", False):
                report.warning_log_count += 1
            
            # D52: WebSocket 메트릭
            if "ws_latency_ms" in entry:
                ws_latency = entry["ws_latency_ms"]
                report.ws_latency_stats.update(ws_latency)
                
                # WS 지연 시간 이상 징후
                if ws_latency > 2000:
                    report.ws_latency_error_count += 1
                elif ws_latency > 500:
                    report.ws_latency_warn_count += 1
            
            if entry.get("ws_reconnect", False):
                report.ws_reconnect_count += 1
            
            if entry.get("ws_message_gap", False):
                report.ws_message_gap_count += 1
            
            # D63: WebSocket Queue Optimization 메트릭
            if "ws_queue_depth" in entry:
                queue_depth = entry["ws_queue_depth"]
                report.ws_queue_depth_max = max(report.ws_queue_depth_max, queue_depth)
            
            if "ws_queue_lag_ms" in entry:
                queue_lag = entry["ws_queue_lag_ms"]
                report.ws_queue_lag_stats.update(queue_lag)
                report.ws_queue_lag_ms_max = max(report.ws_queue_lag_ms_max, queue_lag)
                
                # 큐 지연 경고 (> 1000ms)
                if queue_lag > 1000:
                    report.ws_queue_lag_warn_count += 1
        
        # 이상 징후 탐지
        self._detect_anomalies(report)
        
        return report
    
    def _detect_anomalies(self, report: LongrunReport):
        """이상 징후 탐지"""
        
        # 1. 루프 시간 평균 이상
        if report.loop_time_stats.mean > self.thresholds["loop_time_mean_max_ms"]:
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="LOOP_TIME",
                message=f"Average loop time high: {report.loop_time_stats.mean:.2f}ms > {self.thresholds['loop_time_mean_max_ms']}ms",
                value=report.loop_time_stats.mean,
                threshold=self.thresholds["loop_time_mean_max_ms"],
            ))
        
        # 2. 스냅샷 None 과다
        if report.snapshot_none_count > self.thresholds["snapshot_none_max"]:
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="SNAPSHOT",
                message=f"Snapshot None count high: {report.snapshot_none_count} > {self.thresholds['snapshot_none_max']}",
                value=report.snapshot_none_count,
                threshold=self.thresholds["snapshot_none_max"],
            ))
        
        # 3. 에러 로그 과다
        if report.error_log_count > self.thresholds["error_log_max"]:
            report.add_anomaly(AnomalyAlert(
                severity="ERROR",
                category="ERROR_LOG",
                message=f"Error log count high: {report.error_log_count} > {self.thresholds['error_log_max']}",
                value=report.error_log_count,
                threshold=self.thresholds["error_log_max"],
            ))
        
        # 4. 경고 로그 과다
        if report.warning_log_count > self.thresholds["warning_log_max"]:
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WARNING_LOG",
                message=f"Warning log count high: {report.warning_log_count} > {self.thresholds['warning_log_max']}",
                value=report.warning_log_count,
                threshold=self.thresholds["warning_log_max"],
            ))
        
        # 5. 체결 신호 부족 (총 체결 수 기준)
        total_trades = sum(report.trades_opened_stats.values) if report.trades_opened_stats.values else 0
        if total_trades < self.thresholds["trades_opened_min"]:
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="TRADES",
                message=f"Trades opened too low: {total_trades} < {self.thresholds['trades_opened_min']}",
                value=total_trades,
                threshold=self.thresholds["trades_opened_min"],
            ))
        
        # 6. Guard 과다 발동
        if report.guard_rejected_count > 10:
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="GUARD",
                message=f"Guard rejected too many trades: {report.guard_rejected_count} > 10",
                value=report.guard_rejected_count,
                threshold=10,
            ))
        
        # 7. Guard 세션 중지
        if report.guard_stop_count > 0:
            report.add_anomaly(AnomalyAlert(
                severity="ERROR",
                category="GUARD",
                message=f"Guard stopped session: {report.guard_stop_count} times",
                value=report.guard_stop_count,
                threshold=0,
            ))
        
        # 8. D52: WS 지연 시간 이상
        if report.ws_latency_error_count > 0:
            report.add_anomaly(AnomalyAlert(
                severity="ERROR",
                category="WS_LATENCY",
                message=f"WS latency error (> 2000ms): {report.ws_latency_error_count} times",
                value=report.ws_latency_error_count,
                threshold=0,
            ))
        elif report.ws_latency_warn_count > self.thresholds.get("ws_latency_warn_max", 10):
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WS_LATENCY",
                message=f"WS latency warning (> 500ms): {report.ws_latency_warn_count} times",
                value=report.ws_latency_warn_count,
                threshold=self.thresholds.get("ws_latency_warn_max", 10),
            ))
        
        # 9. D52: WS 재연결 과다
        if report.ws_reconnect_count > self.thresholds.get("ws_reconnect_max", 10):
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WS_RECONNECT",
                message=f"WS reconnect count high: {report.ws_reconnect_count} > {self.thresholds.get('ws_reconnect_max', 10)}",
                value=report.ws_reconnect_count,
                threshold=self.thresholds.get("ws_reconnect_max", 10),
            ))
        
        # 10. D52: WS 메시지 갭
        if report.ws_message_gap_count > self.thresholds.get("ws_message_gap_max", 5):
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WS_MESSAGE_GAP",
                message=f"WS message gap count high: {report.ws_message_gap_count} > {self.thresholds.get('ws_message_gap_max', 5)}",
                value=report.ws_message_gap_count,
                threshold=self.thresholds.get("ws_message_gap_max", 5),
            ))
        
        # 11. D63: WS Queue 지연 이상
        if report.ws_queue_lag_warn_count > self.thresholds.get("ws_queue_lag_warn_max", 10):
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WS_QUEUE_LAG",
                message=f"WS queue lag warning (> 1000ms): {report.ws_queue_lag_warn_count} times",
                value=report.ws_queue_lag_warn_count,
                threshold=self.thresholds.get("ws_queue_lag_warn_max", 10),
            ))
        
        # 12. D63: WS Queue 깊이 이상
        if report.ws_queue_depth_max > self.thresholds.get("ws_queue_depth_max", 100):
            report.add_anomaly(AnomalyAlert(
                severity="WARN",
                category="WS_QUEUE_DEPTH",
                message=f"WS queue depth high: {report.ws_queue_depth_max} > {self.thresholds.get('ws_queue_depth_max', 100)}",
                value=report.ws_queue_depth_max,
                threshold=self.thresholds.get("ws_queue_depth_max", 100),
            ))
        
        # 13. 이상 징후가 없으면 상태를 OK로 설정
        if not report.anomalies and report.overall_status == "UNKNOWN":
            report.overall_status = "OK"
    
    def generate_report(self, report: LongrunReport) -> str:
        """리포트 생성"""
        lines = []
        
        lines.append("=" * 70)
        lines.append(f"D51 Long-run Analysis Report - Scenario {report.scenario}")
        lines.append("=" * 70)
        lines.append("")
        
        # 기본 정보
        lines.append("[기본 정보]")
        lines.append(f"시나리오: {report.scenario}")
        lines.append(f"예상 실행 시간: {report.duration_minutes} 분")
        if report.start_time:
            lines.append(f"시작 시간: {report.start_time}")
        if report.end_time:
            lines.append(f"종료 시간: {report.end_time}")
        lines.append("")
        
        # 루프 시간 분석
        lines.append("[루프 시간 분석]")
        lines.append(f"평균: {report.loop_time_stats.mean:.2f} ms")
        lines.append(f"최대: {report.loop_time_stats.max:.2f} ms")
        lines.append(f"최소: {report.loop_time_stats.min:.2f} ms")
        lines.append(f"표준편차: {report.loop_time_stats.stddev:.2f} ms")
        lines.append(f"샘플 수: {report.loop_time_stats.count}")
        lines.append("")
        
        # 체결 신호 분석
        lines.append("[체결 신호 분석]")
        lines.append(f"총 체결 수: {report.trades_opened_stats.count}")
        if report.trades_opened_stats.count > 0:
            lines.append(f"평균 체결: {report.trades_opened_stats.mean:.2f}")
            lines.append(f"최대 체결: {report.trades_opened_stats.max:.2f}")
        lines.append("")
        
        # 스프레드 분석
        lines.append("[스프레드 분석]")
        if report.spread_bps_stats.count > 0:
            lines.append(f"평균: {report.spread_bps_stats.mean:.2f} bps")
            lines.append(f"최대: {report.spread_bps_stats.max:.2f} bps")
            lines.append(f"최소: {report.spread_bps_stats.min:.2f} bps")
        lines.append("")
        
        # D52: WebSocket 메트릭 분석
        lines.append("[WebSocket 메트릭 분석]")
        if report.ws_latency_stats.count > 0:
            lines.append(f"지연 시간 평균: {report.ws_latency_stats.mean:.2f} ms")
            lines.append(f"지연 시간 최대: {report.ws_latency_stats.max:.2f} ms")
            lines.append(f"지연 시간 최소: {report.ws_latency_stats.min:.2f} ms")
        lines.append(f"재연결 횟수: {report.ws_reconnect_count} 회")
        lines.append(f"메시지 갭: {report.ws_message_gap_count} 회")
        
        # D63: WebSocket Queue Optimization 메트릭
        lines.append("")
        lines.append("[WebSocket Queue Optimization (D63)]")
        lines.append(f"최대 큐 깊이: {report.ws_queue_depth_max}")
        if report.ws_queue_lag_stats.count > 0:
            lines.append(f"큐 지연 평균: {report.ws_queue_lag_stats.mean:.2f} ms")
            lines.append(f"큐 지연 최대: {report.ws_queue_lag_stats.max:.2f} ms")
            lines.append(f"큐 지연 최소: {report.ws_queue_lag_stats.min:.2f} ms")
        lines.append(f"큐 지연 경고 (> 1000ms): {report.ws_queue_lag_warn_count} 회")
        lines.append(f"지연 경고 (> 500ms): {report.ws_latency_warn_count} 회")
        lines.append(f"지연 에러 (> 2000ms): {report.ws_latency_error_count} 회")
        lines.append("")
        
        # 이상 징후
        lines.append("[이상 징후]")
        lines.append(f"스냅샷 None: {report.snapshot_none_count} 회")
        lines.append(f"Guard 거부: {report.guard_rejected_count} 회")
        lines.append(f"Guard 중지: {report.guard_stop_count} 회")
        lines.append(f"에러 로그: {report.error_log_count} 개")
        lines.append(f"경고 로그: {report.warning_log_count} 개")
        lines.append("")
        
        # 탐지된 이상
        if report.anomalies:
            lines.append("[탐지된 이상 징후]")
            for i, alert in enumerate(report.anomalies, 1):
                severity_icon = {
                    "INFO": "ℹ️",
                    "WARN": "⚠️",
                    "ERROR": "❌",
                }.get(alert.severity, "?")
                lines.append(f"{i}. {severity_icon} [{alert.category}] {alert.message}")
            lines.append("")
        else:
            lines.append("[탐지된 이상 징후]")
            lines.append("없음 ✅")
            lines.append("")
        
        # 최종 평가
        lines.append("[최종 평가]")
        status_icon = {
            "OK": "✅",
            "WARN": "⚠️",
            "FAIL": "❌",
            "UNKNOWN": "❓",
        }.get(report.overall_status, "?")
        lines.append(f"상태: {status_icon} {report.overall_status}")
        lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        분석 요약 반환 (테스트용)
        
        Returns:
            요약 dict
        """
        return {
            "scenario": self.scenario,
            "thresholds": self.thresholds,
        }


def analyze_longrun_log(log_file: str, scenario: str = "S1") -> LongrunReport:
    """
    롱런 로그 파일 분석.
    
    Args:
        log_file: 로그 파일 경로
        scenario: S1, S2, S3
    
    Returns:
        LongrunReport
    """
    analyzer = LongrunAnalyzer(scenario=scenario)
    
    # 로그 파일 읽기 (JSON Lines 형식 가정)
    log_data = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        log_data.append(entry)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON line: {line}")
    except FileNotFoundError:
        logger.error(f"Log file not found: {log_file}")
        return LongrunReport(scenario=scenario, duration_minutes=0)
    
    # 분석
    report = analyzer.analyze_metrics_log(log_data)
    report.start_time = log_data[0].get("timestamp") if log_data else None
    report.end_time = log_data[-1].get("timestamp") if log_data else None
    
    return report
