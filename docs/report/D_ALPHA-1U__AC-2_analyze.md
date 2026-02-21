# Factory Analyze Report - D_ALPHA-1U::AC-2

- status: FAIL
- created_at_utc: 2026-02-21T06:24:48+00:00

## Command Results
- do_aider: exit_code=1, duration_sec=8.11, command=bash -lc aider --yes --model gpt-4.1 --subtree-only --map-tokens 1024 --message-file docs/plan/D_ALPHA-1U__AC-2.md  && python3 scripts/git_safe_stage.py && (git diff --cached --quiet || git commit -m "factory: apply D_ALPHA-1U_AC-2")
- do_aider_retry: exit_code=1, duration_sec=17.629, command=bash -lc aider --yes --model gpt-4.1 --subtree-only --map-tokens 512 --message-file docs/plan/D_ALPHA-1U__AC-2.md  && python3 scripts/git_safe_stage.py && (git diff --cached --quiet || git commit -m "factory: apply D_ALPHA-1U_AC-2")
- gate: exit_code=1, duration_sec=3.008, command=bash -lc make gate || (python3 scripts/run_gate_with_evidence.py doctor && python3 scripts/run_gate_with_evidence.py fast && python3 scripts/run_gate_with_evidence.py regression)
- docops: exit_code=0, duration_sec=0.269, command=bash -lc make docops || (python3 scripts/check_ssot_docs.py && python3 scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml && git status --short && git diff --stat)
- evidence_check: exit_code=0, duration_sec=0.035, command=bash -lc make evidence_check || python3 -c "from pathlib import Path; import sys; root=Path('logs/evidence'); required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); missing=[] if candidate else required; print('latest=%s' % candidate); print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)"
