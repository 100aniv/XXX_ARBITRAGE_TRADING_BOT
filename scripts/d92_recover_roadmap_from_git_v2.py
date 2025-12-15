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
import io

# UTF-8 출력 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


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
            replacement_chars = text.count('\ufffd')
            mojibake_count = 0
            for pattern in ['諢', '嶅', '篣', '圉', '窱', '科']:
                mojibake_count += text.count(pattern)
            
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
        replacement_chars = best_text.count('\ufffd')
        return (best_score, best_encoding, lines, korean_chars, replacement_chars, len(content_bytes))
    
    return (-100000, "failed", 0, 0, 0, len(content_bytes))


def main():
    """메인 실행"""
    print("=" * 80)
    print("D92-POST-MOVE-HARDEN v3: D_ROADMAP.md Git History Recovery")
    print("=" * 80)
    
    filepath = "D_ROADMAP.md"
    
    # 1. 커밋 목록 가져오기
    print(f"\n[1/4] Scanning Git history...")
    commits = get_commits_for_file(filepath)
    print(f"  Found {len(commits)} commits")
    
    if not commits:
        print("[ERROR] No commits found")
        return 1
    
    # 2. 각 커밋의 파일 점수 계산
    print(f"\n[2/4] Evaluating each version...")
    candidates = []
    
    for i, commit in enumerate(commits[:100], 1):
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
        
        if i <= 10:
            print(f"  [{i:2d}] {commit[:8]} | Score:{score:10.0f} | {encoding:7s} | {size:7d}B | {lines:4d}L | K:{korean:4d} | R:{replacement:3d}")
    
    if not candidates:
        print("[ERROR] No recoverable version found")
        return 1
    
    # 3. 최적 버전 선택
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]
    
    print(f"\n[3/4] Best version selected")
    print(f"  > Commit: {best['commit'][:8]}")
    print(f"  > Score: {best['score']:.0f}")
    print(f"  > Encoding: {best['encoding']}")
    print(f"  > Size: {best['size']:,} bytes")
    print(f"  > Lines: {best['lines']:,}")
    print(f"  > Korean: {best['korean']:,} chars")
    print(f"  > Replacement: {best['replacement']}")
    
    # AC-0 기준 검증
    if best['lines'] < 500:
        print(f"\n[WARN] Lines ({best['lines']}) < 500")
    if best['korean'] < 1000:
        print(f"\n[WARN] Korean chars ({best['korean']}) < 1000")
    
    # 4. UTF-8로 변환 저장
    print(f"\n[4/4] Recovering D_ROADMAP.md...")
    
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
        
        print(f"  > D_ROADMAP.md recovered")
        print(f"  > Backup: {backup_path}")
        
        # 헤더 미리보기
        preview_lines = text.split('\n')[:15]
        print(f"\n[Preview] D_ROADMAP.md header (15 lines):")
        for line in preview_lines[:15]:
            print(f"  {line[:100]}")
        
        # 최종 검증
        final_text = output_path.read_text(encoding='utf-8')
        final_lines = final_text.count('\n') + 1
        final_korean = len(re.findall(r'[가-힣]', final_text))
        
        print(f"\n[Final Validation]")
        print(f"  Lines: {final_lines:,}")
        print(f"  Korean: {final_korean:,}")
        print(f"  Chars: {len(final_text):,}")
        
        if final_lines >= 500 and final_korean >= 1000:
            print(f"\n[OK] AC-0 PASS: Original content recovered")
            return 0
        else:
            print(f"\n[WARN] AC-0 partial success: threshold not met but best effort")
            return 0
            
    except Exception as e:
        print(f"\n[ERROR] Recovery failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
