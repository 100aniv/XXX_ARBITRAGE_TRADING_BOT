# D97: Top50 1h Baseline Test

**Status**: 🔜 PENDING (D96 완료 후 진행)
**작성일**: 2025-12-18
**작성자**: Windsurf AI

---

## 1. 목표 (Objective)

D97은 Top50 확장의 **1h baseline test**로, 장기 안정성과 성능을 검증한다.

**핵심 목표**:
- Top50 환경에서 1시간 안정 운용
- 장기 실행 시 round trips, win rate, PnL 지속성 검증
- 레이트리밋/헬스 이벤트 모니터링

---

## 2. Acceptance Criteria (인수 조건)

### 안정성 (필수)
- [ ] duration ≥ 1h
- [ ] exit_code == 0
- [ ] 예외/크래시 0

### 거래 활동 (필수)
- [ ] round_trips ≥ 20
- [ ] win_rate ≥ 50%
- [ ] total_pnl ≥ 0
- [ ] KPI JSON 생성 + 파싱 OK

### 시스템 리소스 (모니터링)
- [ ] CPU < 50% (평균)
- [ ] Memory < 300MB
- [ ] Loop latency (avg) < 50ms

### 레이트리밋/헬스 (모니터링)
- [ ] 레이트리밋 이벤트 카운트
- [ ] 헬스 체크 실패 카운트
- [ ] Spread 분포 통계

---

## 3. 전제조건 (Dependencies)

- ✅ D95 성능 Gate PASS (2025-12-17 03:04 KST)
- ✅ D96 Top50 20m smoke PASS (2025-12-17 17:27 KST)
- ✅ Core Regression 44/44 PASS
- ✅ Fast Gate 5/5 PASS

---

## 4. Evidence 경로

```
docs/D97/evidence/
├── d97_top50_1h_kpi.json    # 1h baseline KPI
├── d97_log_tail.txt         # 로그 tail
├── preflight_20251218.txt   # Preflight check
└── spread_report.json       # Spread telemetry
```

---

## 5. 실행 명령어

```bash
# 1h baseline test (Top50)
$env:ARBITRAGE_ENV="paper"
python scripts/run_d77_0_topn_arbitrage_paper.py --universe top50 --duration-minutes 60 --kpi-output-path docs/D97/evidence/d97_top50_1h_kpi.json
```

---

## 6. D95/D96에서의 교훈 적용

1. **Round trip PnL 계산**: `entry_pnl + exit_pnl` 합산 기준 (검증 완료)
2. **Fill Model 파라미터**: `base_volume_multiplier=0.7` (적용 완료)
3. **Entry threshold**: `TOPN_ENTRY_MIN_SPREAD_BPS=8.0` (적용 완료)
4. **20m smoke test**: D96에서 안정성 검증 완료

---

## 7. 다음 단계

- **D98**: Production Readiness (Monitoring/Alerting/Runbook)
- **M7**: Multi-Exchange 확장
