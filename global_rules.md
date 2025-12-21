# global_rules.md — MR WHITE SSOT Engineering Rules (Global)

- Always follow: Plan → Implement → Test/Monitor → Auto-debug → Re-run → Docs/ROADMAP → Git Commit → Push
- No skipping. No “optional” defers. Done only when tests are 100% PASS and docs are synced.
- Prefer reuse over refactor. Scan repo first. Avoid duplication/over-engineering.
- If command produces no output and log doesn’t change for 120s → treat as HANG → stop, diagnose, fix, rerun.
- Korean-first output (English only for necessary technical terms).
- Always end with: test numbers + evidence path + commit hash + compare/PR URL + raw links for big files.
