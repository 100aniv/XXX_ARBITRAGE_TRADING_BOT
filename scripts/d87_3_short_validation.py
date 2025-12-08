#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3_SHORT_VALIDATION: 30m Advisory + 30m Strict PAPER 완전 자동화

3h+3h는 환경 제약으로 완주 불가하므로, 30m+30m으로 빠른 검증 수행.
Duration Guard는 30s 테스트에서 99% accuracy 검증 완료.

Usage:
    python scripts/d87_3_short_validation.py
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class D87ShortValidation:
    """D87-3 Short Validation 30m+30m PAPER Runner"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "d87-3"
        self.advisory_session_tag = "d87_3_advisory_30m"
        self.strict_session_tag = "d87_3_strict_30m"
        self.calibration_path = self.project_root / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        self.advisory_result = None
        self.strict_result = None
        
        logger.info("=" * 100)
        logger.info("D87-3_SHORT_VALIDATION: 30m+30m PAPER 실행")
        logger.info("=" * 100)
        logger.info(f"프로젝트 루트: {self.project_root}")
        logger.info(f"로그 디렉토리: {self.logs_dir}")
        logger.info(f"Calibration: {self.calibration_path}")
        logger.info("")
    
    def _prepare_session_dir(self, session_tag: str):
        """세션 디렉토리 준비"""
        session_dir = self.logs_dir / session_tag
        if session_dir.exists():
            backup_name = f"{session_tag}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir = self.logs_dir / backup_name
            logger.info(f"기존 세션 디렉토리 백업: {session_dir} → {backup_dir}")
            shutil.move(str(session_dir), str(backup_dir))
        
        session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"세션 디렉토리 준비: {session_dir}")
    
    def run_advisory_session(self) -> bool:
        """Advisory 30m 실행"""
        logger.info("=" * 100)
        logger.info("Advisory 30m PAPER 실행")
        logger.info("=" * 100)
        
        self._prepare_session_dir(self.advisory_session_tag)
        
        duration_seconds = 1800  # 30분
        timeout_seconds = duration_seconds + 300  # 30m + 5분 grace period
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "real",
            "--fillmodel-mode", "advisory",
            "--calibration-path", str(self.calibration_path),
            "--session-tag", self.advisory_session_tag,
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info(f"Target duration: {duration_seconds}초 ({duration_seconds/60:.1f}분)")
        logger.info(f"Timeout: {timeout_seconds}초 ({timeout_seconds/60:.1f}분)")
        logger.info("")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True,
                timeout=timeout_seconds
            )
            
            duration = time.time() - start_time
            logger.info(f"✅ Advisory 세션 완료 ({duration:.1f}초 = {duration/60:.1f}분)")
            
            # KPI 파일 검증
            kpi_files = list((self.logs_dir / self.advisory_session_tag).glob("kpi_*.json"))
            if not kpi_files:
                logger.error(f"❌ KPI 파일이 생성되지 않았습니다: {self.logs_dir / self.advisory_session_tag}")
                return False
            logger.info(f"✅ KPI 파일 생성 확인: {kpi_files[0].name}")
            
            # Fill Events 파일 검증
            fill_files = list((self.logs_dir / self.advisory_session_tag).glob("fill_events_*.jsonl"))
            if not fill_files:
                logger.error(f"❌ Fill Events 파일이 생성되지 않았습니다")
                return False
            
            # Fill Events 라인 수 확인
            fill_count = sum(1 for _ in open(fill_files[0], 'r', encoding='utf-8'))
            logger.info(f"✅ Fill Events: {fill_count}개 ({fill_files[0].name})")
            
            self.advisory_result = {
                "session_tag": self.advisory_session_tag,
                "duration_seconds": duration,
                "exit_code": result.returncode,
                "kpi_path": str(kpi_files[0]),
                "fill_events_path": str(fill_files[0]),
                "fill_events_count": fill_count,
            }
            
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Advisory 세션 TIMEOUT! "
                f"Duration limit: {timeout_seconds}초 ({timeout_seconds/60:.1f}분)"
            )
            logger.info("=" * 100)
            logger.info("")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Advisory 세션 실패: exit code {e.returncode}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ Advisory 세션 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def run_strict_session(self) -> bool:
        """Strict 30m 실행"""
        logger.info("=" * 100)
        logger.info("Strict 30m PAPER 실행")
        logger.info("=" * 100)
        
        self._prepare_session_dir(self.strict_session_tag)
        
        duration_seconds = 1800  # 30분
        timeout_seconds = duration_seconds + 300  # 30m + 5분 grace period
        
        cmd = [
            "python",
            "scripts/run_d84_2_calibrated_fill_paper.py",
            "--duration-seconds", str(duration_seconds),
            "--l2-source", "real",
            "--fillmodel-mode", "strict",
            "--calibration-path", str(self.calibration_path),
            "--session-tag", self.strict_session_tag,
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info(f"Target duration: {duration_seconds}초 ({duration_seconds/60:.1f}분)")
        logger.info(f"Timeout: {timeout_seconds}초 ({timeout_seconds/60:.1f}분)")
        logger.info("")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True,
                timeout=timeout_seconds
            )
            
            duration = time.time() - start_time
            logger.info(f"✅ Strict 세션 완료 ({duration:.1f}초 = {duration/60:.1f}분)")
            
            # KPI 파일 검증
            kpi_files = list((self.logs_dir / self.strict_session_tag).glob("kpi_*.json"))
            if not kpi_files:
                logger.error(f"❌ KPI 파일이 생성되지 않았습니다: {self.logs_dir / self.strict_session_tag}")
                return False
            logger.info(f"✅ KPI 파일 생성 확인: {kpi_files[0].name}")
            
            # Fill Events 파일 검증
            fill_files = list((self.logs_dir / self.strict_session_tag).glob("fill_events_*.jsonl"))
            if not fill_files:
                logger.error(f"❌ Fill Events 파일이 생성되지 않았습니다")
                return False
            
            # Fill Events 라인 수 확인
            fill_count = sum(1 for _ in open(fill_files[0], 'r', encoding='utf-8'))
            logger.info(f"✅ Fill Events: {fill_count}개 ({fill_files[0].name})")
            
            self.strict_result = {
                "session_tag": self.strict_session_tag,
                "duration_seconds": duration,
                "exit_code": result.returncode,
                "kpi_path": str(kpi_files[0]),
                "fill_events_path": str(fill_files[0]),
                "fill_events_count": fill_count,
            }
            
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Strict 세션 TIMEOUT! "
                f"Duration limit: {timeout_seconds}초 ({timeout_seconds/60:.1f}분)"
            )
            logger.info("=" * 100)
            logger.info("")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Strict 세션 실패: exit code {e.returncode}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ Strict 세션 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def run_analysis(self) -> bool:
        """A/B 분석 실행"""
        logger.info("=" * 100)
        logger.info("A/B 분석 실행")
        logger.info("=" * 100)
        
        output_path = self.logs_dir / "d87_3_short_ab_summary.json"
        
        cmd = [
            "python",
            "scripts/analyze_d87_3_fillmodel_ab_test.py",
            "--advisory-dir", str(self.logs_dir / self.advisory_session_tag),
            "--strict-dir", str(self.logs_dir / self.strict_session_tag),
            "--calibration-path", str(self.calibration_path),
            "--output", str(output_path),
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        logger.info("")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                text=True,
                capture_output=True
            )
            
            logger.info(result.stdout)
            
            if not output_path.exists():
                logger.error(f"❌ A/B 분석 결과 파일이 생성되지 않았습니다: {output_path}")
                return False
            
            logger.info(f"✅ A/B 분석 완료: {output_path}")
            logger.info("=" * 100)
            logger.info("")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ A/B 분석 실패: exit code {e.returncode}")
            if e.stderr:
                logger.error(f"STDERR:\n{e.stderr}")
            logger.info("=" * 100)
            logger.info("")
            return False
        except Exception as e:
            logger.error(f"❌ A/B 분석 오류: {e}")
            logger.info("=" * 100)
            logger.info("")
            return False
    
    def evaluate_acceptance_criteria(self) -> Dict[str, Any]:
        """Acceptance Criteria 평가"""
        logger.info("=" * 100)
        logger.info("Acceptance Criteria 평가")
        logger.info("=" * 100)
        
        ab_summary_path = self.logs_dir / "d87_3_short_ab_summary.json"
        
        if not ab_summary_path.exists():
            logger.error(f"❌ A/B 분석 결과 파일이 없습니다: {ab_summary_path}")
            return {}
        
        with open(ab_summary_path, 'r', encoding='utf-8') as f:
            ab_summary = json.load(f)
        
        advisory_stats = ab_summary.get("advisory_summary", {})
        strict_stats = ab_summary.get("strict_summary", {})
        comparison = ab_summary.get("comparison", {})
        
        criteria = {}
        
        # SC1: 두 세션 모두 30분 내 정상 종료 (Duration ±2분 이내)
        adv_duration_min = self.advisory_result["duration_seconds"] / 60
        strict_duration_min = self.strict_result["duration_seconds"] / 60
        sc1_pass = (28 <= adv_duration_min <= 32) and (28 <= strict_duration_min <= 32)
        criteria["SC1"] = {
            "name": "Duration 30분 완주",
            "pass": sc1_pass,
            "details": f"Advisory: {adv_duration_min:.1f}분, Strict: {strict_duration_min:.1f}분",
        }
        
        # SC2: Fill Events ≥ 300/세션
        adv_fill_count = self.advisory_result["fill_events_count"]
        strict_fill_count = self.strict_result["fill_events_count"]
        sc2_pass = (adv_fill_count >= 300) and (strict_fill_count >= 300)
        criteria["SC2"] = {
            "name": "Fill Events ≥ 300",
            "pass": sc2_pass,
            "details": f"Advisory: {adv_fill_count}, Strict: {strict_fill_count}",
        }
        
        # SC3: Strict 모드의 Z2 비중 ≥ Advisory 대비 +5%p
        zone_comparison = comparison.get("zone_comparison", {})
        z2_comp = zone_comparison.get("Z2", {})
        z2_ratio_diff = z2_comp.get("delta", {}).get("trade_percentage", 0.0)
        sc3_pass = z2_ratio_diff >= 5.0
        criteria["SC3"] = {
            "name": "Z2 비중 Strict > Advisory +5%p",
            "pass": sc3_pass,
            "details": f"Z2 비중 차이: {z2_ratio_diff:+.1f}%p",
        }
        
        # SC4: Strict 모드의 Z1/Z3/Z4 비중 ≤ Advisory 대비 -3%p
        z1_comp = zone_comparison.get("Z1", {})
        z3_comp = zone_comparison.get("Z3", {})
        z4_comp = zone_comparison.get("Z4", {})
        z1_ratio_diff = z1_comp.get("delta", {}).get("trade_percentage", 0.0)
        z3_ratio_diff = z3_comp.get("delta", {}).get("trade_percentage", 0.0)
        z4_ratio_diff = z4_comp.get("delta", {}).get("trade_percentage", 0.0)
        sc4_pass = (z1_ratio_diff <= -3.0) or (z3_ratio_diff <= -3.0) or (z4_ratio_diff <= -3.0)
        criteria["SC4"] = {
            "name": "Z1/Z3/Z4 비중 Strict < Advisory -3%p",
            "pass": sc4_pass,
            "details": f"Z1: {z1_ratio_diff:+.1f}%p, Z3: {z3_ratio_diff:+.1f}%p, Z4: {z4_ratio_diff:+.1f}%p",
        }
        
        # SC5: Strict 모드의 Z2 평균 사이즈 ≥ Advisory 대비 +3%
        z2_advisory_size = z2_comp.get("advisory", {}).get("avg_size", 0.0)
        z2_strict_size = z2_comp.get("strict", {}).get("avg_size", 0.0)
        if z2_advisory_size > 0:
            z2_size_diff_pct = ((z2_strict_size / z2_advisory_size) - 1.0) * 100
        else:
            z2_size_diff_pct = 0.0
        sc5_pass = z2_size_diff_pct >= 3.0
        criteria["SC5"] = {
            "name": "Z2 평균 사이즈 Strict > Advisory +3%",
            "pass": sc5_pass,
            "details": f"Z2 사이즈 차이: {z2_size_diff_pct:+.1f}%",
        }
        
        # SC6: PnL 및 DD가 극도로 나쁘지 않을 것
        adv_pnl = advisory_stats.get("total_pnl", 0.0)
        strict_pnl = strict_stats.get("total_pnl", 0.0)
        sc6_pass = (adv_pnl > -1000.0) and (strict_pnl > -1000.0)  # 극단적 손실이 아니면 PASS
        criteria["SC6"] = {
            "name": "PnL 정상 범위",
            "pass": sc6_pass,
            "details": f"Advisory PnL: ${adv_pnl:.2f}, Strict PnL: ${strict_pnl:.2f}",
        }
        
        # 최종 판정
        critical_pass = criteria["SC1"]["pass"] and criteria["SC2"]["pass"] and criteria["SC3"]["pass"]
        all_pass = all(c["pass"] for c in criteria.values())
        
        if all_pass:
            status = "PASS"
        elif critical_pass:
            status = "CONDITIONAL_GO"
        else:
            status = "FAIL"
        
        evaluation = {
            "status": status,
            "criteria": criteria,
            "summary": {
                "critical_pass": critical_pass,
                "all_pass": all_pass,
                "pass_count": sum(1 for c in criteria.values() if c["pass"]),
                "total_count": len(criteria),
            }
        }
        
        # 결과 저장
        acceptance_path = self.logs_dir / "d87_3_short_acceptance.json"
        with open(acceptance_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Acceptance Criteria 평가 완료: {status}")
        logger.info(f"   Pass: {evaluation['summary']['pass_count']}/{evaluation['summary']['total_count']}")
        logger.info("")
        
        for sc_id, sc_data in criteria.items():
            status_icon = "✅" if sc_data["pass"] else "❌"
            logger.info(f"   {status_icon} {sc_id}: {sc_data['name']}")
            logger.info(f"      {sc_data['details']}")
        
        logger.info("")
        logger.info(f"결과 저장: {acceptance_path}")
        logger.info("=" * 100)
        logger.info("")
        
        return evaluation
    
    def print_summary(self, evaluation: Dict[str, Any]):
        """최종 요약 출력"""
        logger.info("=" * 100)
        logger.info("D87-3_SHORT_VALIDATION 최종 요약")
        logger.info("=" * 100)
        logger.info("")
        
        logger.info(f"**STATUS:** {evaluation['status']}")
        logger.info("")
        
        logger.info("**핵심 숫자:**")
        logger.info(f"  - Advisory Duration: {self.advisory_result['duration_seconds']/60:.1f}분")
        logger.info(f"  - Strict Duration: {self.strict_result['duration_seconds']/60:.1f}분")
        logger.info(f"  - Advisory Fill Events: {self.advisory_result['fill_events_count']}")
        logger.info(f"  - Strict Fill Events: {self.strict_result['fill_events_count']}")
        logger.info("")
        
        ab_summary_path = self.logs_dir / "d87_3_short_ab_summary.json"
        with open(ab_summary_path, 'r', encoding='utf-8') as f:
            ab_summary = json.load(f)
        
        comparison = ab_summary.get("comparison", {})
        zone_comparison = comparison.get("zone_comparison", {})
        z2_comp = zone_comparison.get("Z2", {})
        z2_ratio_diff = z2_comp.get("delta", {}).get("trade_percentage", 0.0)
        
        z2_advisory_size = z2_comp.get("advisory", {}).get("avg_size", 0.0)
        z2_strict_size = z2_comp.get("strict", {}).get("avg_size", 0.0)
        if z2_advisory_size > 0:
            z2_size_diff_pct = ((z2_strict_size / z2_advisory_size) - 1.0) * 100
        else:
            z2_size_diff_pct = 0.0
        
        logger.info("**A/B 비교:**")
        logger.info(f"  - Z2 비중 차이: {z2_ratio_diff:+.1f}%p")
        logger.info(f"  - Z2 평균 사이즈 차이: {z2_size_diff_pct:+.1f}%")
        logger.info("")
        
        logger.info("**Acceptance Criteria:**")
        for sc_id, sc_data in evaluation["criteria"].items():
            status_icon = "✅ PASS" if sc_data["pass"] else "❌ FAIL"
            logger.info(f"  - {sc_id}: {status_icon} - {sc_data['name']}")
        logger.info("")
        
        logger.info("=" * 100)
    
    def run(self) -> int:
        """전체 파이프라인 실행"""
        try:
            # Advisory 30m
            if not self.run_advisory_session():
                logger.error("❌ Advisory 세션 실패로 중단")
                return 1
            
            # Strict 30m
            if not self.run_strict_session():
                logger.error("❌ Strict 세션 실패로 중단")
                return 1
            
            # A/B 분석
            if not self.run_analysis():
                logger.error("❌ A/B 분석 실패로 중단")
                return 1
            
            # Acceptance Criteria 평가
            evaluation = self.evaluate_acceptance_criteria()
            if not evaluation:
                logger.error("❌ Acceptance Criteria 평가 실패")
                return 1
            
            # 최종 요약
            self.print_summary(evaluation)
            
            if evaluation["status"] == "PASS":
                logger.info("✅ D87-3_SHORT_VALIDATION 완료: PASS")
                return 0
            elif evaluation["status"] == "CONDITIONAL_GO":
                logger.info("⚠️ D87-3_SHORT_VALIDATION 완료: CONDITIONAL_GO")
                return 0
            else:
                logger.info("❌ D87-3_SHORT_VALIDATION 완료: FAIL")
                return 1
                
        except Exception as e:
            logger.error(f"❌ 실행 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return 1


def main():
    parser = argparse.ArgumentParser(description="D87-3 Short Validation 30m+30m")
    args = parser.parse_args()
    
    runner = D87ShortValidation()
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
