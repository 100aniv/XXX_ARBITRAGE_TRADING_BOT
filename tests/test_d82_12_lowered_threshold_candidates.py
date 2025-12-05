#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-12 Lowered Threshold Candidates Generation Tests
"""

import json
import pytest
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.generate_d82_12_lowered_tp_entry_candidates import (
    calculate_edge,
    generate_candidates,
    DEFAULT_ENTRY_CANDIDATES,
    DEFAULT_TP_CANDIDATES,
    ROUNDTRIP_COST_BPS,
)


# =============================================================================
# Edge Calculation Tests
# =============================================================================

def test_calculate_edge_basic():
    """Basic edge calculation test"""
    result = calculate_edge(5.0, 7.0)
    
    # Gross spread = (5 + 7) / 2 = 6.0
    assert result["gross_spread_bps"] == 6.0
    
    # Roundtrip cost = 13.28
    assert result["roundtrip_cost_bps"] == ROUNDTRIP_COST_BPS
    
    # Edge = 6.0 - 13.28 = -7.28
    expected_edge = 6.0 - ROUNDTRIP_COST_BPS
    assert abs(result["edge_bps"] - expected_edge) < 0.01


def test_calculate_edge_d77_4_zone():
    """Edge calculation for D77-4 baseline zone"""
    # D77-4 typical: Entry 7, TP 10
    result = calculate_edge(7.0, 10.0)
    
    # Gross spread = (7 + 10) / 2 = 8.5
    assert result["gross_spread_bps"] == 8.5
    
    # Edge = 8.5 - 13.28 = -4.78 (negative, but D77-4 succeeded)
    assert result["edge_bps"] < 0  # Theoretical edge is negative
    assert result["edge_bps"] == 8.5 - ROUNDTRIP_COST_BPS


# =============================================================================
# Candidate Generation Tests
# =============================================================================

def test_generate_candidates_count():
    """Test that correct number of candidates are generated"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    # Valid combinations (TP > Entry):
    # Entry 5: TP 7, 10, 12 (3)
    # Entry 7: TP 10, 12 (2)
    # Entry 10: TP 12 (1)
    # Total: 6
    assert len(candidates) == 6


def test_generate_candidates_validity():
    """Test that all candidates satisfy TP > Entry"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    for cand in candidates:
        assert cand["tp_bps"] > cand["entry_bps"], (
            f"Invalid candidate: Entry={cand['entry_bps']}, TP={cand['tp_bps']}"
        )


def test_generate_candidates_ranges():
    """Test that candidates are within expected ranges"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    for cand in candidates:
        # Entry in [5, 7, 10]
        assert cand["entry_bps"] in DEFAULT_ENTRY_CANDIDATES
        
        # TP in [7, 10, 12]
        assert cand["tp_bps"] in DEFAULT_TP_CANDIDATES


def test_generate_candidates_schema():
    """Test that candidates have all required fields"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    required_fields = [
        "entry_bps",
        "tp_bps",
        "gross_spread_bps",
        "roundtrip_cost_bps",
        "edge_bps",
        "is_viable",
        "is_d77_4_baseline",
        "rationale",
        "edge_optimistic",
        "edge_realistic",
        "edge_conservative",
        "is_structurally_safe",
        "is_recommended",
    ]
    
    for cand in candidates:
        for field in required_fields:
            assert field in cand, f"Missing field: {field}"


def test_generate_candidates_sorting():
    """Test that candidates are sorted by edge (descending)"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    edges = [c["edge_bps"] for c in candidates]
    
    # Check descending order
    for i in range(len(edges) - 1):
        assert edges[i] >= edges[i + 1], (
            f"Not sorted: edges[{i}]={edges[i]:.2f}, edges[{i+1}]={edges[i+1]:.2f}"
        )


