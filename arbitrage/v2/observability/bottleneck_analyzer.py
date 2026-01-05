"""
D205-11-2: Bottleneck Analyzer

목적:
- stage별 p95 비교, Top 3 병목 선정
- 최적화 우선순위 제안
- bottleneck_report.json 생성

설계 원칙:
- latency_summary.json 입력 기반
- percentage 계산 (각 stage가 전체 latency에서 차지하는 비율)
- 최적화 권장사항 제공 (RECEIVE_TICK → WebSocket, DB → batch 등)

Author: arbitrage-lite V2
Date: 2026-01-05
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BottleneckEntry:
    """병목 항목"""
    stage: str
    p95_ms: float
    percentage: float
    recommendation: str = ""


@dataclass
class BottleneckReport:
    """병목 분석 리포트"""
    top_3_bottlenecks: List[BottleneckEntry] = field(default_factory=list)
    optimization_priority: str = ""
    total_e2e_p95_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return {
            "top_3_bottlenecks": [
                {
                    "stage": b.stage,
                    "p95_ms": round(b.p95_ms, 2),
                    "percentage": round(b.percentage, 2),
                    "recommendation": b.recommendation
                }
                for b in self.top_3_bottlenecks
            ],
            "optimization_priority": self.optimization_priority,
            "total_e2e_p95_ms": round(self.total_e2e_p95_ms, 2)
        }


def analyze_bottleneck(latency_summary: Dict) -> BottleneckReport:
    """
    Bottleneck 분석 (stage별 p95 기준)
    
    Args:
        latency_summary: {
            "stages": {
                "RECEIVE_TICK": {"p50": 56.46, "p95": 120.5, ...},
                "DECIDE": {"p50": 0.01, "p95": 0.02, ...},
                ...
            },
            "e2e": {"p50": 58.0, "p95": 125.0, ...}
        }
        
    Returns:
        BottleneckReport with top 3 bottlenecks
    """
    stages = latency_summary.get("stages", {})
    e2e = latency_summary.get("e2e", {})
    total_e2e_p95 = e2e.get("p95", 0.0)
    
    if total_e2e_p95 == 0.0:
        logger.warning("[BottleneckAnalyzer] E2E p95 is 0, cannot calculate percentages")
        return BottleneckReport(total_e2e_p95_ms=0.0)
    
    stage_entries: List[BottleneckEntry] = []
    
    for stage_name, stats in stages.items():
        p95_ms = stats.get("p95", 0.0)
        percentage = (p95_ms / total_e2e_p95) * 100.0
        
        recommendation = _get_recommendation(stage_name, p95_ms)
        
        entry = BottleneckEntry(
            stage=stage_name,
            p95_ms=p95_ms,
            percentage=percentage,
            recommendation=recommendation
        )
        stage_entries.append(entry)
    
    stage_entries.sort(key=lambda x: x.p95_ms, reverse=True)
    
    top_3 = stage_entries[:3]
    
    priority = top_3[0].stage if top_3 else ""
    
    report = BottleneckReport(
        top_3_bottlenecks=top_3,
        optimization_priority=priority,
        total_e2e_p95_ms=total_e2e_p95
    )
    
    logger.info(f"[BottleneckAnalyzer] Top bottleneck: {priority} ({top_3[0].p95_ms:.2f}ms, {top_3[0].percentage:.1f}%)")
    
    return report


def _get_recommendation(stage: str, p95_ms: float) -> str:
    """
    Stage별 최적화 권장사항
    
    Args:
        stage: Stage name
        p95_ms: p95 latency (ms)
        
    Returns:
        Optimization recommendation
    """
    if stage == "RECEIVE_TICK":
        if p95_ms > 50.0:
            return "REST API → WebSocket 구독 전환 + 캐싱 (100ms TTL)"
        elif p95_ms > 20.0:
            return "병렬 요청 + 캐싱 전략"
        else:
            return "최적화 불필요 (p95 < 20ms)"
    
    elif stage == "DB_RECORD":
        if p95_ms > 5.0:
            return "Batch insert (10개 단위) + 비동기 commit"
        elif p95_ms > 2.0:
            return "Connection pooling 확인 + 인덱스 최적화"
        else:
            return "최적화 불필요 (p95 < 2ms)"
    
    elif stage == "REDIS_WRITE":
        if p95_ms > 2.0:
            return "Pipeline 사용 (batch write)"
        elif p95_ms > 1.0:
            return "Connection pooling 확인"
        else:
            return "최적화 불필요 (p95 < 1ms)"
    
    elif stage == "REDIS_READ":
        if p95_ms > 2.0:
            return "MGET 사용 (batch read) + 캐싱"
        elif p95_ms > 1.0:
            return "Connection pooling 확인"
        else:
            return "최적화 불필요 (p95 < 1ms)"
    
    elif stage == "DECIDE":
        if p95_ms > 5.0:
            return "알고리즘 최적화 (early exit, 캐싱)"
        else:
            return "최적화 불필요 (계산 비용 낮음)"
    
    elif stage == "ADAPTER_PLACE":
        if p95_ms > 10.0:
            return "Exchange API 최적화 (병렬 호출, 재시도 전략)"
        else:
            return "최적화 불필요 (MockAdapter 또는 빠른 API)"
    
    else:
        return "Unknown stage"
