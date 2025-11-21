#!/usr/bin/env python3
"""
D73-D77 로드맵 재구조화 자동 적용 스크립트

기존 D_ROADMAP.md의 Line 716-774를 삭제하고
docs/D73_D77_ROADMAP_RESTRUCTURE.md의 D73-D77 내용으로 교체합니다.
"""

import sys
from pathlib import Path

def main():
    # 파일 경로
    base_dir = Path(__file__).parent.parent
    roadmap_file = base_dir / "D_ROADMAP.md"
    restructure_file = base_dir / "docs" / "D73_D77_ROADMAP_RESTRUCTURE.md"
    
    print("=" * 80)
    print("D73-D77 로드맵 재구조화 자동 적용 스크립트")
    print("=" * 80)
    
    # 1. 기존 D_ROADMAP.md 읽기
    print(f"\n[1/5] 기존 D_ROADMAP.md 읽기...")
    with open(roadmap_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"  ✅ 총 {len(lines)}줄 읽음")
    
    # 2. 삭제할 영역 찾기 (Line 716-774)
    print(f"\n[2/5] 삭제할 영역 찾기...")
    
    # Line 715 찾기: "**세부 내역:** `docs/SYSTEM_DESIGN.md` 참조"
    line_715_idx = None
    for i, line in enumerate(lines):
        if "**세부 내역:** `docs/SYSTEM_DESIGN.md` 참조" in line:
            line_715_idx = i
            break
    
    if line_715_idx is None:
        print("  ❌ Line 715를 찾을 수 없습니다.")
        return 1
    
    print(f"  ✅ Line 715 발견: {line_715_idx + 1}")
    
    # Line 775 찾기: "⸻" (D80~D89 섹션 직전)
    # Line 774 이후에서 "⸻"를 찾음
    line_775_idx = None
    for i in range(line_715_idx + 1, min(line_715_idx + 100, len(lines))):
        if lines[i].strip() == "⸻":
            line_775_idx = i
            break
    
    if line_775_idx is None:
        print("  ❌ Line 775 (⸻)를 찾을 수 없습니다.")
        return 1
    
    print(f"  ✅ Line 775 발견: {line_775_idx + 1}")
    print(f"  📍 삭제 영역: Line {line_715_idx + 2} ~ {line_775_idx} ({line_775_idx - line_715_idx - 1}줄)")
    
    # 3. 새 D73-D77 내용 읽기
    print(f"\n[3/5] 새 D73-D77 내용 읽기...")
    with open(restructure_file, 'r', encoding='utf-8') as f:
        restructure_lines = f.readlines()
    
    # "# D73-D77 상세 내용 (한글)" 섹션 찾기
    start_idx = None
    for i, line in enumerate(restructure_lines):
        if "# D73-D77 상세 내용 (한글)" in line:
            start_idx = i + 1  # 헤더 다음 줄부터
            break
    
    if start_idx is None:
        print("  ❌ D73-D77 상세 내용을 찾을 수 없습니다.")
        return 1
    
    # "---" 또는 파일 끝까지 읽기
    new_content_lines = []
    for i in range(start_idx, len(restructure_lines)):
        line = restructure_lines[i]
        # "## 적용 방법" 섹션 전까지만
        if line.startswith("## 적용 방법") or line.startswith("---"):
            break
        new_content_lines.append(line)
    
    # 마지막 "⸻" 이후 빈 줄 제거
    while new_content_lines and new_content_lines[-1].strip() == "":
        new_content_lines.pop()
    
    print(f"  ✅ 새 내용 {len(new_content_lines)}줄 준비됨")
    
    # 4. 교체 수행
    print(f"\n[4/5] 교체 수행...")
    new_lines = (
        lines[:line_715_idx + 1] +  # Line 1~715
        ["\n"] +                      # 빈 줄
        new_content_lines +           # 새 D73-D77 내용
        ["\n"] +                      # 빈 줄
        lines[line_775_idx:]          # Line 775~끝
    )
    
    print(f"  ✅ 새 파일: {len(new_lines)}줄 (기존 {len(lines)}줄 → 변경: {len(new_lines) - len(lines):+d}줄)")
    
    # 5. 파일 쓰기
    print(f"\n[5/5] D_ROADMAP.md 업데이트...")
    with open(roadmap_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"  ✅ 업데이트 완료!")
    
    print("\n" + "=" * 80)
    print("✅ D73-D77 로드맵 재구조화 완료!")
    print("=" * 80)
    print("\n다음 단계:")
    print("  1. git add D_ROADMAP.md")
    print("  2. git diff --stat --cached")
    print("  3. git commit -m \"[ROADMAP] D73-D77 재구조화 적용\"")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
