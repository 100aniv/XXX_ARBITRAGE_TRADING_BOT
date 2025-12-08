#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3.3: 3h+3h PAPER Long-run Validation & Live Monitoring

완전 자동화 파이프라인:
1. 환경 점검 및 정리 (Redis/DB 초기화, 중복 프로세스 kill)
2. 3h+3h PAPER 실행 (orchestrator 호출)
3. 실시간 모니터링 (heartbeat, trade 카운트, 에러 감지)
4. 종료 후 A/B 분석 및 Acceptance Criteria 평가
5. 문서 자동 업데이트 및 git commit

Usage:
    python scripts/d87_3_run_and_monitor.py
"""

import argparse
import json
import logging
import os
import psutil
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

# 로깅 설정
log_format = "[%(asctime)s] [%(levelname)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class D87ValidationMonitor:
    """D87-3.3 Long-run Validation 완전 자동화 모니터"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs" / "d87-3"
        
        # 세션 경로
        self.advisory_dir = self.logs_dir / "d87_3_advisory_3h"
        self.strict_dir = self.logs_dir / "d87_3_strict_3h"
        self.calibration_path = self.project_root / "logs" / "d86-1" / "calibration_20251207_123906.json"
        
        # 모니터링 로그
        self.monitor_log_path = self.logs_dir / "d87_3_monitor_3h3h.log"
        self.monitor_json_path = self.logs_dir / "d87_3_monitor_3h3h.json"
        
        # A/B 분석 결과
        self.ab_summary_path = self.logs_dir / "d87_3_ab_summary_3h.json"
        self.acceptance_path = self.logs_dir / "d87_3_acceptance_3h.json"
        
        # 실행 정보
        self.start_time = None
        self.orchestrator_process = None
        self.monitor_data = {
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
            "advisory_duration": 0,
            "strict_duration": 0,
            "heartbeats": [],
            "errors": [],
            "warnings": [],
            "status": "NOT_STARTED",
        }
        
        # 파일 핸들러 추가
        self.setup_file_logging()
    
    def setup_file_logging(self):
        """파일 로깅 설정"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(self.monitor_log_path, mode='a')
        file_handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)
    
    def log_error(self, message: str):
        """에러 로그 및 기록"""
        logger.error(message)
        self.monitor_data["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
    
    def log_warning(self, message: str):
        """경고 로그 및 기록"""
        logger.warning(message)
        self.monitor_data["warnings"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
    
    def save_monitor_data(self):
        """모니터링 데이터 저장"""
        with open(self.monitor_json_path, 'w') as f:
            json.dump(self.monitor_data, f, indent=2)
    
    # ==================== Pre-flight: 환경 점검 및 정리 ====================
    
    def check_virtual_env(self) -> bool:
        """가상환경 확인"""
        venv_path = os.environ.get("VIRTUAL_ENV", None)
        if venv_path:
            logger.info(f"✅ 가상환경 활성화됨: {venv_path}")
            return True
        else:
            self.log_warning("가상환경이 활성화되지 않았습니다. 계속 진행합니다.")
            return True  # Warning이지만 계속 진행
    
    def kill_duplicate_processes(self):
        """중복 프로세스 정리"""
        logger.info("중복 프로세스 정리 중...")
        
        killed_count = 0
        target_keywords = [
            "d87_3_longrun_orchestrator",
            "run_d84_2_calibrated_fill_paper",
            "topn_arbitrage",
        ]
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # 현재 프로세스 제외
                if proc.pid == os.getpid():
                    continue
                
                # 타겟 키워드 매칭
                if any(keyword in cmdline_str for keyword in target_keywords):
                    logger.info(f"  중복 프로세스 종료: PID={proc.pid}, CMD={cmdline_str[:100]}")
                    proc.kill()
                    killed_count += 1
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_count > 0:
            logger.info(f"✅ {killed_count}개 프로세스 종료 완료")
            time.sleep(2)  # 프로세스 종료 대기
        else:
            logger.info("✅ 중복 프로세스 없음")
    
    def check_docker_services(self) -> bool:
        """Docker 서비스 확인"""
        logger.info("Docker 서비스 확인 중...")
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            containers = result.stdout.strip().split('\n')
            
            has_postgres = any('postgres' in c.lower() for c in containers)
            has_redis = any('redis' in c.lower() for c in containers)
            
            if has_postgres and has_redis:
                logger.info(f"✅ Docker 서비스 정상: Postgres={has_postgres}, Redis={has_redis}")
                return True
            else:
                self.log_error(f"Docker 서비스 부족: Postgres={has_postgres}, Redis={has_redis}")
                return False
        
        except subprocess.CalledProcessError as e:
            self.log_error(f"Docker 명령 실패: {e}")
            return False
    
    def check_calibration_file(self) -> bool:
        """Calibration 파일 확인"""
        if self.calibration_path.exists():
            logger.info(f"✅ Calibration 파일 존재: {self.calibration_path}")
            return True
        else:
            self.log_error(f"❌ CRITICAL: Calibration 파일 없음: {self.calibration_path}")
            return False
    
    def initialize_redis_db(self):
        """Redis/DB 초기화 (선택적)"""
        logger.info("Redis/DB 초기화 생략 (기존 데이터 유지)")
        # 필요 시 FLUSHALL 등 추가 가능
    
    def pre_flight_check(self) -> bool:
        """Pre-flight 전체 점검"""
        logger.info("=" * 100)
        logger.info("D87-3.3 PRE-FLIGHT CHECK")
        logger.info("=" * 100)
        
        checks = [
            ("가상환경", self.check_virtual_env()),
            ("Docker 서비스", self.check_docker_services()),
            ("Calibration 파일", self.check_calibration_file()),
        ]
        
        # 중복 프로세스 정리
        self.kill_duplicate_processes()
        
        # Redis/DB 초기화
        self.initialize_redis_db()
        
        # 로그 디렉토리 준비
        self.advisory_dir.mkdir(parents=True, exist_ok=True)
        self.strict_dir.mkdir(parents=True, exist_ok=True)
        
        # 결과 검증
        all_passed = all(result for _, result in checks)
        
        if all_passed:
            logger.info("=" * 100)
            logger.info("✅ PRE-FLIGHT CHECK 완료 - 실행 준비 완료")
            logger.info("=" * 100)
        else:
            logger.error("=" * 100)
            logger.error("❌ PRE-FLIGHT CHECK 실패 - 실행 중단")
            logger.error("=" * 100)
        
        return all_passed
    
    # ==================== 6시간 실행 및 모니터링 ====================
    
    def start_orchestrator(self) -> Optional[subprocess.Popen]:
        """Orchestrator 프로세스 시작"""
        logger.info("=" * 100)
        logger.info("ORCHESTRATOR 시작")
        logger.info("=" * 100)
        
        cmd = [
            "python",
            "scripts/d87_3_longrun_orchestrator.py",
            "--mode", "full"
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            logger.info(f"✅ Orchestrator 시작 완료 (PID: {process.pid})")
            return process
        
        except Exception as e:
            self.log_error(f"Orchestrator 시작 실패: {e}")
            return None
    
    def monitor_output_line(self, line: str):
        """출력 라인 모니터링"""
        # 콘솔 출력
        print(line, end='')
        
        # 에러 패턴 감지
        error_patterns = [
            r'ERROR',
            r'Traceback',
            r'Rate limit',
            r'429',
            r'ConnectionError',
            r'Timeout'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.log_error(f"에러 패턴 감지: {line.strip()}")
                break
    
    def get_file_size_mb(self, file_path: Path) -> float:
        """파일 크기 (MB) 반환"""
        if file_path.exists():
            return file_path.stat().st_size / (1024 * 1024)
        return 0.0
    
    def heartbeat_check(self) -> Dict[str, Any]:
        """Heartbeat 체크"""
        advisory_fill_files = list(self.advisory_dir.glob("fill_events_*.jsonl"))
        strict_fill_files = list(self.strict_dir.glob("fill_events_*.jsonl"))
        
        advisory_size = sum(self.get_file_size_mb(f) for f in advisory_fill_files)
        strict_size = sum(self.get_file_size_mb(f) for f in strict_fill_files)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "advisory_fill_mb": round(advisory_size, 2),
            "strict_fill_mb": round(strict_size, 2),
        }
    
    def monitor_execution(self, process: subprocess.Popen):
        """실행 모니터링"""
        logger.info("=" * 100)
        logger.info("실시간 모니터링 시작")
        logger.info("예상 소요 시간: ~6시간")
        logger.info("=" * 100)
        
        last_heartbeat = time.time()
        heartbeat_interval = 300  # 5분
        
        while True:
            # 출력 라인 읽기
            line = process.stdout.readline()
            if line:
                self.monitor_output_line(line)
            
            # 프로세스 종료 확인
            if process.poll() is not None:
                break
            
            # Heartbeat 체크
            if time.time() - last_heartbeat >= heartbeat_interval:
                elapsed = time.time() - self.start_time
                heartbeat = self.heartbeat_check()
                heartbeat["elapsed_minutes"] = int(elapsed / 60)
                
                self.monitor_data["heartbeats"].append(heartbeat)
                self.save_monitor_data()
                
                logger.info("")
                logger.info(f"[HEARTBEAT] {elapsed/60:.0f}분 경과 | "
                          f"Advisory: {heartbeat['advisory_fill_mb']}MB | "
                          f"Strict: {heartbeat['strict_fill_mb']}MB")
                logger.info("")
                
                last_heartbeat = time.time()
        
        # 최종 exit code 확인
        exit_code = process.wait()
        
        elapsed = time.time() - self.start_time
        self.monitor_data["duration_seconds"] = int(elapsed)
        
        logger.info("=" * 100)
        if exit_code == 0:
            logger.info(f"✅ Orchestrator 정상 종료 (소요 시간: {elapsed/3600:.2f}시간)")
            self.monitor_data["status"] = "COMPLETED"
            return True
        else:
            self.log_error(f"❌ Orchestrator 비정상 종료 (Exit code: {exit_code})")
            self.monitor_data["status"] = "FAILED"
            return False
    
    # ==================== A/B 분석 및 Acceptance Criteria ====================
    
    def run_analyzer(self) -> bool:
        """A/B 분석 실행"""
        logger.info("=" * 100)
        logger.info("A/B 분석 실행")
        logger.info("=" * 100)
        
        cmd = [
            "python",
            "scripts/analyze_d87_3_fillmodel_ab_test.py",
            "--advisory-dir", str(self.advisory_dir),
            "--strict-dir", str(self.strict_dir),
            "--calibration-path", str(self.calibration_path),
            "--output", str(self.ab_summary_path),
        ]
        
        logger.info(f"명령: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info("✅ A/B 분석 완료")
            logger.info(result.stdout)
            return True
        
        except subprocess.CalledProcessError as e:
            self.log_error(f"A/B 분석 실패: {e}")
            logger.error(e.stderr)
            return False
    
    def evaluate_acceptance_criteria(self) -> Dict[str, Any]:
        """Acceptance Criteria 평가"""
        logger.info("=" * 100)
        logger.info("ACCEPTANCE CRITERIA 평가")
        logger.info("=" * 100)
        
        if not self.ab_summary_path.exists():
            self.log_error("A/B 분석 결과 파일이 존재하지 않습니다")
            return {}
        
        with open(self.ab_summary_path, 'r') as f:
            ab_result = json.load(f)
        
        comparison = ab_result.get("comparison", {})
        advisory = comparison.get("advisory", {})
        strict = comparison.get("strict", {})
        zone_comparison = comparison.get("zone_comparison", {})
        
        # C1: 완주
        c1_pass = self.monitor_data["status"] == "COMPLETED"
        c1_reason = "Advisory & Strict 3h 완주" if c1_pass else "실행 중 오류 발생"
        
        # C2: 데이터 충분성
        adv_events = advisory.get("total_fill_events", 0)
        str_events = strict.get("total_fill_events", 0)
        c2_pass = adv_events >= 1000 and str_events >= 1000
        c2_reason = f"Advisory={adv_events}, Strict={str_events} (목표: ≥1000)"
        
        # C3: Z2 집중 효과
        adv_z2_pct = zone_comparison.get("Z2", {}).get("advisory", {}).get("trade_percentage", 0)
        str_z2_pct = zone_comparison.get("Z2", {}).get("strict", {}).get("trade_percentage", 0)
        z2_delta = str_z2_pct - adv_z2_pct
        c3_pass = z2_delta >= 10.0
        c3_reason = f"Z2 Delta = {z2_delta:+.1f}%p (목표: ≥+10%p)"
        
        # C4: Z1/Z3/Z4 회피
        adv_other_pct = sum(
            zone_comparison.get(z, {}).get("advisory", {}).get("trade_percentage", 0)
            for z in ["Z1", "Z3", "Z4"]
        )
        str_other_pct = sum(
            zone_comparison.get(z, {}).get("strict", {}).get("trade_percentage", 0)
            for z in ["Z1", "Z3", "Z4"]
        )
        other_delta = str_other_pct - adv_other_pct
        c4_pass = other_delta <= -5.0
        c4_reason = f"Z1+Z3+Z4 Delta = {other_delta:+.1f}%p (목표: ≤-5%p)"
        
        # C5: Z2 사이즈 증가
        adv_z2_size = zone_comparison.get("Z2", {}).get("advisory", {}).get("avg_size", 0)
        str_z2_size = zone_comparison.get("Z2", {}).get("strict", {}).get("avg_size", 0)
        size_ratio = (str_z2_size / adv_z2_size) if adv_z2_size > 0 else 0
        c5_pass = size_ratio >= 1.05
        c5_reason = f"Z2 Size Ratio = {size_ratio:.3f} (목표: ≥1.05)"
        
        # C6: 리스크 균형
        adv_pnl = advisory.get("total_pnl", 0)
        str_pnl = strict.get("total_pnl", 0)
        pnl_ratio = (str_pnl / adv_pnl) if adv_pnl != 0 else 0
        c6_pass = 0.8 <= pnl_ratio <= 1.2
        c6_reason = f"PnL Ratio = {pnl_ratio:.3f} (목표: 0.8~1.2)"
        
        criteria = {
            "C1": {"pass": c1_pass, "reason": c1_reason, "priority": "Critical"},
            "C2": {"pass": c2_pass, "reason": c2_reason, "priority": "Critical"},
            "C3": {"pass": c3_pass, "reason": c3_reason, "priority": "Critical"},
            "C4": {"pass": c4_pass, "reason": c4_reason, "priority": "High"},
            "C5": {"pass": c5_pass, "reason": c5_reason, "priority": "High"},
            "C6": {"pass": c6_pass, "reason": c6_reason, "priority": "Medium"},
        }
        
        # 로그 출력
        logger.info("")
        for cid, result in criteria.items():
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            logger.info(f"  {cid} ({result['priority']}): {status} - {result['reason']}")
        
        # 전체 판정
        critical_pass = all(criteria[c]["pass"] for c in ["C1", "C2", "C3"])
        high_pass = all(criteria[c]["pass"] for c in ["C4", "C5"])
        
        if critical_pass and high_pass:
            overall = "PASS"
        elif critical_pass:
            overall = "CONDITIONAL_GO"
        else:
            overall = "FAIL"
        
        logger.info("")
        logger.info(f"최종 판정: {overall}")
        logger.info("=" * 100)
        
        result = {
            "criteria": criteria,
            "overall": overall,
            "evaluation_time": datetime.now().isoformat(),
        }
        
        # JSON 저장
        with open(self.acceptance_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    # ==================== 문서 업데이트 및 Git ====================
    
    def update_documentation(self, acceptance_result: Dict[str, Any]):
        """문서 업데이트"""
        logger.info("=" * 100)
        logger.info("문서 업데이트")
        logger.info("=" * 100)
        
        logger.info("D87_3_EXECUTION_SUMMARY.md 업데이트 필요 (수동 검토)")
        logger.info("D_ROADMAP.md 업데이트 필요 (수동 검토)")
        
        # TODO: 실제 파일 읽기/쓰기로 자동 업데이트 구현 가능
    
    def run_tests(self) -> bool:
        """테스트 실행"""
        logger.info("=" * 100)
        logger.info("테스트 실행")
        logger.info("=" * 100)
        
        cmd = ["python", "-m", "pytest", "tests/test_d87_3_analyzer.py", "-v"]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info("✅ 테스트 통과")
            logger.info(result.stdout)
            return True
        
        except subprocess.CalledProcessError as e:
            self.log_error(f"테스트 실패: {e}")
            logger.error(e.stderr)
            return False
    
    def git_commit(self, acceptance_result: Dict[str, Any]):
        """Git commit"""
        overall = acceptance_result.get("overall", "UNKNOWN")
        
        if overall != "PASS":
            logger.info(f"⚠️  최종 판정이 {overall}이므로 git commit 생략")
            return
        
        logger.info("=" * 100)
        logger.info("Git commit")
        logger.info("=" * 100)
        
        try:
            subprocess.run(["git", "add", "-A"], cwd=str(self.project_root), check=True)
            subprocess.run(
                ["git", "commit", "-m", "[D87-3.3] 3h+3h PAPER Validation & Monitoring"],
                cwd=str(self.project_root),
                check=True
            )
            logger.info("✅ Git commit 완료")
        
        except subprocess.CalledProcessError as e:
            self.log_warning(f"Git commit 실패: {e}")
    
    # ==================== 메인 실행 ====================
    
    def run(self):
        """전체 파이프라인 실행"""
        self.start_time = time.time()
        self.monitor_data["start_time"] = datetime.now().isoformat()
        self.monitor_data["status"] = "RUNNING"
        
        try:
            # 1. Pre-flight 점검
            if not self.pre_flight_check():
                self.monitor_data["status"] = "PRE_FLIGHT_FAILED"
                self.save_monitor_data()
                sys.exit(1)
            
            # 2. Orchestrator 실행
            process = self.start_orchestrator()
            if not process:
                self.monitor_data["status"] = "START_FAILED"
                self.save_monitor_data()
                sys.exit(1)
            
            # 3. 실시간 모니터링
            success = self.monitor_execution(process)
            
            if not success:
                self.save_monitor_data()
                sys.exit(1)
            
            # 4. A/B 분석
            if not self.run_analyzer():
                self.monitor_data["status"] = "ANALYSIS_FAILED"
                self.save_monitor_data()
                sys.exit(1)
            
            # 5. Acceptance Criteria 평가
            acceptance_result = self.evaluate_acceptance_criteria()
            
            # 6. 문서 업데이트
            self.update_documentation(acceptance_result)
            
            # 7. 테스트
            if not self.run_tests():
                self.log_warning("테스트 실패했지만 계속 진행")
            
            # 8. Git commit
            self.git_commit(acceptance_result)
            
            # 최종 저장
            self.monitor_data["end_time"] = datetime.now().isoformat()
            self.save_monitor_data()
            
            logger.info("=" * 100)
            logger.info("✅ D87-3.3 Long-run Validation 완료")
            logger.info(f"결과: {acceptance_result.get('overall', 'UNKNOWN')}")
            logger.info(f"모니터링 로그: {self.monitor_log_path}")
            logger.info(f"분석 결과: {self.ab_summary_path}")
            logger.info("=" * 100)
        
        except Exception as e:
            self.log_error(f"예외 발생: {e}")
            self.monitor_data["status"] = "EXCEPTION"
            self.save_monitor_data()
            raise


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D87-3.3: 3h+3h PAPER Long-run Validation & Live Monitoring"
    )
    
    args = parser.parse_args()
    
    monitor = D87ValidationMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
