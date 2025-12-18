# D96: Top50 확장 + 안정성 검증

**Status**: ✅ **COMPLETED** (2025-12-17)
**작성일**: 2025-12-17
**작성자**: Windsurf AI

---

## 1. 목표 (Objective)

D96은 TopN 확장의 첫 단계로, **Top50 20m smoke test**를 수행하여 확장 시 안정성을 검증한다.

**핵심 목표**:
- TopN 확장 (Top20 → Top50)
- 20분 smoke test로 초기 안정성 검증
- D95에서 검증된 PnL 계산 로직의 스케일 확장 검증

---

## 2. Acceptance Criteria (인수 조건)

### 안정성 (필수)
- [x] duration ≥ 20m (smoke)
- [x] exit_code == 0
- [x] 예외/크래시 0

### 거래 활동 (필수)
- [x] round_trips ≥ 5
- [x] KPI JSON 생성 + 파싱 OK

### 비용/임계값 (모니터링)
- [x] 손실 폭주 없음 (D95 교훈 적용)
- [x] 레이트리밋/헬스 이벤트 카운트

---

## 3. 전제조건 (Dependencies)

- ✅ D95 성능 Gate PASS (2025-12-17 03:04 KST)
- ✅ Core Regression 44/44 PASS
- ✅ Fast Gate 5/5 PASS

---

## 4. Evidence 경로

```
docs/D96/evidence/
├── d96_top50_20m_kpi.json   # 20m smoke KPI ✅
└── preflight_20251218.txt   # Preflight check
```

---

## 5. 실행 명령어

```bash
# 20m smoke test (Top50) - COMPLETED
python scripts/run_d77_0_topn_arbitrage_paper.py --universe top50 --duration-minutes 20 --kpi-output-path docs/D96/evidence/d96_top50_20m_kpi.json
```

---

## 6. D95에서의 교훈 적용

D95에서 발견된 문제들을 D96에서 방지:

1. **Round trip PnL 계산**: `entry_pnl + exit_pnl` 합산 기준 (이미 수정됨)
2. **Fill Model 파라미터**: `base_volume_multiplier=0.7` (이미 적용됨)
3. **Entry threshold**: `TOPN_ENTRY_MIN_SPREAD_BPS=8.0` (이미 적용됨)

---

## 7. 다음 단계

- **D97**: Top50 1h baseline test
- **D98**: Production Readiness
