import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(r"c:\\work\\XXX_ARBITRAGE_TRADING_BOT")
ROADMAP_PATH = ROOT / "D_ROADMAP.md"
SSOT_RULES_PATH = ROOT / "docs" / "v2" / "SSOT_RULES.md"
REPORTS_PATH = ROOT / "docs" / "v2" / "reports"
EVIDENCE_ROOT = ROOT / "logs" / "evidence"

STAGE_ORDER = ["D_ALPHA", "TURN5", "D206", "D207", "D208", "OTHER"]
KEYWORDS_PROFIT = [
    "pnl",
    "profit",
    "friction",
    "tail",
    "edge",
    "latency",
    "slippage",
    "fee",
    "spread",
    "partial",
    "execution",
    "weld",
    "maker",
    "taker",
]
KEYWORDS_DOCOPS = ["docops", "ssot", "check_ssot_docs"]


def detect_stage(token: str | None, heading_line: str) -> str:
    if "TURN5" in heading_line:
        return "TURN5"
    if token:
        if "D_ALPHA" in token:
            return "D_ALPHA"
        if token.startswith("D206") or "D206" in token:
            return "D206"
        if token.startswith("D207") or "D207" in token:
            return "D207"
        if token.startswith("D208") or "D208" in token:
            return "D208"
    return "OTHER"


def extract_paths(line: str) -> list[str]:
    paths: list[str] = []
    for match in re.findall(r"`([^`]+)`", line):
        if any(key in match for key in ["logs/evidence", "docs/v2/reports", "docs/v2/design", "tests/"]):
            paths.append(match.strip())
    if "logs/evidence/" in line and not paths:
        idx = line.find("logs/evidence/")
        if idx >= 0:
            tail = line[idx:].strip().split()[0].rstrip(").,")
            paths.append(tail)
    return paths


def normalize_title(title: str) -> str:
    lowered = title.lower()
    lowered = re.sub(r"fix-\d+(?:-\d+)*", "", lowered)
    lowered = re.sub(r"\d+", "", lowered)
    lowered = re.sub(r"[^a-z]+", "", lowered)
    return lowered


def intent_key(title: str) -> str:
    lowered = title.lower()
    hits = [key for key in KEYWORDS_PROFIT if key in lowered]
    if hits:
        return "|".join(sorted(set(hits)))
    return ""