def test_generate_candidates_d82_10_compatibility():
    """Test that schema is compatible with D82-10"""
    candidates = generate_candidates(
        DEFAULT_ENTRY_CANDIDATES,
        DEFAULT_TP_CANDIDATES,
    )
    
    # D82-10 후보와 동일한 필드 구조
    d82_10_fields = [
        "entry_bps",
        "tp_bps",
        "edge_optimistic",
        "edge_realistic",
        "edge_conservative",
        "is_structurally_safe",
        "is_recommended",
        "rationale",
    ]
    
    for cand in candidates:
        for field in d82_10_fields:
            assert field in cand, f"D82-10 compatibility: missing {field}"


# =============================================================================
# Script Execution Tests
# =============================================================================

def test_script_execution():
    """Test that script runs without error"""
    output_path = Path("logs/d82-12/test_lowered_tp_entry_candidates.json")
    
    # Remove existing file
    if output_path.exists():
        output_path.unlink()
    
    # Run script
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_d82_12_lowered_tp_entry_candidates.py",
            "--output-path", str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    
    # Check output file exists
    assert output_path.exists(), f"Output file not created: {output_path}"
    
    # Cleanup
    output_path.unlink()


def test_json_output_structure():
    """Test that output JSON has correct structure"""
    output_path = Path("logs/d82-12/test_lowered_tp_entry_candidates.json")
    
    # Remove existing file
    if output_path.exists():
        output_path.unlink()
    
    # Run script
    subprocess.run(
        [
            sys.executable,
            "scripts/generate_d82_12_lowered_tp_entry_candidates.py",
            "--output-path", str(output_path),
        ],
        capture_output=True,
        cwd=Path(__file__).parent.parent,
        check=True,
    )
    
    # Load JSON
    with open(output_path) as f:
        data = json.load(f)
    
    # Check structure
    assert "metadata" in data
    assert "candidates" in data
    
    # Check metadata
    assert "source" in data["metadata"]
    assert "created_at" in data["metadata"]
    assert "cost_profile" in data["metadata"]
    assert "grid" in data["metadata"]
    
    # Check candidates count
    assert len(data["candidates"]) == 6
    
    # Cleanup
    output_path.unlink()


def test_json_candidates_validity():
    """Test that JSON candidates are valid"""
    output_path = Path("logs/d82-12/test_lowered_tp_entry_candidates.json")
    
    # Remove existing file
    if output_path.exists():
        output_path.unlink()
    
    # Run script
    subprocess.run(
        [
            sys.executable,
            "scripts/generate_d82_12_lowered_tp_entry_candidates.py",
            "--output-path", str(output_path),
        ],
        capture_output=True,
        cwd=Path(__file__).parent.parent,
        check=True,
    )
    
    # Load JSON
    with open(output_path) as f:
        data = json.load(f)
    
    # Check each candidate
    for cand in data["candidates"]:
        # TP > Entry
        assert cand["tp_bps"] > cand["entry_bps"]
        
        # Entry in [5, 7, 10]
        assert cand["entry_bps"] in [5.0, 7.0, 10.0]
        
        # TP in [7, 10, 12]
        assert cand["tp_bps"] in [7.0, 10.0, 12.0]
        
        # All D77-4 baseline
        assert cand["is_d77_4_baseline"] is True
        
        # All recommended
        assert cand["is_recommended"] is True
    
    # Cleanup
    output_path.unlink()


# =============================================================================
# Edge Cases
# =============================================================================

def test_empty_lists():
    """Test with empty lists"""
    candidates = generate_candidates([], [])
    assert len(candidates) == 0


def test_single_entry_single_tp():
    """Test with single entry and single TP"""
    candidates = generate_candidates([5.0], [7.0])
    
    assert len(candidates) == 1
    assert candidates[0]["entry_bps"] == 5.0
    assert candidates[0]["tp_bps"] == 7.0


def test_invalid_combinations_filtered():
    """Test that TP <= Entry combinations are filtered out"""
    # Entry 10, TP 5 (invalid)
    candidates = generate_candidates([10.0], [5.0])
    
    # Should be filtered out
    assert len(candidates) == 0
    
    # Entry 7, TP 7 (equal, invalid)
    candidates = generate_candidates([7.0], [7.0])
    
    # Should be filtered out
    assert len(candidates) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
