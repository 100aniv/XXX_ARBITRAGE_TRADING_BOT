#!/usr/bin/env python3
"""
Generate D200-3 Evidence (minimal approach)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

def get_git_info():
    """Get git information"""
    git_info = {
        "timestamp": datetime.now().isoformat(),
        "branch": "unknown",
        "commit": "unknown",
        "status": "unknown",
    }
    
    try:
        # Branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            git_info["branch"] = result.stdout.strip()
        
        # Commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            git_info["commit"] = result.stdout.strip()
        
        # Status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            status_output = result.stdout.strip() if result.stdout else ""
            git_info["status"] = "clean" if not status_output else "dirty"
    
    except Exception as e:
        git_info["error"] = str(e)
    
    return git_info

def main():
    """Generate evidence"""
    # Create run_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get git short hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        short_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        short_hash = "unknown"
    
    run_id = f"{timestamp}_d200-3_{short_hash}"
    evidence_dir = Path("logs/evidence") / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Write git_info.json
    git_info = get_git_info()
    git_info_path = evidence_dir / "git_info.json"
    git_info_path.write_text(json.dumps(git_info, indent=2, ensure_ascii=False))
    
    # Write manifest.json
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "d_number": "d200-3",
        "task_name": "D200-3 Gate Execution",
        "status": "IN_PROGRESS",
        "gates": {}
    }
    manifest_path = evidence_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    # Write cmd_history.txt
    cmd_history_path = evidence_dir / "cmd_history.txt"
    cmd_history_path.write_text(f"# D200-3 Gate Execution\n# {datetime.now().isoformat()}\n\n")
    
    print(f"Evidence run_id: {run_id}")
    print(f"Evidence path: {evidence_dir}")
    print(f"git_info.json: {git_info}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
