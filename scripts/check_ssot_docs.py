#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSOT DocOps Checker (Doc-only hygiene gate)

Purpose:
- Prevent "doc-only SSOT" work from taking 2~4 patch iterations.
- Enforce immutable D-number semantics + branching-only expansion.
- Enforce D_ROADMAP as the single process SSOT + conflict resolution rule.
- Catch common doc rot:
  - COMPLETED but contains TODO/TBD/placeholder/"문서 기반 완료"
  - local/IDE links like cci: / file:/// / c:\\work
  - report filename pattern violations
  - known semantic conflicts (e.g., D205-11 described as Threshold)

Usage:
  python scripts/check_ssot_docs.py
  python scripts/check_ssot_docs.py --root .
  python scripts/check_ssot_docs.py --no-cci-check   (not recommended)
  python scripts/check_ssot_docs.py --no-report-name-check
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

# Force UTF-8 output on Windows (prevent cp949 UnicodeEncodeError)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# -----------------------------
# Config (paths)
# -----------------------------
DEFAULT_D_ROADMAP = "D_ROADMAP.md"
DEFAULT_SSOT_RULES = "docs/v2/SSOT_RULES.md"
DEFAULT_SSOT_MAP = "docs/v2/design/SSOT_MAP.md"
DEFAULT_V2_ARCH = "docs/v2/V2_ARCHITECTURE.md"
DEFAULT_REPORTS_DIR = "docs/v2/reports"
DEFAULT_DOCS_DIR = "docs/v2"

# -----------------------------
# Heuristics / rules
# -----------------------------
# Required concepts (must appear in each SSOT doc in some form)
CONCEPT_RULES = {
    "ssot_single_source": [
        r"\bSSOT\b",
        r"D_ROADMAP\.md",
        r"유일",  # Korean "only"
    ],
    "immutable_semantics": [
        r"불변",             # immutable
        r"Immutable",
        r"D\s*번호.*(불변|변경\s*금지)",
    ],
    "branching_only": [
        r"브랜치",           # branch
        r"\bbranch\b",
        r"D\d{3}-\d+(?:-\d+)*",  # Dxxx-y(-z...) mention
    ],
    "conflict_resolution": [
        r"충돌",             # conflict
        r"conflict",
        r"D_ROADMAP.*우선",  # D_ROADMAP priority
        r"우선.*D_ROADMAP",
    ],
    "evidence_based_done": [
        r"Evidence",
        r"증거",
        r"COMPLETED",
        r"DONE",
        r"허위",             # false/lying
    ],
}

# "Completed but doc still says TODO" kind of smells
COMPLETED_BAD_MARKERS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bPLACEHOLDER\b",
    r"미완",            # incomplete
    r"문서\s*기반\s*완료",  # doc-based completion
    r"실제\s*실행\s*없음",
    r"evidence\s*재사용",  # if you want stricter, keep it here
]

# local/IDE links that must not survive in committed docs
CCI_BAD_MARKERS = [
    r"\bcci:",
    r"file:///",
    r"c:\\\\work\\\\",
    r"c:/work/",
]

# Report filename rule:
# - Dxxx_REPORT.md
# - Dxxx-y_REPORT.md
# - Dxxx-y-z_REPORT.md
# - DALPHA-x_REPORT.md (Alpha track)
# - (allow up to 3 hyphen segments after Dxxx/DALPHA)
REPORT_NAME_RE = re.compile(r"^(?:D\d{3}(?:-\d+){0,3}|DALPHA(?:-[0-9A-Z]+){0,3})_REPORT\.md$")

# Known semantic conflict rules (minimal but effective)
# If these match -> FAIL.
SEMANTIC_CONFLICTS = [
    # D205-11 must not be Threshold/Tuning/Sweep
    (
        "D205-11 must not be described as Threshold/Tuning/Sweep",
        re.compile(r"D205-11", re.IGNORECASE),
        re.compile(r"(threshold|tuning|sweep|sensitivity|민감도|튜닝)", re.IGNORECASE),
    ),
]


# -----------------------------
# Helpers
# -----------------------------
@dataclass
class Finding:
    severity: str  # "FAIL" | "WARN"
    where: str     # file path
    message: str
    line_no: Optional[int] = None
    excerpt: Optional[str] = None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # last resort
        return path.read_text(encoding="utf-8", errors="replace")


def iter_lines(text: str) -> Iterable[Tuple[int, str]]:
    for i, line in enumerate(text.splitlines(), start=1):
        yield i, line


def rg_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE | re.MULTILINE) for p in patterns)


def first_match_line(text: str, pattern: str) -> Optional[Tuple[int, str]]:
    rx = re.compile(pattern, re.IGNORECASE)
    for ln, line in iter_lines(text):
        if rx.search(line):
            return ln, line.rstrip("\n")
    return None


