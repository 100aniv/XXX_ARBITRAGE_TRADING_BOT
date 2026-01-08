"""
D205-15-2: Evidence Integrity Guard (ADD-ON Requirement #2)
D205-15-3: Atomic Write 강화 (temp → fsync → rename)

JSON 무결성 자가검증 유틸리티
- 저장 즉시 재파싱 검증
- Atomic write로 부분 기록 방지
- PowerShell stdout/stderr 혼입 방지
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def validate_json_file(file_path: Path) -> Dict[str, Any]:
    """
    JSON 파일 무결성 검증
    
    Args:
        file_path: JSON 파일 경로
    
    Returns:
        검증 결과 딕셔너리
    
    Raises:
        ValueError: JSON 파싱 실패 시
    """
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        logger.info(f"[EVIDENCE_GUARD] ✅ JSON valid: {file_path.name}")
        
        return {
            "file": str(file_path),
            "status": "valid",
            "size_bytes": file_path.stat().st_size,
            "top_level_keys": list(data.keys()) if isinstance(data, dict) else None,
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"[EVIDENCE_GUARD] ❌ JSON invalid: {file_path.name} - {e}")
        raise ValueError(f"JSON parse error in {file_path}: {e}")
    
    except UnicodeDecodeError as e:
        logger.error(f"[EVIDENCE_GUARD] ❌ Encoding error: {file_path.name} - {e}")
        raise ValueError(f"Encoding error in {file_path}: {e}")


def save_json_with_validation(file_path: Path, data: Any) -> None:
    """
    JSON 저장 + 즉시 검증 (D205-15-3: Atomic Write)
    
    Args:
        file_path: JSON 파일 경로
        data: 저장할 데이터
    
    Raises:
        ValueError: 저장 후 검증 실패 시
    
    Note:
        D205-15-3 강화: temp file → fsync → rename (atomic write)
        - 부분 기록 방지
        - PowerShell stdout/stderr 혼입 방지
    """
    file_path = Path(file_path)
    parent_dir = file_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    
    # D205-15-3: Atomic write (temp → fsync → rename)
    temp_fd = None
    temp_path = None
    
    try:
        # 1. 임시 파일에 쓰기
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".json.tmp",
            dir=str(parent_dir),
            text=True,
        )
        
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            temp_fd = None  # fdopen이 소유권 가져감
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        
        # 2. Atomic rename (기존 파일 덮어쓰기)
        temp_path_obj = Path(temp_path)
        temp_path_obj.replace(file_path)
        temp_path = None  # 성공적으로 이동됨
        
        # 3. 즉시 검증 (재파싱)
        validate_json_file(file_path)
        
        logger.info(f"[EVIDENCE_GUARD] ✅ JSON saved atomically & validated: {file_path.name}")
        
    except Exception as e:
        # 실패 시 임시 파일 정리
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except Exception:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        
        logger.error(f"[EVIDENCE_GUARD] ❌ Atomic save failed: {file_path.name} - {e}")
        raise ValueError(f"Atomic JSON save failed for {file_path}: {e}")


def audit_evidence_directory(evidence_dir: Path) -> Dict[str, Any]:
    """
    Evidence 디렉토리 전체 JSON 검증
    
    Args:
        evidence_dir: Evidence 디렉토리 경로
    
    Returns:
        검증 결과 딕셔너리
    """
    results = {
        "total_json_files": 0,
        "valid_files": 0,
        "invalid_files": 0,
        "details": [],
    }
    
    for json_file in evidence_dir.rglob("*.json"):
        results["total_json_files"] += 1
        
        try:
            validate_result = validate_json_file(json_file)
            results["valid_files"] += 1
            results["details"].append(validate_result)
        
        except ValueError as e:
            results["invalid_files"] += 1
            results["details"].append({
                "file": str(json_file),
                "status": "invalid",
                "error": str(e),
            })
    
    logger.info(
        f"[EVIDENCE_GUARD] Audit complete: "
        f"{results['valid_files']}/{results['total_json_files']} valid"
    )
    
    return results
