#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-0-RM-EXT Full-Auto 하네스

완전 자동화된 Top20 + Top50 1h Real Market PAPER Validation
- 환경 준비 → Smoke Test → Top20 1h → Top50 1h → 결과 분석 → 리포트 업데이트 → Git Commit

Usage:
    python scripts/run_d77_0_rm_ext_full_auto.py
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "prepare_d77_0_rm_ext_env.py"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_d77_0_rm_ext.py"
ANALYZE_SCRIPT = PROJECT_ROOT / "scripts" / "analyze_d77_0_rm_ext_results.py"
REPORT_FILE = PROJECT_ROOT / "docs" / "D77_0_RM_EXT_REPORT.md"
ROADMAP_FILE = PROJECT_ROOT / "D_ROADMAP.md"


class FullAutoHarness:
    """Full-Auto 하네스"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results = {
            "prepare": None,
            "smoke": None,
            "top20": None,
            "top50": None,
            "analyze": None,
            "final_decision": None
        }
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def log(self, message: str, level: str = "INFO"):
        """로그 출력"""
        prefix = {
            "INFO": "ℹ️",
            "OK": "✅",
            "ERROR": "❌",
            "WARN": "⚠️",
            "RUN": "🚀"
        }.get(level, "•")
        print(f"[{level:5s}] {prefix} {message}")
    
    def run_subprocess(self, cmd: list, description: str, timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """subprocess 실행 및 결과 반환"""
        self.log(f"{description} 시작...", "RUN")
        self.log(f"Command: {' '.join(str(c) for c in cmd)}")
        
        if self.dry_run:
            self.log(f"[DRY-RUN] 실제 실행하지 않음", "WARN")
            return 0, "", ""
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=PROJECT_ROOT
            )
            
            if result.returncode == 0:
                self.log(f"{description} 성공 (Exit Code: {result.returncode})", "OK")
            else:
                self.log(f"{description} 실패 (Exit Code: {result.returncode})", "ERROR")
            
            return result.returncode, result.stdout, result.stderr
        
        except subprocess.TimeoutExpired:
            self.log(f"{description} 시간 초과 (Timeout: {timeout}s)", "ERROR")
            return -1, "", "Timeout"
        except Exception as e:
            self.log(f"{description} 예외 발생: {e}", "ERROR")
            return -1, "", str(e)
    
    def step_prepare_env(self) -> bool:
        """환경 준비"""
        self.log("=" * 80)
        self.log("Step 1/5: 환경 준비", "INFO")
        self.log("=" * 80)
        
        cmd = [
            sys.executable,
            str(PREPARE_SCRIPT),
            "--clean-all",
            "--kill-processes"
        ]
        
        exit_code, stdout, stderr = self.run_subprocess(
            cmd,
            "환경 준비 스크립트",
            timeout=60
        )
        
        self.results["prepare"] = {
            "exit_code": exit_code,
            "success": exit_code == 0
        }
        
        return exit_code == 0
    
    def step_smoke_test(self) -> bool:
        """Smoke Test 실행 및 검증"""
        self.log("=" * 80)
        self.log("Step 2/5: Smoke Test (Top20, 3분)", "INFO")
        self.log("=" * 80)
        
        cmd = [
            sys.executable,
            str(RUNNER_SCRIPT),
            "--scenario", "smoke"
        ]
        
        exit_code, stdout, stderr = self.run_subprocess(
            cmd,
            "Smoke Test",
            timeout=600  # 10분 (3분 실행 + 여유)
        )
        
        if exit_code != 0:
            self.results["smoke"] = {"exit_code": exit_code, "success": False}
            return False
        
        # KPI 파일 찾기
        kpi_pattern = "smoke_3m_kpi.json"
        kpi_files = list((PROJECT_ROOT / "logs" / "d77-0-rm-ext").rglob(kpi_pattern))
        
        if not kpi_files:
            self.log(f"Smoke KPI 파일 없음: {kpi_pattern}", "ERROR")
            self.results["smoke"] = {"exit_code": exit_code, "success": False}
            return False
        
        # 가장 최근 파일 선택
        latest_kpi = max(kpi_files, key=lambda p: p.stat().st_mtime)
        self.log(f"Smoke KPI 파일: {latest_kpi}")
        
        # KPI 검증
        with open(latest_kpi, 'r', encoding='utf-8') as f:
            kpi = json.load(f)
        
        actual_duration = kpi.get("actual_duration_minutes", kpi.get("duration_minutes", 0))
        round_trips = kpi.get("round_trips_completed", 0)
        
        smoke_ok = (2 <= actual_duration <= 5) and (round_trips >= 1)
        
        self.log(f"Smoke 검증: Duration={actual_duration:.1f}m, RoundTrips={round_trips}", 
                 "OK" if smoke_ok else "ERROR")
        
        self.results["smoke"] = {
            "exit_code": exit_code,
            "success": smoke_ok,
            "kpi_path": str(latest_kpi),
            "duration": actual_duration,
            "round_trips": round_trips
        }
        
        return smoke_ok
    
    def step_top20_1h(self) -> bool:
        """Top20 1h 실행 및 검증"""
        self.log("=" * 80)
        self.log("Step 3/5: Top20 1h Real PAPER", "INFO")
        self.log("=" * 80)
        
        cmd = [
            sys.executable,
            str(RUNNER_SCRIPT),
            "--scenario", "primary"
        ]
        
        exit_code, stdout, stderr = self.run_subprocess(
            cmd,
            "Top20 1h",
            timeout=4200  # 70분 (60분 실행 + 10분 여유)
        )
        
        if exit_code != 0:
            self.results["top20"] = {"exit_code": exit_code, "success": False}
            return False
        
        # KPI 파일 찾기
        kpi_pattern = "1h_top20_kpi.json"
        kpi_files = list((PROJECT_ROOT / "logs" / "d77-0-rm-ext").rglob(kpi_pattern))
        
        if not kpi_files:
            self.log(f"Top20 KPI 파일 없음: {kpi_pattern}", "ERROR")
            self.results["top20"] = {"exit_code": exit_code, "success": False}
            return False
        
        latest_kpi = max(kpi_files, key=lambda p: p.stat().st_mtime)
        self.log(f"Top20 KPI 파일: {latest_kpi}")
        
        # KPI 검증
        with open(latest_kpi, 'r', encoding='utf-8') as f:
            kpi = json.load(f)
        
        actual_duration = kpi.get("actual_duration_minutes", kpi.get("duration_minutes", 0))
        round_trips = kpi.get("round_trips_completed", 0)
        
        # Critical 기준 체크 (간단 버전)
        duration_ok = 55 <= actual_duration <= 65
        round_trips_ok = round_trips >= 50
        
        top20_ok = duration_ok and round_trips_ok
        
        self.log(f"Top20 검증: Duration={actual_duration:.1f}m ({duration_ok}), "
                f"RoundTrips={round_trips} ({round_trips_ok})",
                "OK" if top20_ok else "WARN")
        
        self.results["top20"] = {
            "exit_code": exit_code,
            "success": top20_ok,
            "kpi_path": str(latest_kpi),
            "duration": actual_duration,
            "round_trips": round_trips,
            "kpi": kpi
        }
        
        return True  # 완료는 했으므로 다음 단계 진행
    
    def step_top50_1h(self) -> bool:
        """Top50 1h 실행 및 검증"""
        self.log("=" * 80)
        self.log("Step 4/5: Top50 1h Real PAPER", "INFO")
        self.log("=" * 80)
        
        cmd = [
            sys.executable,
            str(RUNNER_SCRIPT),
            "--scenario", "extended"
        ]
        
        exit_code, stdout, stderr = self.run_subprocess(
            cmd,
            "Top50 1h",
            timeout=4200  # 70분
        )
        
        if exit_code != 0:
            self.results["top50"] = {"exit_code": exit_code, "success": False}
            return False
        
        # KPI 파일 찾기
        kpi_pattern = "1h_top50_kpi.json"
        kpi_files = list((PROJECT_ROOT / "logs" / "d77-0-rm-ext").rglob(kpi_pattern))
        
        if not kpi_files:
            self.log(f"Top50 KPI 파일 없음: {kpi_pattern}", "ERROR")
            self.results["top50"] = {"exit_code": exit_code, "success": False}
            return False
        
        latest_kpi = max(kpi_files, key=lambda p: p.stat().st_mtime)
        self.log(f"Top50 KPI 파일: {latest_kpi}")
        
        # KPI 검증
        with open(latest_kpi, 'r', encoding='utf-8') as f:
            kpi = json.load(f)
        
        actual_duration = kpi.get("actual_duration_minutes", kpi.get("duration_minutes", 0))
        round_trips = kpi.get("round_trips_completed", 0)
        
        duration_ok = 55 <= actual_duration <= 65
        round_trips_ok = round_trips >= 50
        
        top50_ok = duration_ok and round_trips_ok
        
        self.log(f"Top50 검증: Duration={actual_duration:.1f}m ({duration_ok}), "
                f"RoundTrips={round_trips} ({round_trips_ok})",
                "OK" if top50_ok else "WARN")
        
        self.results["top50"] = {
            "exit_code": exit_code,
            "success": top50_ok,
            "kpi_path": str(latest_kpi),
            "duration": actual_duration,
            "round_trips": round_trips,
            "kpi": kpi
        }
        
        return True
    
    def step_analyze_results(self) -> bool:
        """결과 분석"""
        self.log("=" * 80)
        self.log("Step 5/5: 결과 분석", "INFO")
        self.log("=" * 80)
        
        if not self.results["top20"] or not self.results["top20"].get("kpi_path"):
            self.log("Top20 결과 없음, 분석 스킵", "WARN")
            return False
        
        if not self.results["top50"] or not self.results["top50"].get("kpi_path"):
            self.log("Top50 결과 없음, 분석 스킵", "WARN")
            return False
        
        cmd = [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--top20-kpi", self.results["top20"]["kpi_path"],
            "--top50-kpi", self.results["top50"]["kpi_path"]
        ]
        
        exit_code, stdout, stderr = self.run_subprocess(
            cmd,
            "결과 분석 스크립트",
            timeout=30
        )
        
        self.log(f"\n{stdout}")
        
        # stdout에서 최종 판단 추출 (간단 파싱)
        if "GO" in stdout:
            if "NO-GO" in stdout:
                decision = "NO-GO"
            elif "CONDITIONAL GO" in stdout:
                decision = "CONDITIONAL GO"
            else:
                decision = "GO"
        else:
            decision = "UNKNOWN"
        
        self.results["analyze"] = {
            "exit_code": exit_code,
            "success": exit_code == 0,
            "decision": decision,
            "output": stdout
        }
        self.results["final_decision"] = decision
        
        return exit_code == 0
    
    def update_report(self):
        """REPORT.md 업데이트"""
        self.log("=" * 80)
        self.log("리포트 업데이트", "INFO")
        self.log("=" * 80)
        
        if not REPORT_FILE.exists():
            self.log(f"리포트 파일 없음: {REPORT_FILE}", "WARN")
            return
        
        # 기존 리포트 읽기
        with open(REPORT_FILE, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # 새 섹션 생성
        new_section = f"""

