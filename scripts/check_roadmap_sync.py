#!/usr/bin/env python3
"""
================================================================================
D 번호 동기화 검증 (ROADMAP Sync Checker)
================================================================================
목적: D_ROADMAP.md와 TOBE_ROADMAP.md의 D 번호 목록이 1:1 일치하는지 검증

Exit Code:
  - 0: PASS (D 번호 목록 일치)
  - 2: FAIL (D 번호 불일치 또는 파일 누락)

사용:
  python scripts/check_roadmap_sync.py
"""

import re
import sys
from pathlib import Path
from typing import Set


def extract_d_numbers(file_path: Path) -> Set[str]:
    """
    ROADMAP 파일에서 D 번호 목록 추출 (## D82, ## D83 형태)
    
    Args:
        file_path: ROADMAP 파일 경로
    
    Returns:
        D 번호 집합 (예: {"D82", "D83", "D92", "D93"})
    """
    if not file_path.exists():
        return set()
    
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    
    # "## D82", "## D83" 형태의 헤더 추출
    pattern = r"^##\s+(D\d+)"
    matches = re.findall(pattern, content, re.MULTILINE)
    
    # 중복 제거 및 정렬
    d_numbers = set(matches)
    return d_numbers


def main() -> int:
    """
    메인 검증 로직
    
    Returns:
        0: PASS, 2: FAIL
    """
    print("=" * 80)
    print("ROADMAP 동기화 검증 (D 번호 일치 체크)")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    d_roadmap = project_root / "D_ROADMAP.md"
    tobe_roadmap = project_root / "TOBE_ROADMAP.md"
    
    print(f"프로젝트 루트: {project_root}\n")
    
    # 파일 존재 확인
    if not d_roadmap.exists():
        print(f"[FAIL] D_ROADMAP.md 파일이 없습니다: {d_roadmap}")
        return 2
    
    if not tobe_roadmap.exists():
        print(f"[FAIL] TOBE_ROADMAP.md 파일이 없습니다: {tobe_roadmap}")
        return 2
    
    # D 번호 추출
    d_roadmap_numbers = extract_d_numbers(d_roadmap)
    tobe_roadmap_numbers = extract_d_numbers(tobe_roadmap)
    
    print(f"D_ROADMAP.md D 번호 목록: {sorted(d_roadmap_numbers)}")
    print(f"TOBE_ROADMAP.md D 번호 목록: {sorted(tobe_roadmap_numbers)}\n")
    
    # 일치 여부 검증
    if d_roadmap_numbers == tobe_roadmap_numbers:
        print("[PASS] D 번호 목록이 1:1 일치합니다.\n")
        print("확인된 항목:")
        print(f"  - D_ROADMAP.md와 TOBE_ROADMAP.md D 번호 개수: {len(d_roadmap_numbers)}")
        print(f"  - D 번호 목록: {sorted(d_roadmap_numbers)}")
        return 0
    else:
        print("[FAIL] D 번호 목록이 일치하지 않습니다.\n")
        
        # 차이점 출력
        only_in_d = d_roadmap_numbers - tobe_roadmap_numbers
        only_in_tobe = tobe_roadmap_numbers - d_roadmap_numbers
        
        if only_in_d:
            print(f"D_ROADMAP.md에만 존재: {sorted(only_in_d)}")
        if only_in_tobe:
            print(f"TOBE_ROADMAP.md에만 존재: {sorted(only_in_tobe)}")
        
        print("\n해결 방법:")
        print("  1. D_ROADMAP.md와 TOBE_ROADMAP.md의 D 번호를 일치시키세요.")
        print("  2. 누락된 D 번호를 추가하거나, 잘못된 D 번호를 제거하세요.")
        
        return 2


if __name__ == "__main__":
    sys.exit(main())
