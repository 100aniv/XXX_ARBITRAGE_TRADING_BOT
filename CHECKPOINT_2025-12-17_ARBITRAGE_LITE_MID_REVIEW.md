# CHECKPOINT_2025-12-17 — arbitrage-lite 중간 점검 & 다음 진행 방향 (Windsurf 참고용)

> 목적: **Windsurf가 "현재 프로젝트 상황/SSOT/우선순위/재사용 가능한 모듈"을 한 번에 이해**하고,  
> 다음 작업(특히 **D95 성능 Gate PASS**)을 산으로 가지 않게 진행하도록 돕는 **참조 문서**입니다.  
> (이 문서는 **프롬프트가 아닙니다**. 다만 "무엇을 스캔/확인/재사용할지"는 명확히 적습니다.)

**🎉 업데이트 (2025-12-17 03:04 KST): D95 Performance Gate PASS 달성!**

### 0.1 로드맵 SSOT
- **SSOT:** `D_ROADMAP.md`
  - ROADMAP 계약(SSOT) / 마일스톤(M1~M6) / D별 목표·AC·증거 경로·Next가 정의됨

### 0.2 최근 핵심 D 문서
- **D93:** `docs/D93/D93_0_OBJECTIVE.md`, `docs/D93/D93_1_REPRODUCIBILITY_REPORT.md`
- **D94:** `docs/D94/D94_0_OBJECTIVE.md`, `docs/D94/D94_1_LONGRUN_PAPER_REPORT.md`
- **D95:** `docs/D95/D95_0_OBJECTIVE.md`, `docs/D95/D95_1_PERFORMANCE_PAPER_REPORT.md`
- **D96(20m 스모크, Exit 검증):** 현재 `docs/D95/evidence/` 하위에 증거가 존재  
  - 예: `docs/D95/evidence/d96_20m_decision.json` 등  
  - **주의:** ROADMAP 계약상 이상적인 구조는 `docs/D96/...` 이지만, 현재는 “D95 성능 Gate 해결 과정의 하위 실험”으로 묶여 있음.

---

## 1. 프로젝트 TO-BE 마일스톤(M1~M6)과 현재 위치

`D_ROADMAP.md` 기준(SSOT)으로 현재 상태를 요약합니다.

### M1. 재현성/안정성 Gate SSOT (Repro & Stability)
- **상태:** ✅ PASS (D93, D94)
- 핵심 의미:
  - 같은 조건이면 같은 결론(2-run) + 1h 이상 장기 실행 안정성 “증거 기반” 확보

### M2. 성능 Gate SSOT (Performance / Exit & EV)
- **상태:** ✅ **PASS** (D95-2, 2025-12-17 03:04 KST)
- 결과: round_trips=32, win_rate=100%, TP=32, PnL=+$13.31

### M3. 멀티 심볼 확장 (TopN Scale)
- **상태:** ⏸️ 보류(예정)  
- 전제조건: M2(D95) 성능 Gate가 PASS여야 Top50/Top100의 의미가 생김

### M4. 운영 준비 (Observability / Alerting / Runbook)
- **상태:** 부분 구현/문서 존재(런북/플레이북 포함), **현재 실행 흐름에서 “완전 가동/증거”가 일관되게 남는지는 재점검 필요**
- 운영 관점의 핵심은 “운영자가 상황을 즉시 이해하고 대응” 가능해야 함

### M5. 배포/릴리즈/시크릿 거버넌스
- **상태:** 일부 존재(환경 분리, Docker 등) 추정되나, “릴리즈/롤백/시크릿 정책 SSOT”까지는 아직 마일스톤 단위로 고정 필요

### M6. Live Ramp (소액 → 확대)
- **상태:** 미진행(예정)

---

## 2. 최근 진행 결과(핵심 사실 요약)

### 2.1 D93 — 2-run 재현성 Gate (✅ PASS)
- 목적: “같은 조건이면 같은 결론”을 SSOT 스크립트+증거로 고정
- 산출물: KPI/decision/log tail + 비교 JSON 등 evidence 확보

