# Factory Analyze Report - SAFE::D_ALPHA-0::AC-1

- status: FAIL
- created_at_utc: 2026-02-20T17:08:17+00:00

## Command Results
- do_aider: exit_code=0, duration_sec=92.661, command=bash -lc aider --yes --model gpt-4.1 --message-file docs/plan/SAFE__D_ALPHA-0__AC-1.md && git add -A && (git diff --cached --quiet || git commit -m "factory: apply SAFE_D_ALPHA-0_AC-1")
- gate: exit_code=0, duration_sec=94.62, command=bash -lc make gate || (python3 scripts/run_gate_with_evidence.py doctor && python3 scripts/run_gate_with_evidence.py fast && python3 scripts/run_gate_with_evidence.py regression)
- docops: exit_code=1, duration_sec=0.258, command=bash -lc make docops || (python3 scripts/check_ssot_docs.py && python3 scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml && git status --short && git diff --stat)
- evidence_check: exit_code=0, duration_sec=0.03, command=bash -lc make evidence_check || python3 -c "from pathlib import Path; import sys; root=Path('logs/evidence'); required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); missing=[] if candidate else required; print('latest=%s' % candidate); print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)"
