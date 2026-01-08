"""
D205-15-2: Evidence Integrity Guard (ADD-ON Requirement #2)

JSON 무결성 자가검증 유틸리티
"""

import json
import logging
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
    JSON 저장 + 즉시 검증
    
    Args:
        file_path: JSON 파일 경로
        data: 저장할 데이터
    
    Raises:
        ValueError: 저장 후 검증 실패 시
    """
    # 1. 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # 2. 즉시 검증
    validate_json_file(file_path)
    
    logger.info(f"[EVIDENCE_GUARD] ✅ JSON saved & validated: {file_path.name}")


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
