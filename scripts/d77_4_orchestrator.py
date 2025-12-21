#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-4 Orchestrator - 완전 자동화 메인 엔트리

전체 Validation Phase를 자동으로 orchestrate:
1. env_checker 실행
2. 60초 스모크 실행 + monitor
3. 스모크 PASS 시 1h 실행 + monitor  
4. analyzer 실행
5. reporter 실행
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)


class D77Orchestrator:
    """D77-4 완전 자동화 오케스트레이터"""
    
    def __init__(self, project_root: Path, mode: str = "full"):
        self.project_root = project_root
        self.mode = mode  # "smoke-only" | "full"
        self.run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log_dir = project_root / "logs" / "d77-4" / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # D99-5: 인스턴스별 고유 logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}.{id(self)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self._log_handler = None
        
        # 로그 파일 핸들러 추가
        log_file = self.log_dir / "orchestrator.log"
        self._log_handler = logging.FileHandler(log_file, encoding='utf-8')
        self._log_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        self.logger.addHandler(self._log_handler)
        
        self.logger.info(f"[D77-4 Orchestrator] 시작 (mode={mode}, run_id={self.run_id})")
    
    def close(self):
        """명시적 cleanup - D99-5"""
        if self._log_handler:
            try:
                self._log_handler.flush()
                self.logger.removeHandler(self._log_handler)
                self._log_handler.close()
                self._log_handler = None
                self.logger.handlers.clear()
            except Exception:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __del__(self):
        self.close()
    
    def run(self) -> int:
        """전체 플로우 실행
        
        Returns:
            Exit code (0=성공, 1=실패)
        """
        try:
            # Step 1: 환경 체크
            if not self._run_env_checker():
                self.logger.error("환경 체크 실패")
                return 1
            
            # Step 2: 60초 스모크 테스트
            smoke_kpi_path = self._run_smoke_test()
            if not smoke_kpi_path or not smoke_kpi_path.exists():
                self.logger.error("스모크 테스트 실패")
                return 1
            
            # 스모크 결과 간단 판단
            if not self._check_smoke_pass(smoke_kpi_path):
                self.logger.error("스모크 테스트 FAIL → 중단")
                return 1
            
            self.logger.info("[OK] 스모크 테스트 PASS")
            
            if self.mode == "smoke-only":
                self.logger.info("smoke-only 모드 → 여기서 종료")
                return 0
            
            # Step 3: 1시간 본 실행
            full_kpi_path = self._run_full_test()
            if not full_kpi_path or not full_kpi_path.exists():
                self.logger.error("1시간 본 실행 실패")
                return 1
            
            # Step 4: 분석
            analysis_result_path = self._run_analyzer(full_kpi_path)
            if not analysis_result_path or not analysis_result_path.exists():
                self.logger.error("분석 실패")
                return 1
            
            # Step 5: 리포트 생성
            if not self._run_reporter(analysis_result_path):
                self.logger.error("리포트 생성 실패")
                return 1
            
            self.logger.info("[OK] 전체 플로우 완료")
            return 0
            
        except KeyboardInterrupt:
            self.logger.warning("사용자 중단 (Ctrl+C)")
            return 1
        except Exception as e:
            self.logger.exception(f"예외 발생: {e}")
            return 1
    
    def _run_env_checker(self) -> bool:
        """환경 체커 실행"""
        self.logger.info("[Step 1/5] 환경 체크 실행")
        
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "d77_4_env_checker.py"),
            "--run-id", self.run_id
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            self.logger.info("환경 체크 성공")
            return True
        else:
            self.logger.error(f"환경 체크 실패: {result.stderr}")
            return False
    
    def _run_smoke_test(self) -> Optional[Path]:
        """60초 스모크 테스트 실행"""
        self.logger.info("[Step 2/5] 60초 스모크 테스트 실행")
        
        kpi_path = self.log_dir / "smoke_60s_kpi.json"
        console_log = self.log_dir / "smoke_60s_console.log"
        
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py"),
            "--data-source", "real",
            "--topn-size", "20",
            "--run-duration-seconds", "60",
            "--monitoring-enabled",
            "--kpi-output-path", str(kpi_path)
        ]
        
        # 서브프로세스로 Runner 실행 (로그는 파일로)
        with open(console_log, 'w', encoding='utf-8') as log_f:
            proc = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=self.project_root
            )
            
            self.logger.info(f"Runner 프로세스 시작: PID={proc.pid}")
            
            # 완료 대기 (타임아웃 120초)
            try:
                proc.wait(timeout=120)
                self.logger.info(f"Runner 종료: exit_code={proc.returncode}")
                
                if proc.returncode == 0:
                    return kpi_path
                else:
                    self.logger.error(f"Runner 실패: exit_code={proc.returncode}")
                    return None
            except subprocess.TimeoutExpired:
                self.logger.error("Runner 타임아웃 (120초)")
                proc.kill()
                return None
    
    def _check_smoke_pass(self, kpi_path: Path) -> bool:
        """스모크 테스트 PASS 여부 확인"""
        try:
            import json
            with open(kpi_path, 'r', encoding='utf-8') as f:
                kpi = json.load(f)
            
            # 간단한 체크: round_trips >= 1, crash = 0
            round_trips = kpi.get("round_trips_completed", 0)
            if round_trips < 1:
                self.logger.warning(f"Round trips = {round_trips} < 1 → FAIL")
                return False
            
            self.logger.info(f"스모크 KPI: round_trips={round_trips}")
            return True
        except Exception as e:
            self.logger.error(f"스모크 KPI 로드 실패: {e}")
            return False
    
    def _run_full_test(self) -> Optional[Path]:
        """1시간 본 실행"""
        self.logger.info("[Step 3/5] 1시간 본 실행")
        
        kpi_path = self.log_dir / "full_1h_kpi.json"
        console_log = self.log_dir / "full_1h_console.log"
        
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py"),
            "--data-source", "real",
            "--topn-size", "50",
            "--run-duration-seconds", "3600",
            "--monitoring-enabled",
            "--kpi-output-path", str(kpi_path)
        ]
        
        with open(console_log, 'w', encoding='utf-8') as log_f:
            proc = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=self.project_root
            )
            
            self.logger.info(f"Runner 프로세스 시작: PID={proc.pid}")
            
            # 1시간 + 여유 10분 타임아웃
            try:
                proc.wait(timeout=4200)
                self.logger.info(f"Runner 종료: exit_code={proc.returncode}")
                
                if proc.returncode == 0:
                    return kpi_path
                else:
                    self.logger.error(f"Runner 실패: exit_code={proc.returncode}")
                    return None
            except subprocess.TimeoutExpired:
                self.logger.error("Runner 타임아웃 (70분)")
                proc.kill()
                return None
    
    def _run_analyzer(self, kpi_path: Path) -> Optional[Path]:
        """분석기 실행"""
        self.logger.info("[Step 4/5] 분석기 실행")
        
        console_log = self.log_dir / "full_1h_console.log"
        
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "d77_4_analyzer.py"),
            "--run-id", self.run_id,
            "--kpi-path", str(kpi_path),
            "--console-log-path", str(console_log)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        analysis_result_path = self.log_dir / "analysis_result.json"
        
        if result.returncode == 0 or analysis_result_path.exists():
            self.logger.info("분석 완료")
            return analysis_result_path
        else:
            self.logger.error(f"분석 실패: {result.stderr}")
            return None
    
    def _run_reporter(self, analysis_result_path: Path) -> bool:
        """리포터 실행"""
        self.logger.info("[Step 5/5] 리포터 실행")
        
        cmd = [
            sys.executable,
            str(self.project_root / "scripts" / "d77_4_reporter.py"),
            "--run-id", self.run_id,
            "--analysis-result-path", str(analysis_result_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            self.logger.info("리포트 생성 완료")
            return True
        else:
            self.logger.error(f"리포트 생성 실패: {result.stderr}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="D77-4 Orchestrator - 완전 자동화 Validation Phase"
    )
    parser.add_argument(
        "--mode",
        choices=["smoke-only", "full"],
        default="full",
        help="실행 모드: smoke-only (60초만) | full (전체 플로우)"
    )
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    
    orchestrator = D77Orchestrator(project_root, mode=args.mode)
    exit_code = orchestrator.run()
    
    print(f"\n{'='*80}")
    print(f"D77-4 Orchestrator Complete")
    print(f"Mode: {args.mode}")
    print(f"Result: {'SUCCESS' if exit_code == 0 else 'FAIL'}")
    print(f"Run ID: {orchestrator.run_id}")
    print(f"Logs: {orchestrator.log_dir}")
    print(f"{'='*80}\n")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
