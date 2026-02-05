"""
D000-1: SSOT Rules Guard

Ensures core SSOT governance documents exist and do not contain
forbidden placeholders that would break DocOps.
"""

from pathlib import Path
import re

SSOT_RULES_PATH = Path("docs/v2/SSOT_RULES.md")
D_ROADMAP_PATH = Path("D_ROADMAP.md")

FORBIDDEN_MARKERS = re.compile(r"\b(TODO|TBD|PLACEHOLDER)\b", re.IGNORECASE)


def _read_text(path: Path) -> str:
    assert path.exists(), f"SSOT document missing: {path}"
    return path.read_text(encoding="utf-8")


def _assert_no_forbidden_markers(text: str, label: str) -> None:
    matches = [m.group(0) for m in FORBIDDEN_MARKERS.finditer(text)]
    assert not matches, f"Forbidden markers detected in {label}: {matches}"


def test_ssot_rules_document_exists_and_clean():
    """SSOT_RULES.md must exist and remain free of forbidden markers."""
    text = _read_text(SSOT_RULES_PATH)
    assert "SSOT Rules" in text, "SSOT Rules header missing"
    _assert_no_forbidden_markers(text, "SSOT rules")


def test_d_roadmap_exists():
    """Roadmap must exist; it is the single source of truth."""
    text = _read_text(D_ROADMAP_PATH)
    first_line = text.splitlines()[0]
    assert "Roadmap" in first_line and "SSOT" in first_line, "D_ROADMAP header missing"
    _assert_no_forbidden_markers(text, "D_ROADMAP")
