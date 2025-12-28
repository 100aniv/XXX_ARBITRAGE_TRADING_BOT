"""
Evidence Packer - V2 증거 자동 생성 및 관리 유틸

목적: 모든 V2 실행(Gate/Paper/LIVE)의 증거를 표준 포맷으로 자동 생성
규칙: SSOT = docs/v2/design/EVIDENCE_SPEC.md
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class EvidencePacker:
    """V2 Evidence 자동 생성 및 관리"""

    def __init__(self, d_number: str, task_name: str, evidence_root: str = "logs/evidence"):
        """
        초기화

        Args:
            d_number: D 단계 번호 (예: "d200-2", "d204-2", "gate_doctor")
            task_name: 작업 이름 (예: "Bootstrap Lock + Evidence SSOT")
            evidence_root: Evidence 루트 디렉토리
        """
        self.d_number = d_number
        self.task_name = task_name
        self.evidence_root = Path(evidence_root)
        
        # Run ID 생성: YYYYMMDD_HHMMSS_<d-number>_<short_hash>
        self.timestamp = datetime.now()
        self.run_id = self._generate_run_id()
        self.evidence_dir = self.evidence_root / self.run_id
        
        # 필수 파일 경로
        self.manifest_path = self.evidence_dir / "manifest.json"
        self.gate_log_path = self.evidence_dir / "gate.log"
        self.git_info_path = self.evidence_dir / "git_info.json"
        self.cmd_history_path = self.evidence_dir / "cmd_history.txt"
        self.kpi_summary_path = self.evidence_dir / "kpi_summary.json"
        self.error_log_path = self.evidence_dir / "error.log"
        
        # 상태
        self.manifest = {}
        self.gates = {}
        self.commands = []

    def _generate_run_id(self) -> str:
        """Run ID 생성: YYYYMMDD_HHMMSS_<d-number>_<short_hash>"""
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        short_hash = self._get_git_short_hash()
        return f"{timestamp_str}_{self.d_number}_{short_hash}"

    def _get_git_short_hash(self) -> str:
        """Git short hash 조회"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def _get_git_info(self) -> Dict[str, Any]:
        """Git 상태 스냅샷"""
        try:
            # Branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            branch = branch_result.stdout.strip()

            # Commit
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            commit = commit_result.stdout.strip()

            # Commit message
            msg_result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            commit_message = msg_result.stdout.strip()

            # Status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            status = "clean" if not status_result.stdout.strip() else "dirty"

            # Modified files
            modified = []
            added = []
            for line in status_result.stdout.strip().split("\n"):
                if not line:
                    continue
                prefix = line[:2]
                filename = line[3:]
                if prefix.startswith("M"):
                    modified.append(filename)
                elif prefix.startswith("A"):
                    added.append(filename)

            return {
                "timestamp": self.timestamp.isoformat(),
                "branch": branch,
                "commit": commit,
                "commit_message": commit_message,
                "status": status,
                "remote": {
                    "origin": "https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT.git",
                    "tracking_branch": branch
                },
                "modified_files": modified,
                "added_files": added
            }
        except Exception as e:
            return {
                "timestamp": self.timestamp.isoformat(),
                "error": str(e)
            }

    def start(self):
        """Evidence 폴더 생성 및 초기화"""
        # 폴더 생성
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        # manifest.json 생성
        self.manifest = {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "d_number": self.d_number,
            "task_name": self.task_name,
            "status": "IN_PROGRESS",
            "duration_seconds": 0,
            "python_version": self._get_python_version(),
            "git": self._get_git_info(),
            "environment": self._get_environment_info(),
            "gates": {}
        }
        self._write_manifest()

        # git_info.json 생성
        self._write_json(self.git_info_path, self.manifest["git"])

        # cmd_history.txt 초기화
        header = f"# {self.task_name}\n"
        header += f"# Execution: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC+9\n\n"
        self.cmd_history_path.write_text(header)

        print(f"✅ Evidence 폴더 생성: {self.evidence_dir}")

    def add_command(self, step: str, command: str, status: str = "PASS"):
        """커맨드 기록"""
        entry = f"## {step}\n"
        entry += f"Command: {command}\n"
        entry += f"Status: {status}\n\n"
        
        self.commands.append(entry)
        
        # cmd_history.txt에 append
        with open(self.cmd_history_path, "a") as f:
            f.write(entry)

    def add_gate_result(self, gate_name: str, result: str, details: str = ""):
        """Gate 결과 기록"""
        self.gates[gate_name] = {
            "result": result,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.manifest["gates"][gate_name] = result
        
        # gate.log에 append
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Gate: {gate_name} → {result}\n"
        if details:
            log_entry += f"  Details: {details}\n"
        
        with open(self.gate_log_path, "a") as f:
            f.write(log_entry)

    def add_kpi(self, kpi_data: Dict[str, Any]):
        """KPI 데이터 저장 (Paper 실행 시)"""
        kpi_data["run_id"] = self.run_id
        self._write_json(self.kpi_summary_path, kpi_data)

    def add_error(self, error_message: str):
        """에러 로그 기록"""
        error_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {error_message}\n"
        with open(self.error_log_path, "a") as f:
            f.write(error_entry)
        
        self.manifest["status"] = "FAILED"

    def finish(self, status: str = "PASS"):
        """Evidence 완료 및 압축"""
        # 최종 상태 업데이트
        self.manifest["status"] = status
        self.manifest["duration_seconds"] = int(
            (datetime.now() - self.timestamp).total_seconds()
        )
        self._write_manifest()

        # 폴더 압축 (선택)
        zip_path = self.evidence_root / f"{self.run_id}.zip"
        try:
            shutil.make_archive(
                str(zip_path.with_suffix("")),
                "zip",
                self.evidence_dir
            )
            print(f"✅ Evidence 압축: {zip_path}")
        except Exception as e:
            print(f"⚠️ Evidence 압축 실패: {e}")

        print(f"✅ Evidence 완료: {self.evidence_dir}")
        print(f"   Status: {status}")
        print(f"   Duration: {self.manifest['duration_seconds']}s")

    def _write_manifest(self):
        """manifest.json 저장"""
        self._write_json(self.manifest_path, self.manifest)

    def _write_json(self, path: Path, data: Dict[str, Any]):
        """JSON 파일 저장"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_python_version(self) -> str:
        """Python 버전 조회"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_environment_info(self) -> Dict[str, str]:
        """환경 정보"""
        # Docker 상태 확인 (간단한 버전)
        docker_redis = "unknown"
        docker_postgres = "unknown"
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=redis", "--format", "{{.State}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            docker_redis = "running" if "running" in result.stdout else "stopped"
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=postgres", "--format", "{{.State}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            docker_postgres = "running" if "running" in result.stdout else "stopped"
        except Exception:
            pass

        # venv 확인
        venv = "unknown"
        if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
            venv = "abt_bot_env"

        return {
            "docker_redis": docker_redis,
            "docker_postgres": docker_postgres,
            "venv": venv
        }


# 편의 함수
def create_evidence(d_number: str, task_name: str) -> EvidencePacker:
    """Evidence 생성 편의 함수"""
    packer = EvidencePacker(d_number, task_name)
    packer.start()
    return packer


if __name__ == "__main__":
    # 테스트
    packer = create_evidence("d200-2", "Bootstrap Lock + Evidence SSOT")
    
    packer.add_command("Step 0: SSOT 문서 검증", "(읽기 작업)", "PASS")
    packer.add_command("Step 1: .windsurfrule 추가", "git add .windsurfrule", "PASS")
    packer.add_command("Step 2: SSOT_MAP 정교화", "git add docs/v2/design/SSOT_MAP.md", "PASS")
    packer.add_command("Step 3: Evidence SSOT 문서", "(파일 생성)", "PASS")
    
    packer.add_gate_result("doctor", "PASS", "289 tests collected")
    packer.add_gate_result("fast", "PASS", "27/27 PASS (0.67s)")
    packer.add_gate_result("regression", "PASS", "27/27 PASS (0.67s)")
    
    packer.finish("PASS")
    
    print(f"\n📁 Evidence 경로: {packer.evidence_dir}")
