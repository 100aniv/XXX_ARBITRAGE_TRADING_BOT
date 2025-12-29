#!/usr/bin/env python3
"""
D200-3 Gate Execution with Evidence Generation
Purpose: Run doctor gate and generate evidence with d200-3 run_id
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.evidence_pack import EvidencePacker

def run_gate(packer, gate_name, command):
    """Run a gate and record result"""
    print(f"\n{'='*60}")
    print(f"Running Gate: {gate_name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=False,
            text=True,
            cwd=str(project_root)
        )
        
        exit_code = result.returncode
        status = "PASS" if exit_code == 0 else "FAIL"
        
        packer.add_gate_result(gate_name, status, f"Exit code: {exit_code}")
        print(f"\n✅ {gate_name}: {status}")
        
        return exit_code == 0
    except Exception as e:
        print(f"\n❌ {gate_name}: ERROR - {e}")
        packer.add_gate_result(gate_name, "ERROR", str(e))
        return False

def main():
    """Main execution"""
    print("="*60)
    print("D200-3 Gate Execution with Evidence")
    print("="*60)
    
    # Initialize evidence packer
    packer = EvidencePacker('d200-3', 'D200-3 Gate Execution')
    packer.start()
    
    print(f"\n📁 Evidence run_id: {packer.run_id}")
    print(f"📁 Evidence path: {packer.evidence_dir}")
    
    # Run doctor gate
    doctor_cmd = r".\abt_bot_env\Scripts\python.exe -m pytest tests/ --collect-only -q"
    doctor_pass = run_gate(packer, "doctor", doctor_cmd)
    
    if not doctor_pass:
        print("\n❌ Doctor gate failed. Stopping.")
        packer.manifest["status"] = "FAILED"
        packer._write_manifest()
        return 1
    
    # Finalize evidence
    packer.manifest["status"] = "PASSED"
    packer._write_manifest()
    
    print(f"\n✅ Evidence generated: {packer.evidence_dir}")
    print(f"✅ Files:")
    for f in packer.evidence_dir.glob("*"):
        print(f"   - {f.name}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
