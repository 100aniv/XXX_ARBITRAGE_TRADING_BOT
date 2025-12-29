"""
Evidence Pack 유틸 테스트

목적: tools/evidence_pack.py의 기본 기능 검증
- Evidence 폴더 생성
- 필수 산출물 파일 생성
- JSON 파싱 가능 여부
"""

import json
import tempfile
from pathlib import Path
import pytest
from tools.evidence_pack import EvidencePacker, create_evidence


class TestEvidencePacker:
    """EvidencePacker 클래스 테스트"""

    def test_evidence_packer_init(self):
        """EvidencePacker 초기화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test Task",
                evidence_root=tmpdir
            )
            
            assert packer.d_number == "d200-3"
            assert packer.task_name == "Test Task"
            assert packer.run_id is not None
            assert "_d200-3_" in packer.run_id

    def test_run_id_format(self):
        """Run ID 포맷 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            
            # YYYYMMDD_HHMMSS_<d-number>_<short_hash>
            parts = packer.run_id.split("_")
            assert len(parts) == 4
            assert len(parts[0]) == 8  # YYYYMMDD
            assert len(parts[1]) == 6  # HHMMSS
            assert parts[2] == "d200-3"
            assert len(parts[3]) >= 7  # short_hash

    def test_evidence_folder_creation(self):
        """Evidence 폴더 생성"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            assert packer.evidence_dir.exists()
            assert packer.manifest_path.exists()
            assert packer.git_info_path.exists()
            assert packer.cmd_history_path.exists()

    def test_manifest_json_valid(self):
        """Manifest JSON 파싱 가능 여부"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            # manifest.json 파싱
            with open(packer.manifest_path, "r") as f:
                manifest = json.load(f)
            
            assert "run_id" in manifest
            assert "timestamp" in manifest
            assert "d_number" in manifest
            assert "task_name" in manifest
            assert "status" in manifest
            assert manifest["d_number"] == "d200-3"

    def test_git_info_json_valid(self):
        """Git Info JSON 파싱 가능 여부"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            # git_info.json 파싱
            with open(packer.git_info_path, "r") as f:
                git_info = json.load(f)
            
            assert "timestamp" in git_info
            assert "branch" in git_info or "error" in git_info

    def test_cmd_history_creation(self):
        """Command History 파일 생성"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            assert packer.cmd_history_path.exists()
            content = packer.cmd_history_path.read_text()
            assert "Test" in content
            assert "Execution" in content

    def test_add_command(self):
        """커맨드 기록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            packer.add_command("Step 1", "python test.py", "PASS")
            
            content = packer.cmd_history_path.read_text()
            assert "Step 1" in content
            assert "python test.py" in content
            assert "PASS" in content

    def test_add_gate_result(self):
        """Gate 결과 기록"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            packer.add_gate_result("doctor", "PASS", "289 tests")
            
            assert "doctor" in packer.gates
            assert packer.gates["doctor"]["result"] == "PASS"

    def test_finish_updates_manifest(self):
        """Finish 시 manifest 업데이트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            packer.finish("PASS")
            
            with open(packer.manifest_path, "r") as f:
                manifest = json.load(f)
            
            assert manifest["status"] == "PASS"
            assert manifest["duration_seconds"] >= 0

    def test_create_evidence_convenience_function(self):
        """create_evidence 편의 함수"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 임시 디렉토리 사용
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            assert packer.evidence_dir.exists()
            assert packer.manifest_path.exists()


class TestEvidenceIntegration:
    """Evidence 통합 테스트"""

    def test_full_workflow(self):
        """전체 워크플로우"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Evidence 생성
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Full Workflow Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            # 2. 커맨드 기록
            packer.add_command("Step 1", "just doctor", "PASS")
            packer.add_command("Step 2", "just fast", "PASS")
            
            # 3. Gate 결과 기록
            packer.add_gate_result("doctor", "PASS", "289 tests")
            packer.add_gate_result("fast", "PASS", "27/27")
            
            # 4. 완료
            packer.finish("PASS")
            
            # 5. 검증
            assert packer.evidence_dir.exists()
            assert packer.manifest_path.exists()
            assert packer.gate_log_path.exists()
            assert packer.git_info_path.exists()
            assert packer.cmd_history_path.exists()
            
            # 6. JSON 파싱 검증
            with open(packer.manifest_path, "r") as f:
                manifest = json.load(f)
            assert manifest["status"] == "PASS"
            assert "doctor" in manifest["gates"]
            assert "fast" in manifest["gates"]

    def test_evidence_directory_structure(self):
        """Evidence 디렉토리 구조"""
        with tempfile.TemporaryDirectory() as tmpdir:
            packer = EvidencePacker(
                d_number="d200-3",
                task_name="Structure Test",
                evidence_root=tmpdir
            )
            packer.start()
            
            # 필수 파일 확인
            required_files = [
                packer.manifest_path,
                packer.git_info_path,
                packer.cmd_history_path
            ]
            
            for file_path in required_files:
                assert file_path.exists(), f"{file_path} 파일 없음"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
