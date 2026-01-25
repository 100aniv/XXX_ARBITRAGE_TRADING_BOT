"""
D205-18-2: Evidence Collector (Engine-Centric)

PaperRunner에서 Evidence 생성 로직 분리.

Purpose:
- Metrics snapshot 생성
- Decision trace 수집
- Evidence 파일 저장 (manifest, kpi, decision_trace)
- Runner는 collector.save() 호출만

Author: arbitrage-lite V2
Date: 2026-01-11
"""

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class EvidenceCollector:
    """
    Evidence 수집 및 저장
    
    D205-18-2: PaperRunner에서 분리
    - Metrics → snapshot
    - Trade history → decision trace
    - 파일 저장 (manifest, kpi, decision_trace)
    """
    
    def __init__(self, output_dir: str, run_id: str = ""):
        """
        Args:
            output_dir: Evidence 저장 디렉토리
            run_id: Run ID
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
    
    def generate_metrics_snapshot(
        self,
        metrics: Any,
        db_counts: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Metrics snapshot 생성
        
        Args:
            metrics: PaperMetrics 인스턴스
            db_counts: DB row counts (v2_orders, v2_fills, v2_trades)
        
        Returns:
            Snapshot dict
        """
        reject_total = int(sum(metrics.reject_reasons.values()))

        snapshot = {
            "type": "metrics_snapshot",
            "timestamp": metrics.to_dict().get("start_time"),
            "duration_seconds": metrics.to_dict().get("duration_seconds"),
            
            # Opportunity 통계
            "opportunities": {
                "generated": metrics.opportunities_generated,
                "intents_created": metrics.intents_created,
                "reject_reasons": dict(metrics.reject_reasons),
                "reject_total": reject_total,
            },
            
            # Execution 통계
            "execution": {
                "mock_executions": metrics.mock_executions,
                "db_inserts_ok": metrics.db_inserts_ok,
                "db_inserts_failed": metrics.db_inserts_failed,
            },
            
            # PnL 통계
            "pnl": {
                "closed_trades": metrics.closed_trades,
                "gross_pnl": round(metrics.gross_pnl, 2),
                "net_pnl": round(metrics.net_pnl, 2),
                "fees": round(metrics.fees, 2),
                "wins": metrics.wins,
                "losses": metrics.losses,
                "winrate_pct": round(metrics.winrate_pct, 2),
            },
            
            # MarketData 상태
            "marketdata": {
                "mode": metrics.marketdata_mode,
                "upbit_ok": metrics.upbit_marketdata_ok,
                "binance_ok": metrics.binance_marketdata_ok,
                "real_ticks_ok": metrics.real_ticks_ok_count,
                "real_ticks_fail": metrics.real_ticks_fail_count,
            },
            
            # Redis 상태
            "redis": {
                "ok": metrics.redis_ok,
                "ratelimit_hits": metrics.ratelimit_hits,
                "dedup_hits": metrics.dedup_hits,
            },
            
            # 시스템 리소스
            "system": {
                "memory_mb": metrics.memory_mb,
                "cpu_pct": metrics.cpu_pct,
            },
            
            # Error 통계
            "errors": {
                "count": metrics.error_count,
                "samples": metrics.errors[:10],
                "db_last_error": metrics.db_last_error,
            },
        }
        
        # DB counts 추가
        if db_counts:
            snapshot["db_counts"] = db_counts
        
        return snapshot
    
    def generate_decision_trace(
        self,
        trade_history: List[Dict[str, Any]],
        max_samples: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Decision trace 생성
        
        Args:
            trade_history: Trade 기록 리스트
            max_samples: 최대 샘플 수
        
        Returns:
            Decision trace samples (최근 N개)
        """
        # 최근 max_samples개만 반환
        return trade_history[-max_samples:] if trade_history else []
    
    def save(
        self,
        metrics: Any,
        trade_history: List[Dict[str, Any]],
        edge_distribution: Optional[List[Dict[str, Any]]] = None,
        db_counts: Optional[Dict[str, int]] = None,
        phase: str = "unknown"
    ) -> None:
        """
        Evidence 파일 저장
        
        Args:
            metrics: PaperMetrics 인스턴스
            trade_history: Trade 기록 리스트
            db_counts: DB row counts
            phase: 실행 phase (smoke, baseline, longrun)
        """
        try:
            # 1. KPI JSON
            kpi_dict = metrics.to_dict()
            kpi_path = self.output_dir / "kpi.json"
            with open(kpi_path, "w", encoding="utf-8") as f:
                json.dump(kpi_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] KPI saved: {kpi_path}")
            
            # 2. Metrics Snapshot
            snapshot = self.generate_metrics_snapshot(metrics, db_counts)
            snapshot_path = self.output_dir / "metrics_snapshot.json"
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Metrics snapshot saved: {snapshot_path}")
            
            # 3. Decision Trace
            decision_trace = self.generate_decision_trace(trade_history)
            trace_path = self.output_dir / "decision_trace.json"
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(decision_trace, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Decision trace saved: {trace_path} ({len(decision_trace)} samples)")

            # 3-1. Edge Distribution (D207-3)
            edge_distribution = edge_distribution or []
            edge_distribution_path = self.output_dir / "edge_distribution.json"
            with open(edge_distribution_path, "w", encoding="utf-8") as f:
                json.dump(edge_distribution, f, indent=2, ensure_ascii=False)
            logger.info(
                f"[EvidenceCollector] Edge distribution saved: {edge_distribution_path} ({len(edge_distribution)} samples)"
            )
            
            # 4. Chain Summary (D205-18-4-FIX-2 F4: Evidence Completeness 필수 파일)
            chain_summary = {
                "run_id": self.run_id,
                "phase": phase,
                "duration_seconds": kpi_dict.get("duration_seconds"),
                "closed_trades": kpi_dict.get("closed_trades"),
                "wins": kpi_dict.get("wins"),
                "losses": kpi_dict.get("losses"),
                "net_pnl": kpi_dict.get("net_pnl"),
                "opportunities_generated": kpi_dict.get("opportunities_generated"),
                "stop_reason": kpi_dict.get("stop_reason", "TIME_REACHED"),
            }
            chain_summary_path = self.output_dir / "chain_summary.json"
            with open(chain_summary_path, "w", encoding="utf-8") as f:
                json.dump(chain_summary, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Chain summary saved: {chain_summary_path}")
            
            # 5. Manifest (OPS_PROTOCOL 필수 파일 목록 포함)
            files = [
                "chain_summary.json",
                "heartbeat.jsonl",
                "kpi.json",
                "manifest.json",
                "metrics_snapshot.json",
                "decision_trace.json",
                "edge_distribution.json",
            ]
            run_log_path = self.output_dir / "run_log.txt"
            if run_log_path.exists():
                files.append("run_log.txt")

            file_meta: Dict[str, Any] = {}
            for filename in files:
                filepath = self.output_dir / filename
                if not filepath.exists():
                    continue
                size_bytes = filepath.stat().st_size
                if filename == "manifest.json":
                    file_meta[filename] = {
                        "size_bytes": size_bytes,
                        "sha256": None,
                        "note": "self_reference"
                    }
                    continue
                with open(filepath, "rb") as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()
                file_meta[filename] = {
                    "size_bytes": size_bytes,
                    "sha256": f"sha256:{sha256}"
                }

            manifest = {
                "run_id": self.run_id,
                "phase": phase,
                "timestamp": kpi_dict.get("start_time"),
                "duration_seconds": kpi_dict.get("duration_seconds"),
                "closed_trades": kpi_dict.get("closed_trades"),
                "winrate_pct": kpi_dict.get("winrate_pct"),
                "net_pnl": kpi_dict.get("net_pnl"),
                "marketdata_mode": kpi_dict.get("marketdata_mode"),
                "files": files,
                "file_meta": file_meta,
            }
            manifest_path = self.output_dir / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Manifest saved: {manifest_path}")
            
        except Exception as e:
            logger.error(f"[EvidenceCollector] Failed to save evidence: {e}", exc_info=True)
            raise