def resolve_path(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    cleaned = path_str.strip("`").strip().rstrip(".,)")
    if cleaned.startswith("logs/") or cleaned.startswith("docs/") or cleaned.startswith("tests/"):
        return ROOT / cleaned
    return Path(cleaned)


def evidence_exists(path_str: str | None) -> bool:
    target = resolve_path(path_str)
    return bool(target and target.exists())


def is_profit_related(title: str) -> bool:
    lowered = title.lower()
    return any(key in lowered for key in KEYWORDS_PROFIT)


def is_docops_related(title: str) -> bool:
    lowered = title.lower()
    return any(key in lowered for key in KEYWORDS_DOCOPS)


roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
lines = roadmap_text.splitlines()

current_d = None
current_stage = "OTHER"
current_evidence: list[str] = []
current_gate = {"doctor": None, "fast": None, "regression": None}
collecting_evidence = False

records: list[dict] = []
seen_ids: dict[str, int] = {}

for idx, line in enumerate(lines):
    heading = re.match(r"^\s*#{2,6}\s+(.*)$", line)
    if heading:
        heading_text = heading.group(1)
        d_match = re.search(r"\bD(?:_ALPHA[\w-]*|[0-9]{3}(?:-[0-9A-Z]+)*)", heading_text)
        current_d = d_match.group(0) if d_match else current_d
        current_stage = detect_stage(current_d, heading_text)
        collecting_evidence = False
        current_evidence = []
        current_gate = {"doctor": None, "fast": None, "regression": None}

    if re.search(r"Evidence\s*경로", line):
        collecting_evidence = True
        current_evidence = []
        continue

    if collecting_evidence:
        if line.strip() == "" or line.strip().startswith("---") or re.match(r"^\s*#{2,6}\s+", line):
            collecting_evidence = False
        else:
            if line.strip().startswith("-"):
                paths = extract_paths(line)
                if paths:
                    current_evidence.extend(paths)
                if "Gate Doctor" in line or "Gate doctor" in line:
                    for path in extract_paths(line):
                        current_gate["doctor"] = path
                if "Gate Fast" in line or "Gate fast" in line:
                    for path in extract_paths(line):
                        current_gate["fast"] = path
                if "Gate Regression" in line or "Gate regression" in line:
                    for path in extract_paths(line):
                        current_gate["regression"] = path

    ac_match = re.match(r"^\s*-\s*\[(?P<chk>[ xX])\]\s*(?P<label>AC-\d+):\s*(?P<title>.+)$", line)
    if ac_match:
        label = ac_match.group("label")
        title = ac_match.group("title").strip()
        checked = ac_match.group("chk").lower() == "x"
        base_id = f"{current_d or 'AUTO-OTHER'}::{label}"
        ac_id = base_id
        if ac_id in seen_ids:
            seen_ids[ac_id] += 1
            ac_id = f"{base_id}-{seen_ids[base_id]}"
        else:
            seen_ids[ac_id] = 1
        records.append(
            {
                "ac_id": ac_id,
                "label": label,
                "title": title,
                "stage": current_stage,
                "checked": checked,
                "evidence_paths": list(dict.fromkeys(current_evidence)),
                "gate_paths": dict(current_gate),
                "line": idx + 1,
            }
        )

for record in records:
    canonical = "NONE"
    for path in record["evidence_paths"]:
        resolved = resolve_path(path)
        if resolved and resolved.exists() and resolved.is_dir():
            canonical = path
            break
    record["canonical"] = canonical

    gate_ok = True
    gate_missing: list[str] = []
    for gate_key in ["doctor", "fast", "regression"]:
        gate_path = record["gate_paths"].get(gate_key)
        if not gate_path or not evidence_exists(gate_path):
            gate_ok = False
            gate_missing.append(gate_key)
    record["gate_ok"] = gate_ok
    record["gate_missing"] = gate_missing

    notes: list[str] = []
    rule_hit = "NONE"
    required_ok = True

    if record["canonical"] == "NONE":
        required_ok = False
        notes.append("canonical evidence missing")

    if is_profit_related(record["title"]):
        if record["canonical"] != "NONE":
            ev_dir = resolve_path(record["canonical"])
            if ev_dir and ev_dir.exists() and ev_dir.is_dir():
                kpi_found = False
                breakdown_found = False
                for root_dir, _, files in os.walk(ev_dir):
                    for fname in files:
                        lf = fname.lower()
                        if lf == "kpi.json":
                            kpi_found = True
                        if any(
                            key in lf
                            for key in [
                                "pnl",
                                "friction",
                                "cost",
                                "latency",
                                "slippage",
                                "fee",
                                "execution",
                                "edge",
                            ]
                        ):
                            breakdown_found = True
                if not kpi_found:
                    required_ok = False
                    notes.append("missing kpi.json")
                if not breakdown_found:
                    required_ok = False
                    notes.append("missing pnl/friction breakdown artifact")
            else:
                required_ok = False
                notes.append("canonical evidence missing")
        else:
            required_ok = False
            notes.append("canonical evidence missing")

    if is_docops_related(record["title"]):
        if record["canonical"] != "NONE":
            ev_dir = resolve_path(record["canonical"])
            if ev_dir and ev_dir.exists() and ev_dir.is_dir():
                exitcode_file = ev_dir / "ssot_docs_check_exitcode.txt"
                if not exitcode_file.exists() or exitcode_file.read_text(encoding="utf-8").strip() != "0":
                    required_ok = False
                    notes.append("missing docops exitcode=0 proof")
            else:
                required_ok = False
                notes.append("canonical evidence missing")
        else:
            required_ok = False
            notes.append("canonical evidence missing")

    status = "OPEN"
    if record["gate_ok"] and required_ok:
        status = "DONE"
        rule_hit = "Gate3+Artifacts"

    record["status"] = status
    record["done_rule_hit"] = rule_hit
    record["notes"] = "; ".join(notes) if notes else ""

    norm = normalize_title(record["title"])
    intent = intent_key(record["title"])
    if record["canonical"] != "NONE":
        dup_key = f"EVID:{record['canonical']}"
    elif norm:
        dup_key = f"{record['stage']}:TITLE:{norm}"
    elif intent:
        dup_key = f"{record['stage']}:INTENT:{intent}"
    else:
        dup_key = f"{record['stage']}:TITLE:{record['title'].lower()}"
    record["dup_key"] = dup_key

# duplicate handling
merged_entries: list[dict] = []
dup_groups: dict[str, list[dict]] = {}
for record in records:
    dup_groups.setdefault(record["dup_key"], []).append(record)

for dup_key, group in dup_groups.items():
    if len(group) <= 1:
        continue
    representative = None
    for item in group:
        if item["status"] == "DONE":
            representative = item
            break
    if representative is None:
        for item in group:
            if item["canonical"] != "NONE":
                representative = item
                break
    if representative is None:
        representative = group[0]
    for item in group:
        if item is representative:
            continue
        item["status"] = "MERGED"
        item["merged_into"] = representative["ac_id"]
        item["notes"] = (item["notes"] + "; " if item["notes"] else "") + f"Merged: reason=dup_key({dup_key})"
        merged_entries.append(
            {
                "from_ac": item["ac_id"],
                "to_ac": representative["ac_id"],
                "dup_key": dup_key,
                "reason": "dup_key",
            }
        )

scanned_paths = [str(ROADMAP_PATH), str(EVIDENCE_ROOT), str(REPORTS_PATH), str(SSOT_RULES_PATH)]

# done_marked: DONE but not checked in roadmap

done_marked = []
for record in records:
    if record["status"] == "DONE" and not record["checked"]:
        done_marked.append(
            {
                "ac_id": record["ac_id"],
                "evidence": record["canonical"],
                "rule_hit": record["done_rule_hit"],
            }
        )

still_open = []
for record in records:
    if record["status"] == "OPEN":
        missing = []
        if record["canonical"] == "NONE":
            missing.append("missing canonical evidence")
        if not record["gate_ok"]:
            missing.append("missing gate evidence: " + ",".join(record["gate_missing"]))
        if record["notes"]:
            missing.append(record["notes"])
        still_open.append(
            {
                "ac_id": record["ac_id"],
                "title": record["title"],
                "missing_evidence_or_artifacts": "; ".join(missing),
            }
        )

suspicious = []
for record in records:
    if record["checked"] and record["status"] != "DONE":
        suspicious.append(
            {
                "ac_id": record["ac_id"],
                "title": record["title"],
                "issue": "ROADMAP checked but evidence missing",
            }
        )

for record in records:
    for path in record["evidence_paths"]:
        resolved = resolve_path(path)
        if resolved and not resolved.exists():
            suspicious.append(
                {
                    "ac_id": record["ac_id"],
                    "title": record["title"],
                    "issue": f"evidence path missing: {path}",
                }
            )

summary_counts = {
    "total": len(records),
    "done": sum(1 for record in records if record["status"] == "DONE"),
    "open": sum(1 for record in records if record["status"] == "OPEN"),
    "merged": sum(1 for record in records if record["status"] == "MERGED"),
}

report = {
    "scanned_paths": scanned_paths,
    "done_marked": done_marked,
    "merged": merged_entries,
    "still_open_top": still_open[:20],
    "suspicious": suspicious[:20],
    "summary_counts": summary_counts,
}

ledger_path = ROOT / "docs" / "v2" / "design" / "AC_LEDGER.md"
ledger_path.parent.mkdir(parents=True, exist_ok=True)

header_lines = [
    f"generated_at: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
    f"sources: {ROADMAP_PATH}, {EVIDENCE_ROOT}, {REPORTS_PATH}, {SSOT_RULES_PATH}",
    "rules: evidence-driven done (gate3 + artifacts), dup handling (evidence/title/intent)",
]

rows = []
for record in records:
    rows.append(
        [
            record["ac_id"],
            record["title"],
            record["stage"],
            record["status"],
            record["canonical"],
            record["done_rule_hit"],
            "UNKNOWN",
            record["dup_key"],
            record.get("merged_into", "—") if record.get("status") == "MERGED" else "—",
            record["notes"] or "—",
        ]
    )

rows.sort(
    key=lambda row: (
        STAGE_ORDER.index(row[2]) if row[2] in STAGE_ORDER else 99,
        row[0],
    )
)

with ledger_path.open("w", encoding="utf-8") as handle:
    handle.write("\n".join(header_lines) + "\n")
    handle.write("| AC_ID | TITLE | STAGE | STATUS | CANONICAL_EVIDENCE | DONE_RULE_HIT | LAST_COMMIT | DUP_GROUP_KEY | MERGED_INTO | NOTES |\n")
    handle.write("|---|---|---|---|---|---|---|---|---|---|\n")
    for row in rows:
        handle.write("| " + " | ".join(row) + " |\n")

report_path = ROOT / "logs" / "autopilot" / "roadmap_rebase_report.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"AC_LEDGER: {ledger_path}")
print(f"Rebase report: {report_path}")
