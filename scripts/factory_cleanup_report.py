#!/usr/bin/env python3
"""Factory disk/docker cleanup and reporting utility."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def prune_safe_volumes(apply: bool) -> Dict[str, object]:
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
        if apply:
            rm_result = run_capture(["docker", "volume", "rm", name])
            remove_results.append(rm_result)
            if rm_result["exit_code"] == 0:
                removed.append(name)
        else:
            remove_results.append({
                "command": f"docker volume rm {name}",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            })

    return {
        "list": listed,
        "removed": removed,
        "skipped": skipped,
        "remove_results": remove_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe docker cleanup report")
    parser.add_argument("--apply", action="store_true", help="run prune actions")
    parser.add_argument("--preview", action="store_true", help="preview only (default)")
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="also run docker system prune -af --volumes (dangerous)",
    )
    parser.add_argument(
        "--pip-cache-purge",
        action="store_true",
        help="purge pip cache on host (optional)",
    )
    args = parser.parse_args()

    apply = bool(args.apply)
    before = gather_snapshots()

    if apply:
        cleanup_actions = {
            "docker_builder_prune": run_capture(["docker", "builder", "prune", "-af"]),
            "docker_image_prune": run_capture(["docker", "image", "prune", "-af"]),
            "docker_container_prune": run_capture(["docker", "container", "prune", "-f"]),
            "docker_network_prune": run_capture(["docker", "network", "prune", "-f"]),
            "docker_volume_prune_safe": prune_safe_volumes(apply=True),
        }
        if args.unsafe:
            cleanup_actions["docker_system_prune_volumes"] = run_capture(
                ["docker", "system", "prune", "-af", "--volumes"]
            )
        if args.pip_cache_purge:
            cleanup_actions["pip_cache_purge"] = run_capture(
                [sys.executable, "-m", "pip", "cache", "purge"]
            )
    else:
        cleanup_actions = {
            "docker_builder_prune": {
                "command": "docker builder prune -af",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            },
            "docker_image_prune": {
                "command": "docker image prune -af",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            },
            "docker_container_prune": {
                "command": "docker container prune -f",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            },
            "docker_network_prune": {
                "command": "docker network prune -f",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            },
            "docker_volume_prune_safe": prune_safe_volumes(apply=False),
        }
        if args.unsafe:
            cleanup_actions["docker_system_prune_volumes"] = {
                "command": "docker system prune -af --volumes",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            }
        if args.pip_cache_purge:
            cleanup_actions["pip_cache_purge"] = {
                "command": f"{sys.executable} -m pip cache purge",
                "exit_code": None,
                "stdout": "",
                "stderr": "preview_only",
            }

    after = gather_snapshots()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "preview",
        "policy": {
            "volume_protect_tokens": list(VOLUME_PROTECT_TOKENS),
            "note": "DB/service volumes with arbitrage/postgres/redis tokens are skipped",
            "unsafe_enabled": bool(args.unsafe),
            "pip_cache_purge": bool(args.pip_cache_purge),
        },
        "before": before,
        "actions": cleanup_actions,
        "after": after,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[CLEANUP_REPORT] mode={report['mode']} path={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
