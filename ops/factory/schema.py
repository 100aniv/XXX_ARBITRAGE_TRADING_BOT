from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Dict, List

SCHEMA_VERSION = "1.0"


@dataclass
class PlanScope:
    modify: List[str] = field(default_factory=list)
    readonly: List[str] = field(default_factory=list)
    forbidden: List[str] = field(default_factory=list)


@dataclass
class FactoryPlan:
    schema_version: str
    mode: str
    ticket_id: str
    ac_id: str
    title: str
    created_at_utc: str
    scope: PlanScope
    done_criteria: str
    notes: List[str] = field(default_factory=list)
    risk_level: str = "mid"
    model_budget: str = "mid"
    model_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class CommandResult:
    name: str
    command: List[str]
    exit_code: int
    duration_sec: float


@dataclass
class FactoryResult:
    schema_version: str
    mode: str
    ticket_id: str
    ac_id: str
    status: str
    created_at_utc: str
    commands: List[CommandResult]
    gate_exit_code: int
    docops_exit_code: int
    evidence_check_exit_code: int
    evidence_latest: str
    notes: List[str] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_to_dict(plan: FactoryPlan) -> Dict[str, Any]:
    data = asdict(plan)
    data["scope"] = asdict(plan.scope)
    return data


def result_to_dict(result: FactoryResult) -> Dict[str, Any]:
    data = asdict(result)
    data["commands"] = [asdict(c) for c in result.commands]
    return data


def validate_plan(data: Dict[str, Any]) -> None:
    required_top = ["schema_version", "mode", "ticket_id", "ac_id", "title", "scope", "done_criteria"]
    for key in required_top:
        if key not in data:
            raise ValueError(f"plan missing required key: {key}")

    scope = data.get("scope", {})
    for key in ["modify", "readonly", "forbidden"]:
        if key not in scope or not isinstance(scope[key], list):
            raise ValueError(f"plan.scope.{key} must be a list")

    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {data['schema_version']}")
