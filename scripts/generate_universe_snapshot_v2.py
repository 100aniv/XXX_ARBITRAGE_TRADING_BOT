"""
D205-15-2: Universe Snapshot Generator (null bytes 제거)
Evidence Integrity Guard 적용하여 깨끗한 JSON 생성
"""

import json
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.universe.builder import from_config_dict
from arbitrage.v2.scan.evidence_guard import save_json_with_validation


def main():
    config_path = Path("config/v2/config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    universe_config = config_data.get("universe", {})
    builder = from_config_dict(universe_config)
    snapshot = builder.get_snapshot()
    
    output_file = Path("logs/evidence/d205_15_2_evidence_20260108_012733/universe/universe_snapshot_clean.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    save_json_with_validation(output_file, snapshot)
    print(f"[OK] Universe snapshot saved & validated: {output_file}")


if __name__ == "__main__":
    main()