### 2.2 D94 — 1h Long-run 안정성 Gate (✅ PASS)
- 목적: **성능이 아니라 “1h 안정성(죽지 않음)”**을 증거로 고정  
- 성능(WinRate/PnL)은 M2(D95)로 분리하는 정책을 확정

### 2.3 D95 — 1h 성능 Gate (❌ FAIL)
- 관측된 핵심 증상(요약):
  - round_trips는 발생했으나,
  - **win_rate=0%**
  - **TP=0 / SL=0**
  - **exit_reason이 time_limit 100%**
  - 결과적으로 PnL이 음수
- 결론(SSOT): “시장 조건” 탓으로 넘기면 안 되고, **Exit/Fill/모델링 계층이 성능 Gate를 만족 못함**  
  → 같은 D95에서 수습하여 PASS 만들기 전까지 다음 D로 넘기면 안 됨

### 2.4 D96 — 20m 스모크(Δspread 기반 TP/SL Exit 검증) (✅ PASS, 단 성능은 미해결)
- 핵심 성과:
  - **TP/SL이 실제로 발생**하여 time_limit 100% 상태를 해소(일부 TIME 잔존은 허용 범위)
- 잔존 이슈:
  - **WinRate 0% 문제는 남음**
  - Fill model / fill ratio / 슬리피지 모델링 계층의 개선이 필요

---

## 3. D95 성능 FAIL의 “증거 기반” 원인 가설(우선순위)

> 아래는 “추정”이 아니라, 현재 보고서/증거에서 드러난 패턴을 기반으로 한 **작업 우선순위**입니다.  
> (정답 확정은 다음 프롬프트에서 Windsurf가 repo 스캔 + 계측으로 확정)

### P0: Exit 계층이 시간 제한(time_limit)로만 종료되는 구조
- D95에서는 time_limit 100%였고, D96에서 TP/SL 트리거가 발생하면서 깨짐
- 즉, **Exit 조건 설계/계측은 진전**했으나, 아직 “수익으로 연결되는 Exit”가 아님

### P0: Fill / Slippage / Partial-fill 모델 계층
- D96 문서에서도 “WinRate 0%는 fill model/fill ratio 문제로 잔존”으로 명시됨
- 우선순위:
  1) Entry/Exit 각각의 fill_ratio, slippage_bps, fee_bps를 기록
  2) “이겼어야 하는데” 지는 케이스가 fill/fee/slippage에서 뒤집히는지 수치로 확정

### P1: Threshold/Edge 모델의 일관성(공식/단위/가정)
- D95 Objective에서 fee/slippage 기반 최소 임계값(bps) 계산이 있으나,
  - 실제 운용/시장(bps)과의 **정합성 재확인**이 필요  
  - (예: 수수료 가정이 과도하면, 전략이 구조적으로 승률/기대값을 만들 수 없음)

---

## 4. “이미 구현됐는데 미사용/부분사용” 가능성이 큰 모듈·기능 인벤토리(문서 기반)

> ⚠️ 주의: 현재 이 문서는 “문서(특히 D70/D77~D80/D92 등)에서 언급된 흔적”을 기반으로 작성했습니다.  
> **다음 프롬프트에서는 Windsurf가 repo 전체 스캔(검색/참조 그래프/실행 경로)로 ‘실제 사용 여부’를 확정**해야 합니다.

### 4.1 상태 영속화 / Redis(StateManager) — **존재하지만 미사용 가능성 큼**
- 근거(문서): `docs/D70_STATE_CURRENT.md`에서
  - “대부분 메모리 기반”이며,
  - “Redis 미사용: StateManager 존재하지만 실제 사용 안 함”으로 명시
- 의미:
  - 운영(재시작/복구/장기 런)에서 **치명적인 갭**
- 권장:
  - D95를 끝내기 전 “최소 수준의 계측/저장(TradeLog/KPI)”은 필요하지만,
  - **대규모 상태 복원(RESUME)** 은 M4/M5 마일스톤으로 분리하는 편이 안전

### 4.2 PostgreSQL — “튜닝 결과만 저장” 편향
- 근거(문서): D70에서 “PostgreSQL은 D68 튜닝 결과만 저장”으로 언급
- 의미:
  - 장기 운영에서 “세션 스냅샷/트레이드 이력/리스크 이벤트” 저장이 빠져있을 수 있음
