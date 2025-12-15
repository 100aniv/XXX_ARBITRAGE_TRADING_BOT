#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-POST-MOVE-HARDEN v3: D_ROADMAP.md 인코딩 재변환
latin1으로 읽힌 텍스트를 올바른 인코딩으로 재해석
"""

from pathlib import Path
import re

# 백업 파일 읽기
backup_path = Path("docs/_recovery/D_ROADMAP_raw_bytes_a5a61da1.bin")
raw_bytes = backup_path.read_bytes()

print(f"Raw bytes: {len(raw_bytes):,}")

# 다양한 인코딩 시도
encodings = [
    ("utf-8",),
    ("cp949",),
    ("euc-kr",),
    ("latin1",),
]

results = []

for enc_tuple in encodings:
    try:
        text = raw_bytes.decode(*enc_tuple, errors='replace')
        korean_count = len(re.findall(r'[가-힣]', text))
        lines = text.count('\n') + 1
        replacement_count = text.count('\ufffd')
        
        results.append({
            'encoding': enc_tuple,
            'korean': korean_count,
            'lines': lines,
            'replacement': replacement_count,
            'text': text
        })
        
        print(f"{str(enc_tuple):20s} | Korean: {korean_count:5d} | Lines: {lines:5d} | Repl: {replacement_count:5d}")
    except Exception as e:
        print(f"{str(enc_tuple):20s} | FAILED: {e}")

# 최적 선택 (한글 글자 수 최대)
best = max(results, key=lambda x: x['korean'])

print(f"\nBest encoding: {best['encoding']}")
print(f"  Korean chars: {best['korean']:,}")
print(f"  Lines: {best['lines']:,}")
print(f"  Replacement: {best['replacement']:,}")

# D_ROADMAP.md 저장
output_path = Path("D_ROADMAP.md")
output_path.write_text(best['text'], encoding='utf-8')

# 헤더 미리보기
preview = best['text'].split('\n')[:20]
print(f"\nPreview (first 20 lines):")
for i, line in enumerate(preview, 1):
    print(f"  {i:2d}| {line[:100]}")

print(f"\n[OK] D_ROADMAP.md saved with {best['encoding']} encoding")
