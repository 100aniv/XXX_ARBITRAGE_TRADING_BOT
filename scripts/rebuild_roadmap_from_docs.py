#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 POST-MOVE-HARDEN v2: D_ROADMAP.md 재생성 (docs/ 기반)

Git 히스토리가 모두 모지바케 상태이므로, docs/ 디렉토리의 
D단계 문서들을 스캔해서 ROADMAP을 재생성합니다.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
import sys


def scan_docs_directory(docs_path: Path) -> Dict[str, List[Path]]:
    """docs/ 디렉토리에서 D* 관련 문서들 스캔"""
    d_docs = {}
    
    # D77, D80, D90, D91, D92 등 디렉토리별로 스캔
    for d_dir in docs_path.iterdir():
        if d_dir.is_dir() and d_dir.name.startswith('D'):
            d_num = d_dir.name
            files = []
            for md_file in d_dir.rglob('*.md'):
                if md_file.is_file():
                    files.append(md_file)
            if files:
                d_docs[d_num] = sorted(files)
    
    return d_docs


def extract_phase_info(file_path: Path) -> Dict[str, str]:
    """문서에서 단계 정보 추출"""
    info = {
        'phase': '',
        'title': '',
        'status': 'UNKNOWN',
        'summary': ''
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 제목 추출 (첫 번째 # 헤더)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            info['title'] = title_match.group(1).strip()
        
        # Phase/D번호 추출
        phase_match = re.search(r'(D\d+-\d+)', content)
        if phase_match:
            info['phase'] = phase_match.group(1)
        
        # 상태 추출 (ACCEPTED, PASS, COMPLETE 등)
        if 'ACCEPTED' in content:
            info['status'] = 'ACCEPTED'
        elif 'PASS' in content or 'SUCCESS' in content:
            info['status'] = 'PASS'
        elif 'FAIL' in content or 'PARTIAL' in content:
            info['status'] = 'PARTIAL'
        elif 'COMPLETE' in content:
            info['status'] = 'COMPLETE'
        
        # 요약 추출 (처음 500자 정도)
        lines = content.split('\n')[:20]
        summary_lines = [l for l in lines if l.strip() and not l.startswith('#')]
        info['summary'] = ' '.join(summary_lines[:3])[:200]
        
    except Exception as e:
        print(f"[WARN] 파일 읽기 실패: {file_path.name} - {e}")
    
    return info


def build_roadmap_content(d_docs: Dict[str, List[Path]], git_root: Path) -> str:
    """ROADMAP 콘텐츠 생성"""
    
    content = []
    content.append("# arbitrage-lite 로드맵")
    content.append("")
    content.append("**[REBUILT]** 이 로드맵은 Git 히스토리의 인코딩 문제로 인해 docs/ 디렉토리 기반으로 재생성되었습니다.")
    content.append("")
    content.append("**NOTE:** 이 로드맵은 **arbitrage-lite**(현물 차익 프로젝트)의 공식 로드맵입니다.")
    content.append("본 프로젝트는 **D 단계(D1~Dx)** 기반 개발 프로세스를 따르며, **PHASEXX 단계**는 future_alarm_bot(선물/현물 통합 프로젝트)에 해당하는 로드맵으로 별도 관리됩니다.")
    content.append("")
    content.append("---")
    content.append("")
    content.append("## 0. 공통 원칙 (D 단계 진행 규칙)")
    content.append("")
    content.append("각 D 단계는 다음 원칙을 따릅니다:")
    content.append("")
    content.append("1. **완료 기준**")
    content.append("   - 구현/설계가 완료되고 단위 테스트가 PASS")
    content.append("")
    content.append("2. **완료 증거**")
    content.append("   - 설계 문서 + 코드/로그/테스트 결과")
    content.append("   - 프로젝트의 KPI/지표가 명확히 개선되었거나, PnL 증가 증거")
    content.append("")
    content.append("3. **보고서**")
    content.append("   - DXX_FINAL_REPORT.md")
    content.append("   - 단계별 상세 보고서(DXX_*.md)")
    content.append("   - 테스트 결과, 성능 지표, 설계 변경 근거")
    content.append("")
    content.append("4. **Critical 이슈 0**")
    content.append("   - 각 D 단계는 완료 시 Critical 버그가 0개여야 함")
    content.append("   - 발견 즉시 수정, Non-critical TODO는 다음 단계로 이관 가능")
    content.append("")
    content.append("---")
    content.append("")
    
    # D 단계별로 정리
    for d_num in sorted(d_docs.keys()):
        files = d_docs[d_num]
        content.append(f"## {d_num}")
        content.append("")
        
        for file_path in files:
            info = extract_phase_info(file_path)
            rel_path = file_path.relative_to(git_root)
            
            phase_label = info['phase'] if info['phase'] else d_num
            title = info['title'] if info['title'] else file_path.stem
            status = info['status']
            
            content.append(f"### {phase_label}: {title}")
            content.append("")
            content.append(f"**상태:** {status}")
            content.append(f"**문서:** `{rel_path}`")
            content.append("")
            
            if info['summary']:
                content.append(f"> {info['summary']}")
                content.append("")
        
        content.append("---")
        content.append("")
    
    content.append("## SSOT 규칙")
    content.append("")
    content.append("**ROADMAP SSOT는 루트 /D_ROADMAP.md 단 하나. docs 아래 금지.**")
    content.append("")
    content.append("이 문서가 프로젝트의 단일 진실 소스(Single Source of Truth)입니다.")
    content.append("모든 D 단계의 상태, 진행 상황, 완료 증거는 이 문서에 기록됩니다.")
    content.append("")
    
    return '\n'.join(content)


def main():
    """메인 실행"""
    print("=" * 80)
    print("D92 POST-MOVE-HARDEN v2: D_ROADMAP.md 재생성 (docs/ 기반)")
    print("=" * 80)
    
    try:
        git_root = Path.cwd()
        docs_path = git_root / 'docs'
        
        if not docs_path.exists():
            print(f"[ERROR] docs/ 디렉토리를 찾을 수 없습니다: {docs_path}")
            return 1
        
        print(f"Git 루트: {git_root}")
        print(f"Docs 경로: {docs_path}")
        
        # docs/ 스캔
        print("\ndocs/ 디렉토리 스캔 중...")
        d_docs = scan_docs_directory(docs_path)
        
        if not d_docs:
            print("[ERROR] docs/에서 D* 문서를 찾을 수 없습니다.")
            return 1
        
        total_files = sum(len(files) for files in d_docs.values())
        print(f"[OK] {len(d_docs)}개 D 단계, 총 {total_files}개 문서 발견")
        
        for d_num, files in sorted(d_docs.items()):
            print(f"   - {d_num}: {len(files)}개 문서")
        
        # ROADMAP 생성
        print("\nROADMAP 생성 중...")
        content = build_roadmap_content(d_docs, git_root)
        
        # 파일 저장
        roadmap_path = git_root / 'D_ROADMAP.md'
        with open(roadmap_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[OK] ROADMAP 생성 완료: {roadmap_path}")
        print(f"   파일 크기: {len(content):,} bytes")
        
        # 헤더 출력
        lines = content.split('\n')[:10]
        print("\n생성된 ROADMAP 헤더:")
        for line in lines:
            print(f"   {line}")
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
