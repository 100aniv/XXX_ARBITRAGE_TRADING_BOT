"""
D205-5: Replay Runner

market.ndjson 입력 → 의사결정 재실행 → decisions.ndjson 출력
"""

import json
import logging
import time
import hashlib
import sys
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from arbitrage.v2.replay.schemas import MarketTick, DecisionRecord
from arbitrage.v2.opportunity.detector import detect_candidates
from arbitrage.v2.domain.break_even import BreakEvenParams, compute_break_even_bps
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.execution_quality.model_v1 import SimpleExecutionQualityModel
from arbitrage.v2.core.quote_normalizer import (
    normalize_price_to_krw,
    is_units_mismatch,
    get_quote_mode,
    DEFAULT_FX_KRW_PER_USDT,
)

logger = logging.getLogger(__name__)


class ReplayRunner:
    """
    Replay Runner
    
    market.ndjson 입력을 읽어서 의사결정을 재실행하고
    decisions.ndjson로 출력
    """
    
    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        break_even_params: BreakEvenParams,
        fx_krw_per_usdt: float = DEFAULT_FX_KRW_PER_USDT,
    ):
        """
        Args:
            input_path: market.ndjson 파일 경로
            output_dir: decisions.ndjson 출력 디렉토리
            break_even_params: 손익분기 파라미터
            fx_krw_per_usdt: KRW/USDT 환율 (기본값: DEFAULT_FX_KRW_PER_USDT)
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.break_even_params = break_even_params
        self.fx_krw_per_usdt = fx_krw_per_usdt
        
        self.decisions_path = output_dir / "decisions.ndjson"
        self.manifest_path = output_dir / "manifest.json"
        
        self.decisions: List[DecisionRecord] = []
        self.input_hash = ""
        
        # D205-7: ExecutionQuality model 초기화
        self.exec_quality_model = SimpleExecutionQualityModel()
        
        # D205-4: DecisionTrace 초기화
        from arbitrage.v2.core.decision_trace import DecisionTrace
        self.trace = DecisionTrace()
        
        logger.info(f"[D205-5_REPLAY] Initialized: input={input_path}, output={output_dir}")
    
    def run(self) -> Dict[str, Any]:
        """
        Replay 실행
        
        Returns:
            실행 결과 딕셔너리
        """
        start_time = time.time()
        
        # 1. 입력 파일 읽기 + hash 계산
        ticks = self._load_ticks()
        
        if not ticks:
            logger.error("[D205-5_REPLAY] No ticks loaded")
            return {"status": "FAIL", "reason": "No ticks loaded"}
        
        logger.info(f"[D205-5_REPLAY] Loaded {len(ticks)} ticks")
        
        # 2. 의사결정 재실행
        self._replay_decisions(ticks)
        
        # 3. 결과 저장
        self._save_results()
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = {
            "status": "PASS",
            "duration_sec": duration,
            "ticks_count": len(ticks),
            "decisions_count": len(self.decisions),
            "input_hash": self.input_hash,
        }
        
        logger.info(f"[D205-5_REPLAY] Completed: {result}")
        
        return result
    
    def _load_ticks(self) -> List[MarketTick]:
        """
        market.ndjson 읽기 + input_hash 계산
        
        Returns:
            MarketTick 리스트
        """
        ticks = []
        
        try:
            with open(self.input_path, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Input hash 계산 (재현성 검증용)
                self.input_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
                
                for line in content.strip().split("\n"):
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    tick = MarketTick.from_dict(data)
                    ticks.append(tick)
        
        except Exception as e:
            logger.error(f"[D205-5_REPLAY] Load error: {e}")
        
        return ticks
    
    def _replay_decisions(self, ticks: List[MarketTick]):
        """
        의사결정 재실행
        
        Args:
            ticks: MarketTick 리스트
        """
        for tick in ticks:
            try:
                replay_start_ms = time.time() * 1000
                
                # D205-8: Quote Normalization (USDT → KRW)
                upbit_quote = getattr(tick, 'upbit_quote', 'KRW')
                binance_quote = getattr(tick, 'binance_quote', 'USDT')
                
                price_a_krw = normalize_price_to_krw(tick.upbit_bid, upbit_quote, self.fx_krw_per_usdt)
                price_b_krw = normalize_price_to_krw(tick.binance_ask, binance_quote, self.fx_krw_per_usdt)
                
                # Opportunity detection (정규화된 KRW 가격으로 비교)
                candidate = detect_candidates(
                    symbol=tick.symbol,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=price_a_krw,
                    price_b=price_b_krw,
                    params=self.break_even_params,
                )
                
                replay_end_ms = time.time() * 1000
                latency_ms = replay_end_ms - replay_start_ms
                
                if candidate:
                    # D205-8: SanityGuard - units_mismatch 감지
                    gate_reasons_list = []
                    units_mismatch_detected = is_units_mismatch(candidate.spread_bps, candidate.edge_bps)
                    
                    if units_mismatch_detected:
                        gate_reasons_list.append("units_mismatch")
                        self.trace.gate_units_mismatch_count += 1
                        # DROP 처리: profitable False로 변경
                        candidate.profitable = False
                        logger.warning(
                            f"[D205-8_SANITY] Units mismatch detected: "
                            f"spread_bps={candidate.spread_bps:.2f}, edge_bps={candidate.edge_bps:.2f}"
                        )
                    
                    # D205-7: ExecutionQuality 실전 주입 (실제 계산)
                    exec_cost_breakdown = self.exec_quality_model.compute_execution_cost(
                        edge_bps=candidate.edge_bps,
                        notional=100000.0,  # 기본 10만원 주문 가정
                        upbit_bid_size=tick.upbit_bid_size,
                        upbit_ask_size=tick.upbit_ask_size,
                        binance_bid_size=tick.binance_bid_size,
                        binance_ask_size=tick.binance_ask_size,
                    )
                    
                    # Fallback 처리: size 없으면 fallback 태그
                    if (tick.upbit_bid_size is None and tick.upbit_ask_size is None and
                        tick.binance_bid_size is None and tick.binance_ask_size is None):
                        gate_reasons_list.append("exec_quality_fallback")
                    
                    # D205-8: Quote mode 계산
                    quote_mode = get_quote_mode("upbit", "binance", self.fx_krw_per_usdt)
                    
                    # 의사결정 기록 (D205-7: execution quality + D205-8: quote normalization)
                    decision = DecisionRecord(
                        timestamp=tick.timestamp,
                        symbol=tick.symbol,
                        spread_bps=candidate.spread_bps,
                        break_even_bps=compute_break_even_bps(self.break_even_params),
                        edge_bps=candidate.edge_bps,
                        profitable=candidate.profitable,
                        gate_reasons=gate_reasons_list,
                        latency_ms=latency_ms,
                        exec_cost_bps=exec_cost_breakdown.total_exec_cost_bps,
                        net_edge_after_exec_bps=exec_cost_breakdown.net_edge_after_exec_bps,
                        exec_model_version=exec_cost_breakdown.exec_model_version,
                        fx_krw_per_usdt_used=self.fx_krw_per_usdt,
                        quote_mode=quote_mode,
                        units_mismatch_warning=units_mismatch_detected,
                    )
                    
                    self.decisions.append(decision)
            
            except Exception as e:
                logger.error(f"[D205-5_REPLAY] Decision error: {e}")
    
    def _save_results(self):
        """
        결과 저장 (decisions.ndjson + manifest.json)
        """
        # 1. decisions.ndjson
        with open(self.decisions_path, "w", encoding="utf-8") as f:
            for decision in self.decisions:
                f.write(json.dumps(decision.to_dict(), ensure_ascii=False) + "\n")
        
        logger.info(f"[D205-5_REPLAY] Saved {len(self.decisions)} decisions to {self.decisions_path}")
        
        # 실제 입력 tick 수를 manifest에 저장 (결정 수와 구분)
        actual_ticks_count = len(self.decisions)  # 현재 replay에서 처리한 tick 수
        
        # Git 메타 정보 수집
        git_sha_full = ""
        git_sha_short = ""
        git_branch = ""
        try:
            git_sha_full = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_sha_short = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
        except Exception as e:
            logger.warning(f"[D205-5_REPLAY] Git info collection failed: {e}")
        
        manifest = {
            "run_id": f"replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "mode": "replay",
            "input_path": str(self.input_path.relative_to(Path.cwd())) if self.input_path.is_relative_to(Path.cwd()) else str(self.input_path),
            "input_hash": self.input_hash,
            "ticks_count": actual_ticks_count,
            "decisions_count": len(self.decisions),
            "timestamp": datetime.now().isoformat(),
            "git_sha_full": git_sha_full,
            "git_sha_short": git_sha_short,
            "branch": git_branch,
            "cmdline": " ".join(sys.argv),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
        
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D205-5_REPLAY] Saved manifest to {self.manifest_path}")