---

## 📊 Full-Auto Run: {self.timestamp}

### Execution Summary
- **Smoke Test:** {"✅ PASS" if self.results["smoke"]["success"] else "❌ FAIL"}
  - Duration: {self.results["smoke"].get("duration", "N/A"):.1f} minutes
  - Round Trips: {self.results["smoke"].get("round_trips", "N/A")}

- **Top20 1h:** {"✅ PASS" if self.results["top20"]["success"] else "❌ FAIL"}
  - Duration: {self.results["top20"].get("duration", "N/A"):.1f} minutes
  - Round Trips: {self.results["top20"].get("round_trips", "N/A")}
  - Win Rate: {self.results["top20"]["kpi"].get("win_rate_pct", "N/A"):.1f}%
  - PnL: {self.results["top20"]["kpi"].get("total_pnl", "N/A"):.4f}

- **Top50 1h:** {"✅ PASS" if self.results["top50"]["success"] else "❌ FAIL"}
  - Duration: {self.results["top50"].get("duration", "N/A"):.1f} minutes
  - Round Trips: {self.results["top50"].get("round_trips", "N/A")}
  - Win Rate: {self.results["top50"]["kpi"].get("win_rate_pct", "N/A"):.1f}%
  - PnL: {self.results["top50"]["kpi"].get("total_pnl", "N/A"):.4f}

