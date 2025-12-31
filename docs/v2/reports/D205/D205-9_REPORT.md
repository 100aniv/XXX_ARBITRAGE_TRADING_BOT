# D205-9: Realistic Paper Validation (20m→1h→3h) — 작업 보고서

**작업 ID:** D205-9  
**상태:** IN PROGRESS 🚧 (스크립트 준비 완료, 실행 대기)  
**작성일:** 2025-12-31  
**브랜치:** rescue/d99_15_fullreg_zero_fail

---

## 목표

현실적 KPI 기준으로 Paper 검증 (가짜 낙관 제거)

## 구현 완료 내용

### 1) Validation Script
- **스크립트:** `scripts/run_d205_9_paper_validation.py`
- **기능:** 20m/1h/3h 계단식 Paper 검증
- **AC 검증:** 자동 판정 로직 내장

### 2) AC (Acceptance Criteria) 정의

| Phase | Duration | AC 조건 |
|-------|----------|---------|
| smoke | 20m | closed_trades > 10, edge_after_cost > 0 |
| baseline | 1h | closed_trades > 30, winrate 50~80% |
| longrun | 3h | closed_trades > 100, PnL 안정 (std < mean) |

### 3) 가짜 낙관 방지
- **조건:** winrate 100% (closed_trades > 5일 때)
- **판정:** FAIL (모델이 현실 마찰을 반영하지 않음)

## 실행 방법

### 20m Smoke (필수)
```bash
python scripts/run_d205_9_paper_validation.py --duration 20 --phase smoke
```

### 1h Baseline (권장)
```bash
python scripts/run_d205_9_paper_validation.py --duration 60 --phase baseline
```

### 3h Long Run (선택)
```bash
python scripts/run_d205_9_paper_validation.py --duration 180 --phase longrun
```

## Evidence 구조

```
logs/evidence/d205_9_paper_{phase}_{timestamp}/
├── manifest.json    # git_sha, cmdline, config
├── kpi.json         # closed_trades, winrate, edge_after_cost
├── result.json      # AC 검증 결과
└── paper.log        # 실행 로그
```

## Prerequisites

### 환경 요구사항
- PostgreSQL (선택: `--db-mode optional`)
- 실시간 시장 데이터 연결 (Upbit, Binance)
- Python 환경 (`abt_bot_env`)

### 선행 D-step
- ✅ D205-5 (Record/Replay SSOT)
- ✅ D205-6 (ExecutionQuality v1)
- ✅ D205-7 (Parameter Sweep v1, 125 combinations)
- ✅ D205-8-1 (Quote Normalization)
- ✅ D205-8-2 (FX CLI + SSOT lockdown)

## AC 검증 현황

### 20m Smoke
- [ ] closed_trades > 10
- [ ] edge_after_cost > 0
- [ ] 가짜 낙관 체크 (winrate ≠ 100%)

### 1h Baseline
- [ ] closed_trades > 30
- [ ] winrate 50~80%
- [ ] 가짜 낙관 체크

### 3h Long Run
- [ ] closed_trades > 100
- [ ] PnL 안정성 (std < mean)
- [ ] 가짜 낙관 체크

## 의존성

- **Depends on:** D205-4~D205-8 (전체 Profit Loop)
- **Blocks:** D206 (운영/배포 단계)

## ⚠️ D206 진입 조건

- D205-9 PASS 전에는 D206(Grafana/Deploy) 진입 절대 금지
- "측정 → 튜닝 → 운영" 순서 강제

---

## 참고 자료

- SSOT: `docs/v2/SSOT_RULES.md`
- Paper Runner: `arbitrage/v2/harness/paper_runner.py`
- Architecture: `docs/v2/V2_ARCHITECTURE.md`
