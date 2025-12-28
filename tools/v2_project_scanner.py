#!/usr/bin/env python3
"""
V2 Kickoff - Project Structure Scanner
프로젝트 전체 트리 스캔 + 중복 패턴 리포트 생성
"""
import os
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import re


class ProjectScanner:
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.report = {
            "scan_time": datetime.now().isoformat(),
            "root_path": str(self.root),
            "duplicate_folders": [],
            "duplicate_modules": [],
            "script_launchers": [],
            "duplicate_docs": [],
            "statistics": {}
        }
        
    def scan(self):
        """전체 프로젝트 스캔 실행"""
        print("[V2 Scanner] Starting project scan...")
        
        # 1. 폴더 중복 패턴 탐지
        print("[V2 Scanner] Detecting duplicate folder patterns...")
        self._detect_duplicate_folders()
        
        # 2. Python 모듈 중복 탐지
        print("[V2 Scanner] Detecting duplicate Python modules...")
        self._detect_duplicate_modules()
        
        # 3. 스크립트 런처 중복 탐지
        print("[V2 Scanner] Detecting script launchers...")
        self._detect_script_launchers()
        
        # 4. 문서 중복/유사 탐지
        print("[V2 Scanner] Detecting duplicate/similar docs...")
        self._detect_duplicate_docs()
        
        # 5. 통계 수집
        print("[V2 Scanner] Collecting statistics...")
        self._collect_statistics()
        
        print("[V2 Scanner] Scan completed!")
        return self.report
    
    def _detect_duplicate_folders(self):
        """폴더명 중복 패턴 탐지"""
        folder_names = defaultdict(list)
        
        for root, dirs, files in os.walk(self.root):
            # 가상환경, .git, __pycache__ 등 제외
            dirs[:] = [d for d in dirs if not d.startswith('.') 
                      and d not in ['abt_bot_env', 'abt_bot_env_old', '__pycache__', 'node_modules']]
            
            rel_root = Path(root).relative_to(self.root)
            for dir_name in dirs:
                folder_names[dir_name].append(str(rel_root / dir_name))
        
        # 2개 이상 존재하는 폴더명 리포트
        for folder_name, paths in folder_names.items():
            if len(paths) >= 2:
                self.report["duplicate_folders"].append({
                    "folder_name": folder_name,
                    "count": len(paths),
                    "paths": paths,
                    "suspicion": self._classify_folder_suspicion(folder_name, paths)
                })
        
        # 정렬 (의심도 높은 순)
        self.report["duplicate_folders"].sort(
            key=lambda x: (x["suspicion"]["level"], x["count"]), 
            reverse=True
        )
    
    def _classify_folder_suspicion(self, folder_name: str, paths: list) -> dict:
        """폴더 중복의 의심 수준 분류"""
        # 높은 의심: config/configs, database/db, common 등
        high_suspicion = ['config', 'database', 'db', 'common', 'utils', 'helpers']
        # 중간 의심: monitoring, logging, storage 등
        medium_suspicion = ['monitoring', 'logging', 'storage', 'metrics', 'alerts']
        
        if folder_name.lower() in high_suspicion:
            return {"level": "HIGH", "reason": "Core infrastructure duplication"}
        elif folder_name.lower() in medium_suspicion:
            return {"level": "MEDIUM", "reason": "Service duplication"}
        elif any(p.startswith('tests') for p in paths):
            return {"level": "LOW", "reason": "Test structure duplication (acceptable)"}
        else:
            return {"level": "MEDIUM", "reason": "Generic duplication"}
    
    def _detect_duplicate_modules(self):
        """Python 파일명/클래스명 중복 탐지"""
        file_names = defaultdict(list)
        class_names = defaultdict(list)
        
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith('.') 
                      and d not in ['abt_bot_env', 'abt_bot_env_old', '__pycache__']]
            
            rel_root = Path(root).relative_to(self.root)
            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    file_path = str(rel_root / file)
                    file_names[file].append(file_path)
                    
                    # 클래스명 추출 (간단한 정규식)
                    full_path = Path(root) / file
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            classes = re.findall(r'class\s+(\w+)', content)
                            for cls in classes:
                                class_names[cls].append({
                                    "file": file_path,
                                    "class": cls
                                })
                    except:
                        pass
        
        # 2개 이상 존재하는 파일명
        for file_name, paths in file_names.items():
            if len(paths) >= 2:
                self.report["duplicate_modules"].append({
                    "type": "file",
                    "name": file_name,
                    "count": len(paths),
                    "paths": paths
                })
        
        # 2개 이상 존재하는 클래스명
        for class_name, occurrences in class_names.items():
            if len(occurrences) >= 2:
                self.report["duplicate_modules"].append({
                    "type": "class",
                    "name": class_name,
                    "count": len(occurrences),
                    "occurrences": occurrences
                })
    
    def _detect_script_launchers(self):
        """스크립트 런처 패턴 탐지 (run_*.py)"""
        scripts_dir = self.root / 'scripts'
        if not scripts_dir.exists():
            return
        
        run_scripts = []
        for file in scripts_dir.glob('run_*.py'):
            rel_path = file.relative_to(self.root)
            
            # 파일 크기 및 주요 기능 추출
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = len(content.split('\n'))
                    
                    # 주요 키워드 탐지
                    keywords = {
                        "paper": "paper" in content.lower(),
                        "live": "live" in content.lower(),
                        "smoke": "smoke" in content.lower(),
                        "test": "test" in content.lower(),
                        "runner": "runner" in content.lower(),
                        "arbitrage": "arbitrage" in content.lower()
                    }
                    
                    run_scripts.append({
                        "path": str(rel_path),
                        "lines": lines,
                        "keywords": keywords,
                        "pattern": self._classify_script_pattern(file.name, keywords)
                    })
            except:
                pass
        
        self.report["script_launchers"] = run_scripts
        
        # 패턴별 그룹화
        patterns = defaultdict(list)
        for script in run_scripts:
            patterns[script["pattern"]].append(script["path"])
        
        self.report["script_launcher_patterns"] = dict(patterns)
    
    def _classify_script_pattern(self, filename: str, keywords: dict) -> str:
        """스크립트 패턴 분류"""
        if keywords["smoke"] and keywords["paper"]:
            return "paper_smoke"
        elif keywords["smoke"] and keywords["live"]:
            return "live_smoke"
        elif keywords["paper"]:
            return "paper_runner"
        elif keywords["live"]:
            return "live_runner"
        elif keywords["test"]:
            return "test_runner"
        else:
            return "generic_runner"
    
    def _detect_duplicate_docs(self):
        """문서 중복/유사 탐지"""
        docs_dir = self.root / 'docs'
        if not docs_dir.exists():
            return
        
        # 인덱스/가이드 문서 탐지
        index_docs = []
        guide_docs = []
        report_docs = []
        
        for file in docs_dir.rglob('*.md'):
            rel_path = file.relative_to(self.root)
            filename = file.name.lower()
            
            if 'index' in filename or 'roadmap' in filename:
                index_docs.append(str(rel_path))
            elif 'guide' in filename or 'design' in filename:
                guide_docs.append(str(rel_path))
            elif 'report' in filename or 'summary' in filename:
                report_docs.append(str(rel_path))
        
        self.report["duplicate_docs"] = {
            "index_docs": index_docs,
            "guide_docs": guide_docs,
            "report_docs": report_docs,
            "suspicion": {
                "index_count": len(index_docs),
                "guide_count": len(guide_docs),
                "report_count": len(report_docs),
                "concern": "Multiple index/roadmap docs detected" if len(index_docs) > 2 else "OK"
            }
        }
    
    def _collect_statistics(self):
        """프로젝트 통계 수집"""
        stats = {
            "total_folders": 0,
            "total_python_files": 0,
            "total_test_files": 0,
            "total_docs": 0,
            "total_scripts": 0,
            "arbitrage_modules": 0,
            "config_files": 0
        }
        
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith('.') 
                      and d not in ['abt_bot_env', 'abt_bot_env_old', '__pycache__']]
            
            stats["total_folders"] += len(dirs)
            
            for file in files:
                if file.endswith('.py'):
                    stats["total_python_files"] += 1
                    
                    if 'test_' in file:
                        stats["total_test_files"] += 1
                    
                    if 'arbitrage' in root:
                        stats["arbitrage_modules"] += 1
                    
                    if 'scripts' in root:
                        stats["total_scripts"] += 1
                
                elif file.endswith('.md'):
                    stats["total_docs"] += 1
                
                elif file.endswith(('.yaml', '.yml', '.json')):
                    if 'config' in root:
                        stats["config_files"] += 1
        
        self.report["statistics"] = stats
    
    def save_report(self, output_dir: str):
        """리포트를 파일로 저장"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # JSON 리포트
        json_path = output_path / 'scan_report.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        
        # Markdown 리포트 (읽기 쉬운 형식)
        md_path = output_path / 'scan_report.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            self._write_markdown_report(f)
        
        print(f"[V2 Scanner] Report saved to {output_path}")
        return str(json_path), str(md_path)
    
    def _write_markdown_report(self, f):
        """Markdown 형식 리포트 작성"""
        f.write("# V2 Kickoff - Project Structure Scan Report\n\n")
        f.write(f"**Scan Time:** {self.report['scan_time']}\n\n")
        f.write(f"**Root Path:** {self.report['root_path']}\n\n")
        
        # 통계
        f.write("## 📊 Project Statistics\n\n")
        for key, value in self.report["statistics"].items():
            f.write(f"- **{key.replace('_', ' ').title()}:** {value}\n")
        f.write("\n")
        
        # 중복 폴더
        f.write("## 📁 Duplicate Folder Patterns\n\n")
        if self.report["duplicate_folders"]:
            for item in self.report["duplicate_folders"][:20]:  # Top 20
                f.write(f"### {item['folder_name']} (Count: {item['count']}, Level: {item['suspicion']['level']})\n")
                f.write(f"**Reason:** {item['suspicion']['reason']}\n\n")
                for path in item['paths'][:10]:  # 최대 10개
                    f.write(f"- `{path}`\n")
                f.write("\n")
        else:
            f.write("No duplicate folders detected.\n\n")
        
        # 중복 모듈
        f.write("## 🐍 Duplicate Python Modules\n\n")
        if self.report["duplicate_modules"]:
            file_dups = [m for m in self.report["duplicate_modules"] if m["type"] == "file"]
            class_dups = [m for m in self.report["duplicate_modules"] if m["type"] == "class"]
            
            f.write(f"**Total File Duplicates:** {len(file_dups)}\n")
            f.write(f"**Total Class Duplicates:** {len(class_dups)}\n\n")
            
            if file_dups:
                f.write("### Top File Duplicates\n\n")
                for item in file_dups[:10]:
                    f.write(f"**{item['name']}** (Count: {item['count']})\n")
                    for path in item['paths'][:5]:
                        f.write(f"- `{path}`\n")
                    f.write("\n")
            
            if class_dups:
                f.write("### Top Class Duplicates\n\n")
                for item in class_dups[:10]:
                    f.write(f"**{item['name']}** (Count: {item['count']})\n")
                    for occ in item['occurrences'][:5]:
                        f.write(f"- `{occ['file']}` → class {occ['class']}\n")
                    f.write("\n")
        else:
            f.write("No duplicate modules detected.\n\n")
        
        # 스크립트 런처
        f.write("## 🚀 Script Launchers (run_*.py)\n\n")
        if self.report["script_launchers"]:
            f.write(f"**Total Scripts:** {len(self.report['script_launchers'])}\n\n")
            
            if "script_launcher_patterns" in self.report:
                f.write("### By Pattern\n\n")
                for pattern, scripts in self.report["script_launcher_patterns"].items():
                    f.write(f"**{pattern}** ({len(scripts)} scripts)\n")
                    for script in scripts[:5]:
                        f.write(f"- `{script}`\n")
                    f.write("\n")
        else:
            f.write("No script launchers detected.\n\n")
        
        # 문서 중복
        f.write("## 📝 Document Structure\n\n")
        if self.report["duplicate_docs"]:
            f.write(f"**Index/Roadmap Docs:** {self.report['duplicate_docs']['suspicion']['index_count']}\n")
            f.write(f"**Guide/Design Docs:** {self.report['duplicate_docs']['suspicion']['guide_count']}\n")
            f.write(f"**Report/Summary Docs:** {self.report['duplicate_docs']['suspicion']['report_count']}\n\n")
            
            f.write(f"**Concern:** {self.report['duplicate_docs']['suspicion']['concern']}\n\n")
            
            if self.report['duplicate_docs']['index_docs']:
                f.write("### Index/Roadmap Documents\n\n")
                for doc in self.report['duplicate_docs']['index_docs'][:10]:
                    f.write(f"- `{doc}`\n")
                f.write("\n")


def main():
    """메인 실행 함수"""
    root_path = Path(__file__).parent.parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = root_path / 'logs' / 'evidence' / f'v2_kickoff_scan_{timestamp}'
    
    scanner = ProjectScanner(str(root_path))
    report = scanner.scan()
    json_path, md_path = scanner.save_report(str(output_dir))
    
    print("\n" + "="*80)
    print("V2 KICKOFF SCAN COMPLETED")
    print("="*80)
    print(f"\nReports saved:")
    print(f"  - JSON: {json_path}")
    print(f"  - Markdown: {md_path}")
    print("\nTop Findings:")
    print(f"  - Duplicate Folders: {len(report['duplicate_folders'])}")
    print(f"  - Duplicate Modules: {len(report['duplicate_modules'])}")
    print(f"  - Script Launchers: {len(report['script_launchers'])}")
    print(f"  - Total Python Files: {report['statistics']['total_python_files']}")
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