def collect_md_files(root: Path, under: Path) -> List[Path]:
    base = root / under
    if not base.exists():
        return []
    return sorted([p for p in base.rglob("*.md") if p.is_file()])


# -----------------------------
# Checks
# -----------------------------
def check_file_exists(root: Path, rel_path: str) -> List[Finding]:
    p = root / rel_path
    if not p.exists():
        return [Finding("FAIL", rel_path, "File missing")]
    return []


def check_d_roadmap_global_rules(root: Path, roadmap_rel: str) -> List[Finding]:
    findings: List[Finding] = []
    p = root / roadmap_rel
    text = read_text(p)

    # Only enforce in the "top" portion to ensure it's truly global.
    top = "\n".join(text.splitlines()[:220])

    required = {
        "ssot_single_source": [r"\bSSOT\b", r"D_ROADMAP\.md", r"유일"],
        "immutable_semantics": [r"불변", r"Immutable", r"D\s*번호"],
        "branching_only": [r"브랜치", r"\bbranch\b", r"D\d{3}-\d+"],
        "conflict_resolution": [r"충돌", r"conflict", r"D_ROADMAP.*우선", r"우선.*D_ROADMAP"],
        "evidence_based_done": [r"Evidence", r"증거", r"허위", r"COMPLETED", r"DONE"],
    }

    for concept, pats in required.items():
        if not rg_any(top, pats):
            findings.append(
                Finding(
                    "FAIL",
                    roadmap_rel,
                    f"D_ROADMAP global section missing concept: {concept}",
                    line_no=None,
                    excerpt=None,
                )
            )

    return findings


def check_ssot_docs_concepts(root: Path, ssot_files: List[Tuple[str, str]]) -> List[Finding]:
    """
    ssot_files: list of (label, rel_path)
    """
    findings: List[Finding] = []
    for label, rel in ssot_files:
        p = root / rel
        text = read_text(p)

        for concept, pats in CONCEPT_RULES.items():
            if not rg_any(text, pats):
                findings.append(
                    Finding(
                        "FAIL",
                        rel,
                        f"[{label}] missing SSOT concept: {concept}",
                    )
                )
    return findings


def check_semantic_conflicts(root: Path, md_files: List[Path]) -> List[Finding]:
    findings: List[Finding] = []
    for f in md_files:
        rel = str(f)
        text = read_text(f)

        # line-based for more precise reporting
        for rule_name, left_rx, right_rx in SEMANTIC_CONFLICTS:
            for ln, line in iter_lines(text):
                if left_rx.search(line) and right_rx.search(line):
                    findings.append(
                        Finding(
                            "FAIL",
                            rel,
                            f"Semantic conflict: {rule_name}",
                            line_no=ln,
                            excerpt=line.strip(),
                        )
                    )
    return findings


def check_completed_without_todos(root: Path, md_files: List[Path]) -> List[Finding]:
    findings: List[Finding] = []

    bad_rx = re.compile("|".join(COMPLETED_BAD_MARKERS), re.IGNORECASE)
    completed_rx = re.compile(r"\bCOMPLETED\b|\[x\]\s*COMPLETED", re.IGNORECASE)

    for f in md_files:
        text = read_text(f)
        lines = list(iter_lines(text))

        # If file claims COMPLETED anywhere, it must not contain bad markers anywhere (strict).
        file_is_completed = any(completed_rx.search(line) for _, line in lines)
        if file_is_completed:
            for ln, line in lines:
                if bad_rx.search(line):
                    findings.append(
                        Finding(
                            "FAIL",
                            str(f),
                            "COMPLETED doc contains TODO/TBD/placeholder/doc-only-complete marker",
                            line_no=ln,
                            excerpt=line.strip(),
                        )
                    )
                    break  # one is enough per file (keep output readable)

    return findings


def check_cci_links(root: Path, md_files: List[Path]) -> List[Finding]:
    findings: List[Finding] = []
    bad_rx = re.compile("|".join(CCI_BAD_MARKERS), re.IGNORECASE)

    for f in md_files:
        text = read_text(f)
        for ln, line in iter_lines(text):
            if bad_rx.search(line):
                findings.append(
                    Finding(
                        "FAIL",
                        str(f),
                        "Local/IDE link residue detected (cci:/file:///c:\\work) — must not be committed",
                        line_no=ln,
                        excerpt=line.strip(),
                    )
                )
                break

    return findings


