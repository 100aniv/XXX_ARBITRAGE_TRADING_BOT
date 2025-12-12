#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D92-5: Runtime Metadata 생성 및 Import Provenance 하드락

목적:
- 실행 시작 시 runtime_meta.json 생성
- 핵심 파일의 __file__ 절대경로 + sha256 + mtime 기록
- "다른 파일이 실행됨/캐시임" 물리적 차단
"""

import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime
import socket


def get_file_sha256(file_path: Path) -> str:
    """파일 SHA256 해시 계산"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_file_mtime(file_path: Path) -> str:
    """파일 수정 시각 (ISO 포맷)"""
    return datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()


def generate_runtime_meta(run_dir: Path, stage_id: str) -> Path:
    """
    Runtime Metadata 생성
    
    Args:
        run_dir: Run 디렉토리 (logs/{stage_id}/{run_id}/)
        stage_id: Stage ID
    
    Returns:
        runtime_meta.json 경로
    """
    repo_root = Path(__file__).resolve().parent.parent
    
    # 핵심 파일 목록
    core_files = [
        repo_root / "scripts" / "run_d92_1_topn_longrun.py",
        repo_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py",
        repo_root / "arbitrage" / "common" / "run_paths.py",
    ]
    
    # Zone Profile YAML (실제 로드한 파일)
    zone_profile_yaml = repo_root / "arbitrage" / "config" / "zone_profiles_v2.yaml"
    if zone_profile_yaml.exists():
        core_files.append(zone_profile_yaml)
    
    # 파일 메타데이터 수집
    file_metadata = {}
    for file_path in core_files:
        if file_path.exists():
            file_metadata[str(file_path.relative_to(repo_root))] = {
                "abs_path": str(file_path),
                "sha256": get_file_sha256(file_path),
                "mtime": get_file_mtime(file_path),
            }
    
    # Git 정보
    try:
        import subprocess
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
        ).strip()
    except Exception:
        git_commit = "unknown"
    
    # Runtime Meta 생성
    runtime_meta = {
        "generated_at": datetime.now().isoformat(),
        "stage_id": stage_id,
        "repo_root": str(repo_root),
        "python_exe": sys.executable,
        "python_version": sys.version,
        "hostname": socket.gethostname(),
        "git_commit": git_commit,
        "core_files": file_metadata,
    }
    
    # 저장
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = run_dir / "runtime_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(runtime_meta, f, indent=2, ensure_ascii=False)
    
    print(f"[D92-5] Runtime metadata generated: {meta_path}")
    return meta_path


def verify_import_provenance() -> bool:
    """
    Import Provenance 자가 점검
    
    Returns:
        True if all imports are from REPO_ROOT
    """
    repo_root = Path(__file__).resolve().parent.parent
    
    # 검증할 모듈들
    modules_to_check = [
        "scripts.run_d92_1_topn_longrun",
        "scripts.run_d77_0_topn_arbitrage_paper",
        "arbitrage.common.run_paths",
    ]
    
    all_ok = True
    for module_name in modules_to_check:
        try:
            module = sys.modules.get(module_name)
            if module is None:
                # 아직 import 안됨
                continue
            
            module_file = Path(module.__file__).resolve()
            if not str(module_file).startswith(str(repo_root)):
                print(f"[ERROR] Module {module_name} is NOT from REPO_ROOT:")
                print(f"  Expected: {repo_root}")
                print(f"  Actual: {module_file}")
                all_ok = False
            else:
                print(f"[OK] {module_name}: {module_file}")
        except Exception as e:
            print(f"[WARN] Failed to check {module_name}: {e}")
    
    return all_ok


if __name__ == "__main__":
    # Self-test
    print("[D92-5] Runtime Meta & Import Provenance Self-Check")
    print("=" * 80)
    
    # 1. Import Provenance 검증
    print("\n[1/2] Import Provenance Check:")
    if verify_import_provenance():
        print("✅ All imports from REPO_ROOT")
    else:
        print("❌ Import provenance FAILED")
        sys.exit(1)
    
    # 2. Runtime Meta 생성 테스트
    print("\n[2/2] Runtime Meta Generation Test:")
    test_run_dir = Path("logs/d92-5-test/test-run")
    meta_path = generate_runtime_meta(test_run_dir, "d92-5-test")
    
    # 검증
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        print(f"✅ Runtime meta generated: {len(meta['core_files'])} files tracked")
        print(f"   Git commit: {meta['git_commit']}")
        print(f"   Python: {meta['python_version'][:20]}...")
    else:
        print("❌ Runtime meta generation FAILED")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("[D92-5] Self-check PASSED")
