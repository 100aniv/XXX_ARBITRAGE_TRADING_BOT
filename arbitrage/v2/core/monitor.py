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
    
    def _edge_analysis_summary(self, edge_distribution: List[Dict[str, Any]]) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        for tick in edge_distribution:
            tick_candidates = tick.get("candidates") or []
            candidates.extend(tick_candidates)

        def _quantile(values: List[float], q: float) -> Optional[float]:
            if not values:
                return None
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * q)
            idx = min(max(idx, 0), len(sorted_vals) - 1)
            return round(sorted_vals[idx], 4)

        spread_vals = [float(c.get("spread_bps", 0.0)) for c in candidates]
        be_vals = [float(c.get("break_even_bps", 0.0)) for c in candidates]
        edge_vals = [float(c.get("edge_bps", 0.0)) for c in candidates]
        net_edge_vals = [float(c.get("net_edge_bps", 0.0)) for c in candidates]

        summary = {
            "total_ticks": len(edge_distribution),
            "total_candidates": len(candidates),
            "p50": {
                "spread_bps": _quantile(spread_vals, 0.50),
                "break_even_bps": _quantile(be_vals, 0.50),
                "edge_bps": _quantile(edge_vals, 0.50),
                "net_edge_bps": _quantile(net_edge_vals, 0.50),
            },
            "max_net_edge_bps": round(max(net_edge_vals), 4) if net_edge_vals else None,
            "min_net_edge_bps": round(min(net_edge_vals), 4) if net_edge_vals else None,
            "positive_net_edge_pct": round(
                (sum(1 for v in net_edge_vals if v > 0) / len(net_edge_vals) * 100), 2
            ) if net_edge_vals else 0.0,
            "negative_net_edge_pct": round(
                (sum(1 for v in net_edge_vals if v < 0) / len(net_edge_vals) * 100), 2
            ) if net_edge_vals else 0.0,
        }

        return summary

    def _edge_survey_report(
        self,
        edge_distribution: List[Dict[str, Any]],
        run_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        def _quantile(values: List[float], q: float) -> Optional[float]:
            if not values:
                return None
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * q)
            idx = min(max(idx, 0), len(sorted_vals) - 1)
            return round(sorted_vals[idx], 4)

        per_symbol: Dict[str, Dict[str, Any]] = {}
        total_candidates = 0
        all_spread_vals: List[float] = []
        all_net_edge_vals: List[float] = []
        
        for tick in edge_distribution:
            tick_candidates = tick.get("candidates") or []
            for candidate in tick_candidates:
                symbol = candidate.get("symbol") or "unknown"
                entry = per_symbol.setdefault(
                    symbol,
                    {"spread_vals": [], "net_edge_vals": [], "opportunity_count": 0},
                )
                spread_val = candidate.get("spread_bps")
                net_edge_val = candidate.get("net_edge_bps")
                if spread_val is not None:
                    entry["spread_vals"].append(float(spread_val))
                    all_spread_vals.append(float(spread_val))
                if net_edge_val is not None:
                    entry["net_edge_vals"].append(float(net_edge_val))
                    all_net_edge_vals.append(float(net_edge_val))
                entry["opportunity_count"] += 1
                total_candidates += 1

        symbol_summary: Dict[str, Dict[str, Any]] = {}
        for symbol, entry in per_symbol.items():
            spread_vals = entry.get("spread_vals", [])
            net_edge_vals = entry.get("net_edge_vals", [])
            symbol_summary[symbol] = {
                "opportunity_count": entry.get("opportunity_count", 0),
                "max_spread_bps": round(max(spread_vals), 4) if spread_vals else None,
                "p95_net_edge_bps": _quantile(net_edge_vals, 0.95),
                "p99_net_edge_bps": _quantile(net_edge_vals, 0.99),
                "min_net_edge_bps": round(min(net_edge_vals), 4) if net_edge_vals else None,
                "max_net_edge_bps": round(max(net_edge_vals), 4) if net_edge_vals else None,
            }

        sampling_entries = [
            tick.get("sampling_policy")
            for tick in edge_distribution
            if tick.get("sampling_policy")
        ]
        sampling_summary = {
            "mode": None,
            "max_symbols_per_tick": None,
            "universe_size": None,
            "symbols_sampled": None,
            "ticks_total": len(edge_distribution),
            "ticks_sampled": len(sampling_entries),
        }
        if sampling_entries:
            base = sampling_entries[0]
            sampling_summary.update({
                "mode": base.get("mode"),
                "max_symbols_per_tick": base.get("max_symbols_per_tick"),
                "universe_size": base.get("universe_size"),
                "symbols_sampled": base.get("symbols_sampled"),
            })
        
        # D_ALPHA-0: Extract universe metadata from run_meta
        unique_symbols_evaluated = len(per_symbol)
        evaluated_symbols = sorted(per_symbol.keys())
        evaluated_symbols_hash = hashlib.sha256(
            json.dumps(evaluated_symbols, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        universe_metadata = {}
        if run_meta and "universe_metadata" in run_meta:
            raw_universe_metadata = run_meta.get("universe_metadata")
            if raw_universe_metadata is not None:
                universe_metadata = dict(raw_universe_metadata)
            # Override universe_size in sampling_summary if available
            if universe_metadata.get("universe_loaded_count") is not None:
                sampling_summary["universe_size"] = universe_metadata["universe_loaded_count"]

        requested_count = universe_metadata.get("universe_requested_top_n")
        if requested_count is None:
            requested_count = sampling_summary.get("universe_size")
        coverage_ratio = None
        if isinstance(requested_count, int) and requested_count > 0:
            coverage_ratio = round(unique_symbols_evaluated / requested_count, 6)

        status = "PASS" if total_candidates > 0 else "FAIL"
        
        # D207-7: Extract reject reasons from run_meta
        reject_total = 0
        reject_by_reason: Dict[str, int] = {}
        if run_meta and "metrics" in run_meta:
            metrics_dict = run_meta["metrics"]
            if "reject_reasons" in metrics_dict:
                reject_by_reason = dict(metrics_dict["reject_reasons"])
                reject_total = sum(reject_by_reason.values())
        
        # D207-7: Global tail statistics
        tail_stats = {
            "max_spread_bps": round(max(all_spread_vals), 4) if all_spread_vals else None,
            "p95_spread_bps": _quantile(all_spread_vals, 0.95),
            "p99_spread_bps": _quantile(all_spread_vals, 0.99),
            "max_net_edge_bps": round(max(all_net_edge_vals), 4) if all_net_edge_vals else None,
            "min_net_edge_bps": round(min(all_net_edge_vals), 4) if all_net_edge_vals else None,
            "p95_net_edge_bps": _quantile(all_net_edge_vals, 0.95),
            "p99_net_edge_bps": _quantile(all_net_edge_vals, 0.99),
            "positive_net_edge_pct": round(
                (sum(1 for v in all_net_edge_vals if v > 0) / len(all_net_edge_vals) * 100), 2
            ) if all_net_edge_vals else 0.0,
        }

        return {
            "status": status,
            "total_ticks": len(edge_distribution),
            "total_symbols": len(symbol_summary),
            "total_candidates": total_candidates,
            "unique_symbols_evaluated": unique_symbols_evaluated,
            "coverage_ratio": coverage_ratio,
            "universe_symbols_hash": evaluated_symbols_hash,
            "reject_total": reject_total,
            "reject_by_reason": reject_by_reason,
            "tail_stats": tail_stats,
            "sampling_policy": sampling_summary,
            "universe_metadata": universe_metadata,
            "symbols": symbol_summary,
            "run_meta": run_meta or {},
        }

    def save(
        self,
        metrics: Any,
        trade_history: List[Dict[str, Any]],
        edge_distribution: Optional[List[Dict[str, Any]]] = None,
        db_counts: Optional[Dict[str, int]] = None,
        phase: str = "unknown",
        run_meta: Optional[Dict[str, Any]] = None
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

            # 3-2. Edge Analysis Summary (D207-5)
            edge_summary = self._edge_analysis_summary(edge_distribution)
            edge_summary_path = self.output_dir / "edge_analysis_summary.json"
            with open(edge_summary_path, "w", encoding="utf-8") as f:
                json.dump(edge_summary, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Edge analysis summary saved: {edge_summary_path}")

            # 3-3. Edge Survey Report (D207-6)
            edge_survey_report = self._edge_survey_report(edge_distribution, run_meta=run_meta)
            edge_survey_path = self.output_dir / "edge_survey_report.json"
            with open(edge_survey_path, "w", encoding="utf-8") as f:
                json.dump(edge_survey_report, f, indent=2, ensure_ascii=False)
            logger.info(f"[EvidenceCollector] Edge survey report saved: {edge_survey_path}")
            
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
                "edge_analysis_summary.json",
                "edge_survey_report.json",
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
                "run_meta": run_meta or {},
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