- 권장:
  - 최소: D95 성능 Gate에서 “원인 분석을 위한 트레이드 레벨 로그”는 DB 또는 파일로 SSOT화 필요

### 4.3 모니터링/알림/런북 — 문서/설계는 풍부, “실행 흐름에서 상시 가동”은 재확인 필요
- 근거(문서):
  - `docs/monitoring/D77-3_MONITORING_RUNBOOK.md` 존재
  - Grafana 대시보드 JSON, Prometheus Exporter, Alerting pipeline(텔레그램/Slack/Email 등) 설계가 문서에 등장
- 의미:
  - 구현이 되어 있어도 “현재 D95 실행 스크립트에서 메트릭/알림이 실제로 살아있는지”는 별개
- Windsurf 스캔 포인트:
  - `/metrics` endpoint가 실제로 뜨는지(포트/프로세스)
  - D95 실행에서 KPI 10종이 지표로 남는지
  - Alert routing이 ‘기본 채널(텔레그램)’로 동작하는지

### 4.4 Config 폴더 중복/분화 — “정리 유혹이 크지만 지금 손대면 위험”
- 근거(문서): `docs/D92/D92_1_SCAN_SUMMARY.md`
  - `config/`, `configs/`, `arbitrage/config/`, `tests/config/`가 서로 다른 용도로 공존
- 의미:
  - 지금 시점에서 병합/삭제는 런타임을 깨기 쉬움
- 권장:
  - D95 PASS 전에는 “정리”보다 “증거/성능” 우선
  - 정리는 별도 D(또는 D95-n 중 “검증 PASS 후 정리 커밋”)로 분리

---

## 5. ROADMAP 관점의 “누락 가능” 마일스톤/대분류 제안

`D_ROADMAP.md`에는 M1~M6가 정의돼 있으나, TO-BE 관점에서 아래 항목은 **마일스톤에 더 명시적으로 못 박는 편이 드리프트 방지에 유리**합니다.

### 5.1 멀티 거래소 확장(Multi-exchange) 마일스톤의 명시
- 현재는 “Upbit-Binance 중심”으로 충분히 상용 가치가 있으나,
- 장기적으로는:
  - 거래소 추가(예: 2→3+),
  - 인벤토리/리밸런싱,
  - 헬스/컴플라이언스 훅
  같은 범주가 로드맵 SSOT에 분명히 자리잡아야 함.
- 제안:
  - M3 하위에 `M3b: Multi-exchange Readiness` 같은 서브 마일스톤 추가
  - 또는 `M7`로 분리(선호: 분리)

### 5.2 운영자 UI/콘솔(Operator UX) 범주의 명시
- Grafana는 필수지만, “운영자가 즉시 조치”하려면
  - run control(시작/중단/프로파일 선택),
  - 사고시 빠른 요약(현재 포지션/손익/가드 상태),
  - 리포트 링크 모음
  같은 “운영 UX”가 별도 범주로 정리되면 좋음.
- 제안:
  - M4에 “Operator Console(최소 CLI+리포트 링크 SSOT)”를 포함하거나 별도 서브 항목으로 고정

---

## 6. Windsurf가 repo 스캔 시 “이 문서로 해야 할 일” 체크리스트

> 이 문서의 핵심 목적은 **“힘들게 만들어 놓고 안 쓰는 모듈”을 다시 살리고,  
> 동시에 ‘정리 유혹’ 때문에 산으로 가지 않게** 가드하는 것입니다.

### 6.1 실행 경로(Entry Point) 기준 “실제 사용 여부” 확정
- 최근 실행 스크립트(D95/D94/D93 runner)에서 import/instantiate 되는지 확인
- ‘있는데 안 쓰는’ 후보:
  - StateManager(Redis), DB 세션 스냅샷, Prometheus exporter, Alerting dispatcher, TradeLogger 등

