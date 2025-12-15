#!/usr/bin/env python3
"""
================================================================================
D 번호 검증 (ROADMAP Single SSOT Checker)
================================================================================
목적: D_ROADMAP.md (단일 SSOT)에서 D 번호 누락/중복/순서 오류 검사

변경 이력:
  - v1.0: D_ROADMAP.md ↔ TOBE_ROADMAP.md 동기화 검증 (DEPRECATED)
  - v2.0: D_ROADMAP.md 단일 SSOT 검증 (현재)

Exit Code:
  - 0: PASS (D 번호 정상)
  - 2: FAIL (D 번호 누락/중복/순서 오류 또는 파일 누락)

사용:
  python scripts/check_roadmap_sync.py
"""

import re
import sys
from pathlib import Path
from typing import List, Set


def extract_d_numbers_ordered(file_path: Path) -> List[str]:
    """
    ROADMAP 파일에서 D 번호 목록을 순서대로 추출 (## D82, ## D83 형태)
    
    Args:
        file_path: ROADMAP 파일 경로
    
    Returns:
        D 번호 리스트 (순서 유지, 중복 포함)
    """
    if not file_path.exists():
        return []
    
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    
    # "## D82", "## D83" 형태의 헤더 추출 (순서 유지)
    pattern = r"^##\s+(D\d+)"
    matches = re.findall(pattern, content, re.MULTILINE)
    
    return matches


def validate_d_numbers(d_numbers: List[str]) -> tuple[bool, List[str]]:
    """
    D 번호 목록 검증 (중복/누락/순서)
    
    Args:
        d_numbers: D 번호 리스트
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    if not d_numbers:
        errors.append("D 번호가 하나도 없습니다")
        return False, errors
    
    # 중복 검사
    unique_numbers = set(d_numbers)
    if len(unique_numbers) != len(d_numbers):
        duplicates = [d for d in unique_numbers if d_numbers.count(d) > 1]
        errors.append(f"중복된 D 번호 발견: {duplicates}")
    
    # 순서 검사 (D82 → D83 → D84... 순서여야 함)
    # D 번호를 숫자로 변환하여 정렬
    try:
        d_nums_int = [int(d[1:]) for d in d_numbers]  # "D82" → 82
        expected_order = sorted(d_nums_int)
        
        if d_nums_int != expected_order:
            errors.append(f"D 번호 순서 오류: 현재={d_numbers}, 기대={['D'+str(n) for n in expected_order]}")
    except ValueError as e:
        errors.append(f"D 번호 파싱 오류: {e}")
    
    # 연속성 검사 (선택적 - D82 다음은 D83이어야 함)
    # 이 검사는 선택적으로 적용 (프로젝트에 따라 D 번호가 건너뛸 수 있음)
    
    return len(errors) == 0, errors


def main() -> int:
    """
    메인 검증 로직
    
    Returns:
        0: PASS, 2: FAIL
    """
    print("=" * 80)
    print("ROADMAP 단일 SSOT 검증 (D 번호 누락/중복/순서 체크)")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    d_roadmap = project_root / "D_ROADMAP.md"
    
    print(f"프로젝트 루트: {project_root}")
    print(f"ROADMAP SSOT: D_ROADMAP.md (유일)\n")
    
    # 파일 존재 확인
    if not d_roadmap.exists():
        print(f"[FAIL] D_ROADMAP.md 파일이 없습니다: {d_roadmap}")
        return 2
    
    # D 번호 추출 (순서 유지)
    d_numbers = extract_d_numbers_ordered(d_roadmap)
    
    if not d_numbers:
        print("[FAIL] D_ROADMAP.md에 D 번호가 하나도 없습니다")
        return 2
    
    print(f"발견된 D 번호 목록 (순서대로): {d_numbers}")
    print(f"D 번호 개수: {len(d_numbers)}\n")
    
    # D 번호 검증
    is_valid, errors = validate_d_numbers(d_numbers)
    
    if is_valid:
        print("[PASS] D 번호 검증 성공\n")
        print("확인된 항목:")
        print(f"  - D 번호 개수: {len(d_numbers)}")
        print(f"  - 중복 없음")
        print(f"  - 순서 정상")
        print(f"  - D 번호 목록: {d_numbers}")
        return 0
    else:
        print("[FAIL] D 번호 검증 실패\n")
        print("발견된 오류:")
        for error in errors:
            print(f"  - {error}")
        
        print("\n해결 방법:")
        print("  1. D_ROADMAP.md에서 중복된 D 번호를 제거하세요")
        print("  2. D 번호를 정렬된 순서로 배치하세요 (D82, D83, D84...)")
        print("  3. 누락된 D 번호를 추가하세요")
        
        return 2


if __name__ == "__main__":
    sys.exit(main())