def check_report_filenames(root: Path, reports_dir_rel: str) -> List[Finding]:
    findings: List[Finding] = []
    reports_dir = root / reports_dir_rel
    if not reports_dir.exists():
        findings.append(Finding("FAIL", reports_dir_rel, "Reports directory missing"))
        return findings

    for f in sorted(reports_dir.rglob("*.md")):
        if not f.is_file():
            continue
        name = f.name
        if not REPORT_NAME_RE.match(name):
            findings.append(
                Finding(
                    "FAIL",
                    str(f),
                    f"Report filename violates pattern: {REPORT_NAME_RE.pattern}",
                )
            )
    return findings


def print_findings(findings: List[Finding]) -> None:
    if not findings:
        print("[PASS] SSOT DocOps: PASS (0 issues)")
        return

    fails = [x for x in findings if x.severity == "FAIL"]
    warns = [x for x in findings if x.severity == "WARN"]

    if fails:
        print(f"[FAIL] SSOT DocOps: FAIL ({len(fails)} failures, {len(warns)} warnings)")
    else:
        print(f"[WARN] SSOT DocOps: WARN ({len(warns)} warnings)")

    # grouped output
    for f in findings:
        loc = f.where
        if f.line_no is not None:
            loc = f"{loc}:{f.line_no}"
        print(f"- [{f.severity}] {loc} - {f.message}")
        if f.excerpt:
            # ASCII-safe excerpt (Windows cp949 호환)
            safe_excerpt = f.excerpt.encode('ascii', errors='replace').decode('ascii')
            print(f"         -> {safe_excerpt}")


def main() -> int:
    ap = argparse.ArgumentParser(description="SSOT DocOps checker (doc-only hygiene gate)")
    ap.add_argument("--root", default=".", help="Repo root path (default: .)")
    ap.add_argument("--roadmap", default=DEFAULT_D_ROADMAP, help="Path to D_ROADMAP.md")
    ap.add_argument("--ssot-rules", default=DEFAULT_SSOT_RULES, help="Path to SSOT_RULES.md")
    ap.add_argument("--ssot-map", default=DEFAULT_SSOT_MAP, help="Path to SSOT_MAP.md")
    ap.add_argument("--v2-arch", default=DEFAULT_V2_ARCH, help="Path to V2_ARCHITECTURE.md")
    ap.add_argument("--docs-dir", default=DEFAULT_DOCS_DIR, help="Docs base dir to scan (default: docs/v2)")
    ap.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR, help="Reports dir to check names (default: docs/v2/reports)")
    ap.add_argument("--no-cci-check", action="store_true", help="Disable cci/file:///c:\\work residue check (NOT recommended)")
    ap.add_argument("--no-report-name-check", action="store_true", help="Disable report filename pattern check")
    ap.add_argument("--no-completed-todo-check", action="store_true", help="Disable COMPLETED vs TODO/TBD strict check")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    findings: List[Finding] = []

    # 0) must-have files exist
    must_files = [
        ("D_ROADMAP", args.roadmap),
        ("SSOT_RULES", args.ssot_rules),
        ("SSOT_MAP", args.ssot_map),
        ("V2_ARCHITECTURE", args.v2_arch),
    ]
    for _, rel in must_files:
        findings += check_file_exists(root, rel)

    # stop early if missing core files
    if any(f.severity == "FAIL" and f.message == "File missing" for f in findings):
        print_findings(findings)
        return 1

    # 1) D_ROADMAP global rules (top section) must include core concepts
    findings += check_d_roadmap_global_rules(root, args.roadmap)

    # 2) all 4 SSOT docs must contain the same core concepts (presence check)
    ssot_docs = [
        ("Process SSOT", args.roadmap),
        ("Rules SSOT", args.ssot_rules),
        ("Map SSOT", args.ssot_map),
        ("Architecture SSOT", args.v2_arch),
    ]
    findings += check_ssot_docs_concepts(root, ssot_docs)

    # 3) scan docs for semantic conflicts (minimal known rules)
    docs_md = collect_md_files(root, Path(args.docs_dir))
    # include D_ROADMAP too
    docs_md = [root / args.roadmap] + docs_md
    # de-dup
    seen = set()
    uniq_docs_md: List[Path] = []
    for p in docs_md:
        rp = str(p.resolve())
        if rp not in seen and p.exists():
            seen.add(rp)
            uniq_docs_md.append(p)

    findings += check_semantic_conflicts(root, uniq_docs_md)

    # 4) COMPLETED must not contain TODO/TBD/etc (strict)
    if not args.no_completed_todo_check:
        findings += check_completed_without_todos(root, uniq_docs_md)

    # 5) cci/file:///c:\work residues are forbidden
    if not args.no_cci_check:
        findings += check_cci_links(root, uniq_docs_md)

    # 6) report filenames must follow pattern
    if not args.no_report_name_check:
        findings += check_report_filenames(root, args.reports_dir)

    print_findings(findings)

    # exit code
    has_fail = any(f.severity == "FAIL" for f in findings)
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())