### Final Decision
**{self.results["final_decision"]}**

### Next Steps
{"- D78 Authentication & Secrets 진행" if self.results["final_decision"] == "GO" else "- Gap 분석 및 개선 계획 수립"}
"""
        
        # 리포트 업데이트 (마지막에 추가)
        updated_content = report_content.rstrip() + new_section
        
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        self.log(f"리포트 업데이트 완료: {REPORT_FILE}", "OK")
    
    def update_roadmap(self):
        """ROADMAP.md 업데이트"""
        self.log("=" * 80)
        self.log("로드맵 업데이트", "INFO")
        self.log("=" * 80)
        
        if not ROADMAP_FILE.exists():
            self.log(f"로드맵 파일 없음: {ROADMAP_FILE}", "WARN")
            return
        
        # 기존 로드맵 읽기
        with open(ROADMAP_FILE, 'r', encoding='utf-8') as f:
            roadmap_content = f.read()
        
        # D77-0-RM-EXT 섹션 찾아서 상태 업데이트
        # 간단한 치환 (실제로는 더 정교하게 파싱)
        if self.results["final_decision"] == "GO":
            new_status = "✅ COMPLETE"
        elif self.results["final_decision"] == "CONDITIONAL GO":
            new_status = "⚠️ CONDITIONAL"
        else:
            new_status = "⚠️ PARTIAL"
        
        # D77-0-RM-EXT Status 업데이트 (간단 치환)
        if "Status: ⚠️ PARTIAL" in roadmap_content and self.results["final_decision"] in ["GO", "CONDITIONAL GO"]:
            roadmap_content = roadmap_content.replace(
                "Status: ⚠️ PARTIAL",
                f"Status: {new_status}",
                1  # D77-0-RM-EXT 섹션만
            )
            
            with open(ROADMAP_FILE, 'w', encoding='utf-8') as f:
                f.write(roadmap_content)
            
            self.log(f"로드맵 업데이트 완료: Status → {new_status}", "OK")
        else:
            self.log("로드맵 업데이트 스킵 (이미 최신 상태 또는 섹션 없음)", "WARN")
    
    def git_commit(self):
        """Git commit"""
        self.log("=" * 80)
        self.log("Git Commit", "INFO")
        self.log("=" * 80)
        
        # git status
        cmd_status = ["git", "status", "--short"]
        exit_code, stdout, stderr = self.run_subprocess(cmd_status, "Git status", timeout=10)
        
        if not stdout.strip():
            self.log("변경 사항 없음, commit 스킵", "WARN")
            return
        
        self.log(f"변경 파일:\n{stdout}")
        
        # git add
        files_to_add = [
            str(REPORT_FILE.relative_to(PROJECT_ROOT)),
            str(ROADMAP_FILE.relative_to(PROJECT_ROOT))
        ]
        
        cmd_add = ["git", "add"] + files_to_add
        exit_code, stdout, stderr = self.run_subprocess(cmd_add, "Git add", timeout=10)
        
        if exit_code != 0:
            self.log("Git add 실패", "ERROR")
            return
        
        # git commit
        commit_msg = f"[D77-0-RM-EXT] Full-auto Top20+Top50 1h validation - {self.results['final_decision']}"
        cmd_commit = ["git", "commit", "-m", commit_msg]
        exit_code, stdout, stderr = self.run_subprocess(cmd_commit, "Git commit", timeout=10)
        
        if exit_code == 0:
            self.log(f"Git commit 완료: {commit_msg}", "OK")
        else:
            self.log(f"Git commit 실패 (아마 변경 없음)", "WARN")
    
    def run(self) -> int:
        """전체 실행"""
        self.log("=" * 80)
        self.log("D77-0-RM-EXT Full-Auto 하네스 시작", "INFO")
        self.log("=" * 80)
        self.log(f"Timestamp: {self.timestamp}")
        self.log(f"Dry-Run: {self.dry_run}")
        self.log("")
        
        # Step 1: 환경 준비
        if not self.step_prepare_env():
            self.log("환경 준비 실패, 중단", "ERROR")
            return 1
        
        # Step 2: Smoke Test
        if not self.step_smoke_test():
            self.log("Smoke Test 실패, 중단", "ERROR")
            return 1
        
        # Step 3: Top20 1h
        if not self.step_top20_1h():
            self.log("Top20 1h 실패, 중단", "ERROR")
            return 1
        
        # Step 4: Top50 1h
        if not self.step_top50_1h():
            self.log("Top50 1h 실패, 중단", "ERROR")
            return 1
        
        # Step 5: 결과 분석
        if not self.step_analyze_results():
            self.log("결과 분석 실패", "WARN")
        
        # 리포트 & 로드맵 업데이트
        self.update_report()
        self.update_roadmap()
        
        # Git commit
        self.git_commit()
        
        # 최종 요약
        self.log("")
        self.log("=" * 80)
        self.log("Full-Auto 하네스 완료", "OK")
        self.log("=" * 80)
        self.log(f"최종 판단: {self.results['final_decision']}")
        self.log("")
        
        return 0 if self.results["final_decision"] in ["GO", "CONDITIONAL GO"] else 1


def main():
    parser = argparse.ArgumentParser(description="D77-0-RM-EXT Full-Auto 하네스")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run 모드")
    
    args = parser.parse_args()
    
    harness = FullAutoHarness(dry_run=args.dry_run)
    return harness.run()


if __name__ == "__main__":
    sys.exit(main())
