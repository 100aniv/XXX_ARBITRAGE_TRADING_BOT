#!/usr/bin/env python3
"""Smart storage cleanup utility for local workspace maintenance."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

TEXT_EXTENSIONS = {".log", ".json", ".txt"}
CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox",
}
EXCLUDED_TOPLEVEL_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "trading_bot_env",
    "abt_bot_env",
    "node_modules",
}


@dataclass
class CleanupResult:
    name: str
    bytes_freed: int
    deleted_files: int
    deleted_dirs: int
    notes: List[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def bytes_to_gb(value: int) -> float:
    return round(value / (1024 ** 3), 4)


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except (FileNotFoundError, PermissionError, OSError):
        return 0


def dir_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += file_size(item)
    except (PermissionError, OSError):
        return total
    return total


def is_excluded_path(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    if not rel.parts:
        return False
    return rel.parts[0] in EXCLUDED_TOPLEVEL_DIRS


def iter_text_logs(logs_root: Path) -> Iterable[Path]:
    if not logs_root.exists():
        return []
    return (
        p
        for p in logs_root.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS
    )


def contains_pass_token(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if b"PASS" in chunk:
                    return True
    except OSError:
        return False
    return False


def purge_old_logs(
    logs_root: Path,
    retention_days: int,
    keep_pass_count: int,
    dry_run: bool,
) -> CleanupResult:
    cutoff = utc_now() - timedelta(days=retention_days)
    pass_candidates: List[Tuple[float, Path]] = []

    for p in iter_text_logs(logs_root):
        if contains_pass_token(p):
            try:
                pass_candidates.append((p.stat().st_mtime, p))
            except FileNotFoundError:
                continue

    pass_candidates.sort(key=lambda item: item[0], reverse=True)
    pass_keep_set = {p for _, p in pass_candidates[:keep_pass_count]}

    deleted_files = 0
    bytes_freed = 0
    notes: List[str] = []

    for p in iter_text_logs(logs_root):
        try:
            modified = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except FileNotFoundError:
            continue

        if modified >= cutoff:
            continue
        if p in pass_keep_set:
            continue

        size = file_size(p)
        if not dry_run:
            try:
                p.unlink()
            except FileNotFoundError:
                continue
        deleted_files += 1
        bytes_freed += size

    notes.append(f"retention_days={retention_days}")
    notes.append(f"kept_pass_logs={len(pass_keep_set)}")
    notes.append(f"detected_pass_logs={len(pass_candidates)}")
    return CleanupResult(
        name="log_purge",
        bytes_freed=bytes_freed,
        deleted_files=deleted_files,
        deleted_dirs=0,
        notes=notes,
    )


def cleanup_cache_dirs(repo_root: Path, dry_run: bool) -> CleanupResult:
    cache_dirs = [
        p
        for p in repo_root.rglob("*")
        if p.is_dir() and p.name in CACHE_DIR_NAMES and not is_excluded_path(p, repo_root)
    ]
    cache_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    deleted_dirs = 0
    deleted_files = 0
    bytes_freed = 0

    for cache_dir in cache_dirs:
        size = dir_size(cache_dir)
        file_count = 0
        try:
            file_count = sum(1 for f in cache_dir.rglob("*") if f.is_file())
        except (PermissionError, OSError):
            file_count = 0
        if not dry_run:
            shutil.rmtree(cache_dir, ignore_errors=True)
        deleted_dirs += 1
        deleted_files += file_count
        bytes_freed += size

    pyc_files = [
        p
        for p in repo_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pyc", ".pyo"} and not is_excluded_path(p, repo_root)
    ]
    for pyc in pyc_files:
        size = file_size(pyc)
        if not dry_run:
            try:
                pyc.unlink()
            except (FileNotFoundError, PermissionError, OSError):
                continue
        deleted_files += 1
        bytes_freed += size

    return CleanupResult(
        name="cache_cleanup",
        bytes_freed=bytes_freed,
        deleted_files=deleted_files,
        deleted_dirs=deleted_dirs,
        notes=[f"cache_dirs={len(cache_dirs)}", f"pyc_files={len(pyc_files)}"],
    )


def summarize_large_json(path: Path, size_bytes: int) -> str:
    preview = ""
    try:
        with path.open("rb") as handle:
            preview = handle.read(8192).decode("utf-8", errors="ignore")
    except OSError:
        preview = "<preview_unavailable>"

    return "\n".join(
        [
            f"source_file={path}",
            f"generated_at_utc={iso_utc(utc_now())}",
            f"size_bytes={size_bytes}",
            f"size_gb={bytes_to_gb(size_bytes)}",
            f"modified_at_utc={iso_utc(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))}",
            "preview_head=",
            preview[:2000],
        ]
    )


def manage_large_evidence_json(
    evidence_root: Path,
    threshold_bytes: int,
    dry_run: bool,
) -> CleanupResult:
    deleted_files = 0
    bytes_freed = 0
    notes: List[str] = []

    if not evidence_root.exists():
        return CleanupResult("evidence_management", 0, 0, 0, ["evidence_root_missing"])

    large_json_files = [
        p
        for p in evidence_root.rglob("*.json")
        if p.is_file() and file_size(p) > threshold_bytes
    ]

    for json_file in large_json_files:
        size = file_size(json_file)
        summary_path = json_file.with_suffix(json_file.suffix + ".summary.txt")
        summary_text = summarize_large_json(json_file, size)

        if not dry_run:
            summary_path.write_text(summary_text, encoding="utf-8")
            try:
                json_file.unlink()
            except FileNotFoundError:
                continue

        deleted_files += 1
        bytes_freed += size
        notes.append(f"summarized_and_removed={json_file}")

    notes.insert(0, f"threshold_bytes={threshold_bytes}")
    notes.insert(1, f"large_json_count={len(large_json_files)}")
    return CleanupResult(
        name="evidence_management",
        bytes_freed=bytes_freed,
        deleted_files=deleted_files,
        deleted_dirs=0,
        notes=notes,
    )


def retain_latest_evidence_runs(
    evidence_root: Path,
    keep_runs: int,
    dry_run: bool,
) -> CleanupResult:
    if not evidence_root.exists():
        return CleanupResult("evidence_retention", 0, 0, 0, ["evidence_root_missing"])

    runs = [p for p in evidence_root.iterdir() if p.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    stale_runs = runs[max(keep_runs, 0) :]

    bytes_freed = 0
    deleted_dirs = 0
    deleted_files = 0
    notes: List[str] = [
        f"keep_runs={keep_runs}",
        f"total_runs={len(runs)}",
        f"stale_runs={len(stale_runs)}",
    ]

    for run_dir in stale_runs:
        size = dir_size(run_dir)
        file_count = 0
        try:
            file_count = sum(1 for item in run_dir.rglob("*") if item.is_file())
        except (PermissionError, OSError):
            file_count = 0

        if not dry_run:
            shutil.rmtree(run_dir, ignore_errors=True)

        bytes_freed += size
        deleted_dirs += 1
        deleted_files += file_count

    return CleanupResult(
        name="evidence_retention",
        bytes_freed=bytes_freed,
        deleted_files=deleted_files,
        deleted_dirs=deleted_dirs,
        notes=notes,
    )


def build_du_report(repo_root: Path, top_k: int = 40) -> Dict[str, object]:
    entries: List[Tuple[str, int]] = []
    for item in repo_root.iterdir():
        if item.name in EXCLUDED_TOPLEVEL_DIRS:
            continue
        if item.is_file():
            size = file_size(item)
        elif item.is_dir():
            size = dir_size(item)
        else:
            continue
        entries.append((item.name, size))

    entries.sort(key=lambda pair: pair[1], reverse=True)
    return {
        "generated_at_utc": iso_utc(utc_now()),
        "top_k": top_k,
        "items": [
            {
                "path": name,
                "size_bytes": size,
                "size_gb": bytes_to_gb(size),
            }
            for name, size in entries[:top_k]
        ],
    }


def ensure_report_dir(repo_root: Path) -> Path:
    report_dir = repo_root / "logs" / "cleanup"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart storage cleanup")
    parser.add_argument("--retention-days", type=int, default=3)
    parser.add_argument("--keep-pass", type=int, default=5)
    parser.add_argument("--evidence-threshold-gb", type=float, default=1.0)
    parser.add_argument("--evidence-keep", type=int, default=20)
    parser.add_argument("--du-report", default="logs/cleanup/du_report.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    logs_root = repo_root / "logs"
    evidence_root = logs_root / "evidence"

    threshold_bytes = int(args.evidence_threshold_gb * (1024 ** 3))

    results = [
        purge_old_logs(
            logs_root=logs_root,
            retention_days=args.retention_days,
            keep_pass_count=args.keep_pass,
            dry_run=args.dry_run,
        ),
        cleanup_cache_dirs(repo_root=repo_root, dry_run=args.dry_run),
        retain_latest_evidence_runs(
            evidence_root=evidence_root,
            keep_runs=args.evidence_keep,
            dry_run=args.dry_run,
        ),
        manage_large_evidence_json(
            evidence_root=evidence_root,
            threshold_bytes=threshold_bytes,
            dry_run=args.dry_run,
        ),
    ]

    total_freed = sum(item.bytes_freed for item in results)
    generated_at = utc_now()

    report = {
        "generated_at_utc": iso_utc(generated_at),
        "dry_run": args.dry_run,
        "retention_days": args.retention_days,
        "keep_pass": args.keep_pass,
        "evidence_threshold_gb": args.evidence_threshold_gb,
        "total_bytes_freed": total_freed,
        "total_gb_freed": bytes_to_gb(total_freed),
        "steps": [
            {
                "name": item.name,
                "bytes_freed": item.bytes_freed,
                "gb_freed": bytes_to_gb(item.bytes_freed),
                "deleted_files": item.deleted_files,
                "deleted_dirs": item.deleted_dirs,
                "notes": item.notes,
            }
            for item in results
        ],
    }

    report_dir = ensure_report_dir(repo_root)
    report_path = report_dir / f"cleanup_storage_{generated_at.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    du_report_path = Path(args.du_report)
    if not du_report_path.is_absolute():
        du_report_path = repo_root / du_report_path
    du_report_path.parent.mkdir(parents=True, exist_ok=True)
    du_report = build_du_report(repo_root=repo_root)
    du_report_path.write_text(json.dumps(du_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[CLEANUP] report={report_path}")
    print(f"[CLEANUP] du_report={du_report_path}")
    print(f"[CLEANUP] dry_run={args.dry_run}")
    print(f"[CLEANUP] total_bytes_freed={total_freed}")
    print(f"[CLEANUP] total_gb_freed={bytes_to_gb(total_freed)}")

    for item in results:
        print(
            f"[CLEANUP] step={item.name} bytes_freed={item.bytes_freed} "
            f"deleted_files={item.deleted_files} deleted_dirs={item.deleted_dirs}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