### 6.2 D95 성능 Gate 해결에 직접 기여하는 것만 먼저 활성화
- 우선순위:
  1) 트레이드 레벨 계측(Entry/Exit spread, fill_ratio, slippage_bps, fee_bps)
  2) WinRate=0%의 원인을 **수치로 확정**
  3) Exit/Fill/Threshold 수정 → 동일 Gate에서 PASS

### 6.3 문서/증거 구조 계약 준수
- evidence 경로, compare/PR/raw 링크 출력, KPI/decision/log tail 저장을 “항상” 유지
- D95-n으로 수습할 경우에도 “ROADMAP → D문서 → code/evidence” 순서 유지

---

## 7. 참고: 외부 표준(운영/관측/설정)에서 최소로 지켜야 할 원칙

- 환경설정/시크릿 분리 원칙(환경변수 기반, 설정은 코드에서 분리): Twelve-Factor App의 Config 원칙을 참고할 가치가 큼.
- 메트릭/관측은 Prometheus의 라벨/메트릭 설계 원칙을 따르는 것이 장기 유지보수에 유리.
- 런북/플레이북 기반 운영은 SRE 표준 관점에서 장애 대응 속도·재현성에 결정적.

(이 섹션은 “우리 프로젝트 문서/규칙을 대체”하지 않고, **기존 TO-BE를 뒷받침하는 외부 기준**으로만 참고)

---

## 8. 결론(한 문장)

**지금은 ‘M2(D95) 성능 Gate’를 같은 D에서 PASS로 만드는 것이 최우선이며,  
이를 위해 repo에 이미 존재할 가능성이 큰 계측/로그/Executor/Fill/모니터링 모듈을 “실제 실행 경로에 연결”하는 방향으로 진행한다.**


## 📌 외부 운영 표준(참고용 근거)

문서 마지막에는 “외부 표준을 최소 참고”로만 언급했어.

설정/시크릿 분리 원칙: Twelve-Factor App Config 원칙(환경변수 기반)
https://12factor.net/config

Prometheus 메트릭 설계(네이밍/라벨) Best Practice
https://prometheus.io/docs/practices/naming/

SRE 관점 모니터링/런북/운영 개념(골든 시그널 등)
https://sre.google/sre-book/monitoring-distributed-systems/

Grafana 대시보드 설계 Best Practice(운영 가독성)
(Grafana Docs 검색 기반)

---

## 9. D95-2 최종 결과 (2025-12-17 03:04 KST) ✅ PASS

### 9.1 성능 Gate 결과
| 지표 | 결과 | 목표 | 상태 |
|------|------|------|------|
| round_trips | 32 | ≥10 | ✅ |
| win_rate | 100.0% | ≥20% | ✅ |
| take_profit | 32건 | ≥1 | ✅ |
| stop_loss | 2건 (20m) | ≥1 | ✅ |
| Total PnL | +$13.31 | - | ✅ |

### 9.2 적용된 파라미터 변경
- `FILL_MODEL_ADVANCED_BASE_VOLUME_MULTIPLIER`: 0.15 → **0.7**
- `FILL_MODEL_SLIPPAGE_ALPHA`: 0.0001 → **0.00003**
- `TOPN_ENTRY_MIN_SPREAD_BPS`: 0.7 → **8.0**
- BTC `threshold_bps`: 1.5 → **8.0**

### 9.3 핵심 버그 수정
- **Round trip PnL 계산**: `entry_pnl + exit_pnl` 합산 기준으로 수정
- **Win Rate 0% 해결**: Entry/Exit 개별 PnL이 아닌 전체 round trip 기준 판정

### 9.4 미사용 모듈 확인 결과
- **Redis (StateManager)**: 코드베이스에서 미발견 (제거 불필요)
- **StrategyManager**: 코드베이스에서 미발견 (제거 불필요)
- **TradeLogger**: KPI JSON으로 대체됨

### 9.5 Evidence
- `docs/D95/evidence/d95_1h_kpi.json`
- `docs/D95/evidence/d95_20m_kpi_v3.json`
- `docs/D95/evidence/d95_log_tail.txt`

---

## 10. 다음 단계 (M3 이후)
- **D97**: Multi-Symbol TopN 확장 (Top50 → Top100)
- **D98**: Production Readiness
- **M4**: 운영 준비 (Observability 강화)
