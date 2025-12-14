#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 POST-MOVE-HARDEN v2: D_ROADMAP.md UTF-8 자동 복구

Git 히스토리에서 정상 UTF-8 버전을 자동 탐지하고 복구.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional


def get_git_root() -> Path:
    """Git 루트 디렉토리 찾기"""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True
    )
    return Path(result.stdout.strip())


def get_roadmap_commits() -> List[str]:
    """D_ROADMAP.md를 수정한 모든 커밋 목록"""
    result = subprocess.run(
        ["git", "rev-list", "--all", "--", "D_ROADMAP.md"],
        capture_output=True,
        text=True,
        check=True
    )
    commits = result.stdout.strip().split('\n')
    return [c for c in commits if c]


def get_file_at_commit(commit: str, filepath: str) -> Optional[bytes]:
    """특정 커밋의 파일 내용 가져오기 (바이트)"""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{filepath}"],
            capture_output=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def score_utf8_quality(content: bytes) -> Tuple[float, str]:
    """
    UTF-8 품질 점수 계산
    
    Returns:
        (score, reason) - 높을수록 좋음
    """
    reasons = []
    score = 0.0
    
    # 1. UTF-8 디코딩 시도
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError as e:
        return -1000.0, f"UTF-8 디코딩 실패: {e}"
    
    # 2. 한글(가-힣) 비율
    korean_chars = len(re.findall(r'[가-힣]', text))
    total_chars = len(text)
    if total_chars > 0:
        korean_ratio = korean_chars / total_chars
        score += korean_ratio * 100
        reasons.append(f"한글 비율: {korean_ratio:.2%}")
    
    # 3. 모지바케 패턴 감지 (諢嶅, 篣圉, 窱科 등)
    mojibake_patterns = [
        r'諢', r'嶅', r'篣', r'圉', r'窱', r'科',
        r'鴔', r'穈', r'韠', r'窶', r'賈', r'䁯'
    ]
    mojibake_count = sum(len(re.findall(p, text)) for p in mojibake_patterns)
    if mojibake_count > 0:
        score -= mojibake_count * 10
        reasons.append(f"모지바케 패턴: {mojibake_count}개")
    
    # 4. Replacement character (�) 개수
    replacement_count = text.count('�')
    if replacement_count > 0:
        score -= replacement_count * 20
        reasons.append(f"Replacement char: {replacement_count}개")
    
    # 5. 기본 마크다운 구조 확인
    if text.startswith('# '):
        score += 10
        reasons.append("마크다운 헤더 있음")
    
    # 6. 키워드 존재 여부 (정상 파일이면 있어야 함)
    keywords = ['arbitrage-lite', 'ROADMAP', 'D92', 'D77']
    keyword_count = sum(1 for kw in keywords if kw in text)
    score += keyword_count * 5
    reasons.append(f"키워드: {keyword_count}/{len(keywords)}")
    
    reason_str = " | ".join(reasons)
    return score, reason_str


def find_best_commit(commits: List[str]) -> Optional[Tuple[str, float, str]]:
    """가장 품질 좋은 커밋 찾기"""
    best_commit = None
    best_score = -float('inf')
    best_reason = ""
    
    print(f"\n🔍 {len(commits)}개 커밋 스캔 중...")
    
    for i, commit in enumerate(commits[:50], 1):  # 최근 50개만 스캔
        content = get_file_at_commit(commit, "D_ROADMAP.md")
        if not content:
            continue
        
        score, reason = score_utf8_quality(content)
        
        # 상위 5개만 출력
        if i <= 5 or score > 0:
            print(f"  [{i:2d}] {commit[:8]} | Score: {score:7.1f} | {reason}")
        
        if score > best_score:
            best_score = score
            best_commit = commit
            best_reason = reason
    
    if best_commit:
        return best_commit, best_score, best_reason
    return None


def recover_roadmap(git_root: Path, commit: str) -> bool:
    """선택된 커밋에서 D_ROADMAP.md 복구"""
    content = get_file_at_commit(commit, "D_ROADMAP.md")
    if not content:
        return False
    
    # UTF-8로 디코딩 확인
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        return False
    
    # 파일 저장
    roadmap_path = git_root / "D_ROADMAP.md"
    with open(roadmap_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return True


def main():
    """메인 실행"""
    print("=" * 80)
    print("D92 POST-MOVE-HARDEN v2: D_ROADMAP.md UTF-8 자동 복구")
    print("=" * 80)
    
    try:
        git_root = get_git_root()
        print(f"📁 Git 루트: {git_root}")
        
        commits = get_roadmap_commits()
        if not commits:
            print("❌ D_ROADMAP.md 수정 커밋을 찾을 수 없습니다.")
            return 1
        
        print(f"📝 D_ROADMAP.md 수정 커밋: {len(commits)}개")
        
        result = find_best_commit(commits)
        if not result:
            print("\n❌ 정상 UTF-8 버전을 찾을 수 없습니다.")
            print("   대안: docs/D* 문서들을 스캔해서 ROADMAP 재생성 필요")
            return 1
        
        best_commit, best_score, best_reason = result
        
        print("\n" + "=" * 80)
        print(f"✅ 최적 커밋 발견: {best_commit[:8]}")
        print(f"   Score: {best_score:.1f}")
        print(f"   {best_reason}")
        print("=" * 80)
        
        # 복구 실행
        print("\n🔧 D_ROADMAP.md 복구 중...")
        if recover_roadmap(git_root, best_commit):
            print("✅ 복구 완료!")
            
            # 복구 후 품질 재확인
            roadmap_path = git_root / "D_ROADMAP.md"
            with open(roadmap_path, 'rb') as f:
                recovered_content = f.read()
            
            final_score, final_reason = score_utf8_quality(recovered_content)
            print(f"\n📊 복구 파일 품질: Score={final_score:.1f}")
            print(f"   {final_reason}")
            
            # 한글 샘플 출력
            with open(roadmap_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:5]
            print("\n📄 복구 파일 헤더 (처음 5줄):")
            for line in lines:
                print(f"   {line.rstrip()}")
            
            return 0
        else:
            print("❌ 복구 실패")
            return 1
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Git 명령 실패: {e}")
        return 1
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
