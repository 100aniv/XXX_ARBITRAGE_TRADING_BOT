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
    # config.yml에서 universe 섹션 직접 로드
    config_path = Path("config/v2/config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    universe_config = config_data.get("universe", {})
    
    # from_config_dict 사용하여 UniverseBuilder 생성
    builder = from_config_dict(universe_config)
    snapshot = builder.get_snapshot()
    
    output_file = Path("logs/evidence/d205_15_2_evidence_20260108_012733/universe/universe_snapshot_clean.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Evidence Guard 적용하여 저장 + 즉시 검증
    save_json_with_validation(output_file, snapshot)
    
    print(f"[OK] Universe snapshot saved & validated: {output_file}")


if __name__ == "__main__":
    main()
