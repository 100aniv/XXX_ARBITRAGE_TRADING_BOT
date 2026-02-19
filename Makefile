PYTHON ?= python3

.PHONY: doctor fast regression gate docops evidence_check

doctor:
	@echo "[GATE 1/3] Doctor: Syntax + Import checks"
	$(PYTHON) scripts/run_gate_with_evidence.py doctor

fast:
	@echo "[GATE 2/3] Fast: Core tests (no ML/Live/API dependencies)"
	$(PYTHON) scripts/run_gate_with_evidence.py fast

regression:
	@echo "[GATE 3/3] Regression: Full suite (no live API)"
	$(PYTHON) scripts/run_gate_with_evidence.py regression

gate: doctor fast regression

docops:
	@echo "[DOCOPS] SSOT check + forbidden token scan"
	$(PYTHON) scripts/check_ssot_docs.py
	$(PYTHON) scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml
	git status --short
	git diff --stat

evidence_check:
	@echo "[EVIDENCE] Latest run minimum set check"
	$(PYTHON) -c "from pathlib import Path; import sys; root=Path('logs/evidence'); required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); missing=[] if candidate else required; print('latest=%s' % candidate); print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)"
