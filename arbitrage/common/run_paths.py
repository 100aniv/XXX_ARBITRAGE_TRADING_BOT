# -*- coding: utf-8 -*-
"""
D92-5: Run Artifact Path Resolution Utility

아티팩트 경로 SSOT 관리.

목표:
- D92-5부터 모든 실행은 logs/{stage_id}/{run_id}/ 구조 사용
- 기존 D77/D82 코드는 하위 호환성 유지
- 호환을 위해 logs/d77-0 등에 복사 가능 (SSOT는 stage_id 경로)

Author: arbitrage-lite project
Date: 2025-12-13 (D92-5)
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


def resolve_run_paths(
    stage_id: str,
    run_id: Optional[str] = None,
    universe_mode: str = "top_10",
    create_dirs: bool = True,
) -> Dict[str, Path]:
    """
    Run 아티팩트 경로 해석.
    
    D92-5 SSOT 구조:
        logs/{stage_id}/{run_id}/
            - {run_id}_kpi_summary.json
            - {run_id}_trades.jsonl
            - {run_id}_config_snapshot.yaml
            - {run_id}_runtime_meta.json
    
    Args:
        stage_id: D 단계 ID (예: "d92-5", "d77-0", "d82-0")
        run_id: Run ID (None이면 자동 생성)
        universe_mode: Universe 모드 (예: "top_10", "top_20")
        create_dirs: 디렉토리 자동 생성 여부
    
    Returns:
        경로 딕셔너리:
        {
            "run_id": str,
            "stage_dir": Path,  # logs/{stage_id}
            "run_dir": Path,    # logs/{stage_id}/{run_id}
            "kpi_summary": Path,
            "trades_log": Path,
            "config_snapshot": Path,
            "runtime_meta": Path,
        }
    
    Example:
        >>> paths = resolve_run_paths("d92-5", universe_mode="top_10")
        >>> print(paths["kpi_summary"])
        logs/d92-5/d92-5-top10-20251213_001234/d92-5-top10-20251213_001234_kpi_summary.json
    """
    # Run ID 자동 생성
    if run_id is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        universe_label = universe_mode.lower().replace("_", "")
        run_id = f"{stage_id}-{universe_label}-{timestamp}"
    
    # 경로 구조
    stage_dir = Path("logs") / stage_id
    run_dir = stage_dir / run_id
    
    paths = {
        "run_id": run_id,
        "stage_dir": stage_dir,
        "run_dir": run_dir,
        "kpi_summary": run_dir / f"{run_id}_kpi_summary.json",
        "trades_log": run_dir / f"{run_id}_trades.jsonl",
        "config_snapshot": run_dir / f"{run_id}_config_snapshot.yaml",
        "runtime_meta": run_dir / f"{run_id}_runtime_meta.json",
    }
    
    # 디렉토리 생성
    if create_dirs:
        run_dir.mkdir(parents=True, exist_ok=True)
    
    return paths


def get_legacy_log_dir(stage_id: str) -> Path:
    """
    레거시 로그 디렉토리 반환.
    
    D77/D82 하위 호환성을 위해 기존 경로 반환.
    
    Args:
        stage_id: D 단계 ID
    
    Returns:
        레거시 로그 디렉토리 (예: logs/d77-0)
    """
    # D77-0, D82-0 등은 기존 경로 유지
    if stage_id.startswith("d77"):
        return Path("logs/d77-0")
    elif stage_id.startswith("d82"):
        return Path("logs/d82-0")
    else:
        # D92+ 는 레거시 없음, stage_id 그대로 사용
        return Path("logs") / stage_id


def copy_to_legacy_compat(
    src_path: Path,
    legacy_dir: Path,
    create_legacy_dir: bool = True,
) -> Optional[Path]:
    """
    SSOT 파일을 레거시 경로에 복사 (호환성용).
    
    Args:
        src_path: 원본 파일 경로 (SSOT)
        legacy_dir: 레거시 디렉토리
        create_legacy_dir: 레거시 디렉토리 자동 생성 여부
    
    Returns:
        복사된 파일 경로 (실패 시 None)
    """
    if not src_path.exists():
        return None
    
    if create_legacy_dir:
        legacy_dir.mkdir(parents=True, exist_ok=True)
    
    dst_path = legacy_dir / src_path.name
    
    try:
        import shutil
        shutil.copy2(src_path, dst_path)
        return dst_path
    except Exception:
        return None
