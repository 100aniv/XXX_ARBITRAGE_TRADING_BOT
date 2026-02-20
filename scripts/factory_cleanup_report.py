#!/usr/bin/env python3
"""Factory disk/docker cleanup and reporting utility."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "logs" / "cleanup" / "cleanup_report.json"
VOLUME_PROTECT_TOKENS = ("arbitrage", "postgres", "redis")


def run_capture(command: List[str]) -> Dict[str, object]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def gather_snapshots() -> Dict[str, Dict[str, object]]:
    return {
        "df_h": run_capture(["df", "-h"]),
        "docker_system_df_v": run_capture(["docker", "system", "df", "-v"]),
        "docker_image_top20": run_capture(
            [
                "bash",
                "-lc",
                "docker image ls --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | sort -k2 -h | tail -n 20",
            ]
        ),
        "repo_du_top30": run_capture(
            [
                "bash",
                "-lc",
                "du -sh ./* 2>/dev/null | sort -h | tail -n 30",
            ]
        ),
    }


def prune_safe_volumes() -> Dict[str, object]:
    listed = run_capture(["docker", "volume", "ls", "-qf", "dangling=true"])
    if listed["exit_code"] != 0:
        return {
            "list": listed,
            "removed": [],
            "skipped": [],
            "remove_results": [],
        }

    names = [line.strip() for line in str(listed["stdout"]).splitlines() if line.strip()]
    removed: List[str] = []
    skipped: List[str] = []
    remove_results: List[Dict[str, object]] = []

    for name in names:
        lowered = name.lower()
        if any(token in lowered for token in VOLUME_PROTECT_TOKENS):
            skipped.append(name)
            continue
        rm_result = run_capture(["docker", "volume", "rm", name])
        remove_results.append(rm_result)
        if rm_result["exit_code"] == 0:
            removed.append(name)

    return {
        "list": listed,
        "removed": removed,
        "skipped": skipped,
        "remove_results": remove_results,
    }


def main() -> int:
    before = gather_snapshots()

    cleanup_actions = {
        "docker_builder_prune": run_capture(["docker", "builder", "prune", "-af"]),
        "docker_image_prune": run_capture(["docker", "image", "prune", "-af"]),
        "docker_container_prune": run_capture(["docker", "container", "prune", "-f"]),
        "docker_volume_prune_safe": prune_safe_volumes(),
    }

    after = gather_snapshots()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "volume_protect_tokens": list(VOLUME_PROTECT_TOKENS),
            "note": "DB/service volumes with arbitrage/postgres/redis tokens are skipped",
        },
        "before": before,
        "actions": cleanup_actions,
        "after": after,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[CLEANUP_REPORT] path={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
