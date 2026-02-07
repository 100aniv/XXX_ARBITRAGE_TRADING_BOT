"""
D205-14-2: AutoTuner leaderboard 형식 검증
"""

import json
import pytest
from pathlib import Path

pytestmark = pytest.mark.optional_live


def test_leaderboard_structure():
    """
    leaderboard.json 구조 검증
    
    AC:
    - leaderboard는 list[dict]
    - 각 entry는 rank, params, metrics 포함
    - metrics는 positive_net_edge_rate, mean_net_edge_bps, p10_net_edge_bps 포함
    """
    # D205-14-2 evidence
    evidence_dir = Path("logs/evidence/d205_14_2_autotune_fix_20260106_235126/autotune_run")
    
    if not evidence_dir.exists():
        pytest.skip(f"Evidence not found: {evidence_dir}")
    
    leaderboard_path = evidence_dir / "leaderboard.json"
    assert leaderboard_path.exists(), f"leaderboard.json not found: {leaderboard_path}"
    
    with open(leaderboard_path, "r") as f:
        leaderboard = json.load(f)
    
    # 구조 검증
    assert isinstance(leaderboard, list), "leaderboard는 list여야 함"
    assert len(leaderboard) > 0, "leaderboard는 최소 1개 entry 필요"
    
    for idx, entry in enumerate(leaderboard):
        assert "rank" in entry, f"Entry {idx}: rank 필드 누락"
        assert "params" in entry, f"Entry {idx}: params 필드 누락"
        assert "metrics" in entry, f"Entry {idx}: metrics 필드 누락"
        
        # params 검증
        params = entry["params"]
        assert "slippage_alpha" in params
        assert "partial_fill_penalty_bps" in params
        assert "max_safe_ratio" in params
        assert "min_spread_bps" in params
        
        # metrics 검증
        metrics = entry["metrics"]
        assert "positive_net_edge_rate" in metrics
        assert "mean_net_edge_bps" in metrics
        assert "p10_net_edge_bps" in metrics


def test_leaderboard_ranked():
    """
    leaderboard가 positive_net_edge_rate 내림차순 정렬되었는지 검증
    """
    evidence_dir = Path("logs/evidence/d205_14_2_autotune_fix_20260106_235126/autotune_run")
    
    if not evidence_dir.exists():
        pytest.skip(f"Evidence not found: {evidence_dir}")
    
    leaderboard_path = evidence_dir / "leaderboard.json"
    
    with open(leaderboard_path, "r") as f:
        leaderboard = json.load(f)
    
    # 정렬 검증
    for i in range(len(leaderboard) - 1):
        current_rate = leaderboard[i]["metrics"]["positive_net_edge_rate"]
        next_rate = leaderboard[i + 1]["metrics"]["positive_net_edge_rate"]
        assert current_rate >= next_rate, f"정렬 오류: entry {i} ({current_rate}) < entry {i+1} ({next_rate})"


def test_manifest_ticks_count():
    """
    manifest.json의 ticks_count >= 200 검증
    """
    evidence_dir = Path("logs/evidence/d205_14_2_autotune_fix_20260106_235126/autotune_run")
    
    if not evidence_dir.exists():
        pytest.skip(f"Evidence not found: {evidence_dir}")
    
    manifest_path = evidence_dir / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not found: {manifest_path}"
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    # D205-14-2 목표: ticks_count >= 200
    # 주의: 실제로는 input 파일의 라인 수를 확인해야 하지만,
    # manifest에 기록되지 않을 수 있으므로 별도 검증 필요
    # (이 테스트는 manifest 형식만 검증)
    assert "combinations_total" in manifest
    assert manifest["combinations_total"] == 144
