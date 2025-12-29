#!/usr/bin/env python3
"""
Initialize Evidence Packer for D200-3
Purpose: Create evidence folder with d200-3 run_id
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.evidence_pack import EvidencePacker

def main():
    """Initialize evidence packer for d200-3"""
    try:
        packer = EvidencePacker('d200-3', 'watchdog gate execution')
        packer.start()
        
        print(f"Evidence run_id: {packer.run_id}")
        print(f"Evidence path: {packer.evidence_dir}")
        print(f"Manifest: {packer.manifest_path}")
        print(f"Git info: {packer.git_info_path}")
        
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
