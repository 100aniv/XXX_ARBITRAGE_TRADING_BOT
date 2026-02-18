# Guard Fail-Fast Evidence (D000-3)

## 목적
- Welding/Engine-centric 가드가 실제로 FAIL-fast로 동작하는지 증명

## 테스트 시나리오
### Welding Guard (check_no_duplicate_pnl.py)
**위반 케이스:** 고의로 `calculate_net_pnl_full` 중복 구현 생성

**테스트 파일:** `logs/autopilot/_test_guard_violation.py`
```python
def calculate_net_pnl_full(trades):
    """Duplicate welding violation"""
    return sum(t.get("pnl", 0) for t in trades)
```

**실행 결과:**
```
python scripts/check_no_duplicate_pnl.py
[FAIL] Duplicate PnL/Friction implementation detected
 - logs\autopilot\_test_guard_violation.py :: duplicate_net_pnl_full
[HINT] Use arbitrage/v2/domain/pnl_calculator.py as the single welding source.
Exit Code: 1
```

**원복 후:**
```
python scripts/check_no_duplicate_pnl.py
[PASS] Single welding friction path enforced
Exit Code: 0
```

## Gate 강제 실행 확인
`scripts/run_gate_with_evidence.py`의 `preflight_checks` 섹션:
```python
preflight_checks = [
    (
        "check_no_duplicate_pnl",
        [sys.executable, "scripts/check_no_duplicate_pnl.py"],
    ),
    (
        "check_engine_centricity",
        [sys.executable, "scripts/check_engine_centricity.py"],
    ),
]
```

**결론:**
- Gate 실행 시 가드가 preflight로 자동 실행됨
- 가드 FAIL → Gate FAIL (ExitCode=1)
- 가드 PASS → Gate 계속 진행

## Engine-Centric Guard
`scripts/check_engine_centricity.py`는 다음을 검증:
1. `scripts/`, `arbitrage/v2/harness/` 얇은막 강제
2. 클래스 정의, 루프, 비즈니스 로직 금지
3. 역방향 import 금지 (core/domain → harness/scripts)

**HARNESS_NON_THIN_ALLOWLIST:**
- `arbitrage/v2/harness/paper_runner.py`
- `arbitrage/v2/harness/paper_chain.py`
- `arbitrage/v2/harness/smoke_runner.py`

위 3개 파일은 legacy로 인정, 나머지는 얇은막 강제.

## 증거 날짜
- 2026-02-18 18:08 UTC+09:00
