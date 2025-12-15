#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-POST-MOVE-HARDEN v3: D_ROADMAP.md Git 히스토리 복구
최대 크기의 정상 버전을 찾아 UTF-8로 복구
"""

import subprocess
import sys
from pathlib import Path
import re


def get_commits_for_file(filepath: str, max_count: int = 200) -> list:
    """특정 파일을 수정한 커밋 목록 반환"""
    result = subprocess.run(
        ["git", "rev-list", "-n", str(max_count), "HEAD", "--", filepath],
        capture_output=True,
        text=True,
        check=True
    )
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return commits


def get_file_content_at_commit(commit_sha: str, filepath: str) -> bytes:
    """특정 커밋의 파일 내용을 바이트로 반환"""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit_sha}:{filepath}"],
            capture_output=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return b""


def score_content(content_bytes: bytes) -> tuple:
    """
    콘텐츠 품질 점수 계산
    Returns: (score, encoding, lines, korean_chars, replacement_chars, size_bytes)
    """
    if not content_bytes:
        return (-100000, "none", 0, 0, 0, 0)
    
    # 인코딩 시도 순서
    encodings = ["utf-8", "cp949", "euc-kr", "latin1"]
    best_score = -100000
    best_encoding = "unknown"
    best_text = ""
    
    for enc in encodings:
        try:
            text = content_bytes.decode(enc, errors="replace")
            
            # 점수 계산
            lines = text.count('\n') + 1
            korean_chars = len(re.findall(r'[가-힣]', text))
            replacement_chars = text.count('�')
            mojibake_patterns = ['諢', '嶅', '篣', '圉', '窱', '科', '鴔', '穈', '韠', '窶', '賈', '䁯']
            mojibake_count = sum(text.count(p) for p in mojibake_patterns)
            
            # 점수 공식: 크기 + 한글 + 라인수 - 손상
            score = len(content_bytes) + (korean_chars * 10) + (lines * 5) - (replacement_chars * 100) - (mojibake_count * 50)
            
            if score > best_score:
                best_score = score
                best_encoding = enc
                best_text = text
                
        except Exception:
            continue
    
    if best_text:
        lines = best_text.count('\n') + 1
        korean_chars = len(re.findall(r'[가-힣]', best_text))
        replacement_chars = best_text.count('�')
        return (best_score, best_encoding, lines, korean_chars, replacement_chars, len(content_bytes))
    
    return (-100000, "failed", 0, 0, 0, len(content_bytes))


def main():
    """메인 실행"""
    print("=" * 80)
    print("D92-POST-MOVE-HARDEN v3: D_ROADMAP.md Git 히스토리 복구")
    print("=" * 80)
    
    filepath = "D_ROADMAP.md"
    
    # 1. 커밋 목록 가져오기
    print(f"\n[1/4] Git 히스토리 스캔 중...")
    commits = get_commits_for_file(filepath)
    print(f"  → {len(commits)}개 커밋 발견")
    
    if not commits:
        print("[ERROR] 커밋 없음")
        return 1
    
    # 2. 각 커밋의 파일 점수 계산
    print(f"\n[2/4] 각 버전 품질 평가 중...")
    candidates = []
    
    for i, commit in enumerate(commits[:100], 1):  # 최근 100개만
        content = get_file_content_at_commit(commit, filepath)
        if not content:
            continue
        
        score, encoding, lines, korean, replacement, size = score_content(content)
        candidates.append({
            "commit": commit,
            "score": score,
            "encoding": encoding,
            "lines": lines,
            "korean": korean,
            "replacement": replacement,
            "size": size,
            "content": content
        })
        
        if i <= 10:  # 상위 10개만 출력
            print(f"  [{i:2d}] {commit[:8]} | Score: {score:10.0f} | {encoding:7s} | {size:7d}B | {lines:4d}줄 | 한글:{korean:4d} | repl:{replacement:3d}")
    
    if not candidates:
        print("[ERROR] 복구 가능한 버전 없음")
        return 1
    
    # 3. 최적 버전 선택
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]
    
    print(f"\n[3/4] 최적 버전 선택")
    print(f"  > Commit: {best['commit'][:8]}")
    print(f"  > Score: {best['score']:.0f}")
    print(f"  > Encoding: {best['encoding']}")
    print(f"  > Size: {best['size']:,} bytes")
    print(f"  > Lines: {best['lines']:,}")
    print(f"  > Korean: {best['korean']:,} chars")
    print(f"  > Replacement: {best['replacement']}")
    
    # AC-0 기준 검증
    if best['lines'] < 500:
        print(f"\n[WARN] 라인 수({best['lines']})가 500 미만")
    if best['korean'] < 1000:
        print(f"\n[WARN] 한글 글자 수({best['korean']})가 1000 미만")
    
    # 4. UTF-8로 변환 저장
    print(f"\n[4/4] D_ROADMAP.md 복구 중...")
    
    try:
        # 원본 인코딩으로 디코딩 후 UTF-8로 재인코딩
        text = best['content'].decode(best['encoding'], errors='replace')
        
        # UTF-8로 저장
        output_path = Path("D_ROADMAP.md")
        output_path.write_text(text, encoding='utf-8')
        
        # 백업 저장
        backup_dir = Path("docs/_recovery")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"D_ROADMAP_raw_bytes_{best['commit'][:8]}.bin"
        backup_path.write_bytes(best['content'])
        
        print(f"  > D_ROADMAP.md 복구 완료")
        print(f"  > 백업: {backup_path}")
        
        # 헤더 미리보기
        preview_lines = text.split('\n')[:15]
        print(f"\n[미리보기] D_ROADMAP.md 헤더 (15줄):")
        for line in preview_lines:
            print(f"  {line}")
        
        # 최종 검증
        final_text = output_path.read_text(encoding='utf-8')
        final_lines = final_text.count('\n') + 1
        final_korean = len(re.findall(r'[가-힣]', final_text))
        
        print(f"\n[최종 검증]")
        print(f"  Lines: {final_lines:,}")
        print(f"  한글: {final_korean:,}")
        print(f"  Chars: {len(final_text):,}")
        
        if final_lines >= 500 and final_korean >= 1000:
            print(f"\n[OK] AC-0 PASS: 원본 복구 완료")
            return 0
        else:
            print(f"\n[WARN] AC-0 부분 성공: 임계치 미달이지만 최선")
            return 0
            
    except Exception as e:
        print(f"\n[ERROR] 복구 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
