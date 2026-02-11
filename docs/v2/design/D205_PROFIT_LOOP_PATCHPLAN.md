# D205 Profit Loop Patchplan - 로드맵 재구조화

**작성일:** 2025-12-31  
**목적:** V2 로드맵(D200~D206)의 "Engineering vs Profit" 불균형 해소
**근거:** GPT + Gemini 교차 분석 결과

---

## 🚨 현재 문제 요약

### 핵심 진단
현재 D200~D206 로드맵은 **"안죽는 시스템(Engineering)"에 과도하게 치우쳐 있고, "돈 버는 시스템(Quant/Trading)" 단계가 구조적으로 비어있다.**

### 구체적 Gap (상용급 기준)

1. **"눈"만 생기고 "뇌"가 없다**
   - D205-3까지의 흐름: 리포팅/측정(눈)만 구축
   - 누락: 그 눈으로 보고 로직/파라미터를 고치는 튜닝 루프(뇌)

2. **실행 성능/체결 품질(Execution Quality) 단계 없음**
   - 누락 지표:
     - latency p50/p95 (Tick→Decision→Fill)
     - slippage_bps, fill_rate/partial/timeout/cancel
     - reject/error/rate_limit_hit(429)/reconnect_count
     - **edge_after_cost 분포** (승률보다 중요)

3. **백테스트/리플레이(Record→Replay) 게이트 없음**
   - 실시간 paper만으로는 튜닝 너무 느림, 재현성 없음
   - NDJSON 기록 + 리플레이 실행 필수

4. **운영자 제어(Admin/Control) 최소요건 없음**
   - Grafana는 "모니터링"이지 "제어" 아님
   - 필수 제어 기능:
     - 즉시 Stop/Pause
     - 심볼 블랙리스트
     - 강제 청산(paper: 포지션 플랫/상태 초기화)
     - 위험 임계치 조정(노출, 최대 동시 포지션)

### 경고: 가짜 낙관 신호
- 현재 KPI: "승률 100%, PnL 엄청 큼"
- 이는 **현실 마찰(수수료/슬리피지/부분체결/지연/429/취소/재호가/호가두께)이 제대로 먹지 않은 상태**
- 100% 승률 = "천재" 아니라 **"모델이 현실을 안 먹었다"** 신호

---

## 📋 추가/재배치할 D-step 목록

### D205-4~9 신설 (Profit Loop/Optimization 블록)

#### D205-4: Reality Wiring (실데이터 루프 완성)
- **목표:** 실 MarketData → detector → decision → paper execution(가정 체결)
- **산출물:** 기회 발생률, edge 분포, latency 기초
- **AC:**
  - MarketData Provider 실데이터 연결
  - Detector → Engine → Paper Executor 플로우 완성
  - latency p95 < 100ms (기준선)
  - 기회 발생률 측정 (per symbol/per minute)

#### D205-5: Record/Replay SSOT (NDJSON 기록+리플레이 재현)
- **목표:** 기록 포맷 SSOT, 동일 입력→동일 결정 재현(회귀 테스트)
- **산출물:** 
  - `logs/replay/<date>/market.ndjson` (시장 데이터)
  - `logs/replay/<date>/decisions.ndjson` (결정 로그)
  - 리플레이 엔진 (동일 입력 → 동일 결과 검증)
- **AC:**
  - NDJSON 포맷 SSOT 정의
  - 동일 market.ndjson 입력 시 동일 decisions.ndjson 출력
  - 회귀 테스트 자동화 (replay → diff → PASS/FAIL)

#### D205-6: ExecutionQuality v1 (슬리피지/부분체결/타임아웃 모델+지표화)
- **목표:** 승률이 아니라 **edge_after_cost** 중심 KPI 전환
- **산출물:**
  - ExecutionQuality 메트릭 SSOT
  - slippage_bps, partial_fill_rate, timeout_rate, api_error_rate
  - edge_after_cost 분포 (히스토그램)
- **AC:**
  - slippage_bps 측정 (가정값 → 실제 체결가 차이)
  - partial fill/timeout/cancel 비율 측정
  - edge_after_cost > 0 비율 (진짜 수익성 지표)
  - **가짜 낙관 방지:** winrate 100%면 오히려 FAIL 경고

#### D205-7: Parameter Sweep v1 (Random/Grid 튜닝 초석)
- **목표:** threshold/buffer/cooldown/필터 조합 탐색
- **산출물:**
  - 리플레이 기반 Parameter Sweep 프레임워크
  - Random/Grid Search 기초 구현
  - 후보 압축 → paper 계단식 검증
- **AC:**
  - 최소 3개 파라미터 sweep (threshold, buffer, cooldown)
  - 리플레이로 100+ 조합 고속 테스트
  - Top-5 후보 → paper 1시간 검증
  - Pareto frontier 시각화

#### D205-8: TopN + Route/Stress (Top10→50→100 확장)
- **목표:** 진짜 확장 시 rate limit/지연/큐 적체 생존 검증
- **산출물:**
  - Top10 → Top50 → Top100 확장 시나리오
  - rate_limit_hit, queue_depth, latency_p95 트렌드
- **AC:**
  - Top10: latency p95 < 100ms, rate_limit_hit = 0
  - Top50: latency p95 < 200ms, rate_limit_hit < 5/hr
  - Top100: latency p95 < 500ms, rate_limit_hit < 20/hr
  - 적체 시 자동 throttling 동작

#### D205-9: Realistic Paper Validation (20m→1h→3h)
- **목표:** 현실적 KPI 기준으로 검증 (가짜 낙관 제거)
- **산출물:**
  - 20m/1h/3h paper 실행 증거
  - **현실적 KPI 판정 기준:** winrate < 90%, edge_after_cost > 0
- **AC:**
  - 20m: closed_trades > 10, edge_after_cost > 0
  - 1h: closed_trades > 30, winrate 50~80% (현실적 범위)
  - 3h: closed_trades > 100, PnL 안정성 (std < mean)
  - **가짜 낙관 FAIL:** winrate 100% → 모델 현실 미반영으로 FAIL 처리

---

### D206 재정의 (조건부 진입, 순서 뒤로 밀림)

#### 조건: D205-9 PASS 전에는 D206 진입 금지

#### D206-1: Grafana (튜닝/운영 용도로만)
- **목표:** D205-4~9 지표를 패널로 보여주기
- **금지:** 핵심 로직 검증 전 Grafana 먼저 → 절대 금지
- **AC:**
  - edge_after_cost, latency p95, slippage_bps 패널
  - parameter sweep 결과 시각화
  - Admin Control 최소 UI (Stop/Pause/Blacklist)

#### D206-2: Docker Compose SSOT (패키징)
- **목표:** 운영 포장(컨테이너)은 "돈 버는 로직" 검증 후
- **AC:**
  - V2 전용 docker-compose.v2.yml
  - health check (DB/Redis/Engine)
  - 1-command deploy (docker-compose up)

#### D206-3: Failure Injection/Runbook
- **목표:** 장애 주입 + 대응 절차
- **시나리오:**
  - 429 rate limit
  - WS disconnect/reconnect
  - DB 지연/timeout
  - Redis flush
- **AC:**
  - 각 시나리오별 Runbook 작성
  - Failure Injection 테스트 자동화
  - 복구 시간 < 30초

#### D206-4: Admin Control Panel (최소 제어)
- **목표:** 웹 UI든 텔레그램이든 최소 제어 기능
- **필수 기능:**
  - Start/Stop/Pause
  - Symbol blacklist (즉시 반영)
  - Emergency flatten (paper: 포지션 초기화)
  - Risk limit override (노출/동시포지션)
- **AC:**
  - Stop 명령 → 5초 내 전체 중단
  - Blacklist 추가 → 즉시 해당 심볼 거래 중단
  - Emergency flatten → 10초 내 모든 포지션 청산

### K8s: DEFER (지금은 보류)
- **이유:** k8s는 "상용급"이 아니라 "상용급처럼 보이는 장식"이 되기 쉬움
- **조건:** LIVE ramp 실제 운영 요구 발생 시에만 진행

---

## 📂 수정할 문서 파일 목록

### 1. D_ROADMAP.md (최우선)
**위치:** `D_ROADMAP.md`

**수정 내용:**
- D205-3 다음에 D205-4~9 신설 섹션 추가
- D206 조건부 진입 명시 ("D205-9 PASS 전에는 진입 금지")
- 각 D-step에 목표/AC/증거 요구사항/PASS 판단 기준 포함
- "가짜 낙관 방지" 규칙 명시 (winrate 100% → FAIL 경고)

### 2. SSOT_RULES.md
**위치:** `docs/v2/SSOT_RULES.md`

**추가 내용:**
- "Grafana/Deploy/K8s는 Profit Loop 블록(D205-4~9) 통과 후" 규칙 명문화
- "측정(Reporting) → 튜닝(Optimization) → 운영(Ops)" 순서 강제
- "Record/Replay 없으면 튜닝/회귀 불가" 규칙 추가

### 3. SSOT_MAP.md
**위치:** `docs/v2/design/SSOT_MAP.md`

**추가 도메인 SSOT:**
- Record/Replay SSOT (logs/replay/ 규칙)
- ExecutionQuality Metrics SSOT (slippage, partial, timeout 정의)
- Tuning Pipeline SSOT (parameter sweep 포맷)
- Admin Control SSOT (운영 제어 인터페이스)

### 4. V2_ARCHITECTURE.md
**위치:** `docs/v2/V2_ARCHITECTURE.md`

**추가 섹션:**
- Profit Loop 플로우:
  ```
  MarketData → Detector → Decision → (Paper Exec Model) 
  → Ledger → KPI → Tuning Feedback → Parameter Update
  ```
- V1 자산 재사용 원칙 재강조 (복사 금지, import/reuse 우선)

### 5. EVIDENCE_FORMAT.md
**위치:** `docs/v2/design/EVIDENCE_FORMAT.md`

**추가 필드:**
- `edge_after_cost` (float)
- `slippage_bps` (float)
- `partial_fill_rate` (float)
- `replay_input_hash` (str, 리플레이 입력 무결성 검증)

### 6. REPORT_TEMPLATE.md
**위치:** `docs/v2/templates/REPORT_TEMPLATE.md`

**추가 섹션:**
- edge_after_cost 분포
- latency p50/p95
- rate_limit_hits / api_errors
- slippage/partial/timeout 요약
- 튜닝 후보 파라미터/결정 근거

---

## 🔍 용어/정의 충돌 포인트

### 1. "Phase" 용어 사용
**현황:**
- SSOT_RULES.md: 176~190 라인 "Phase 0/1/2" 표기
- V2_ARCHITECTURE.md: 367~384 라인 "Phase 0/1/2/3" 표기

**조치:**
- 모든 "Phase" → D 번호 기반 표현으로 변경
- 예: "Phase 1: 점진적 전환" → "D201~D204: V1→V2 점진적 전환"

### 2. "측정 vs 튜닝" 순서 불명확
**현황:**
- D205-3까지: 측정/리포팅 중심
- D206: 바로 Grafana/Deploy로 점프 (튜닝 단계 없음)

**조치:**
- "측정 → 튜닝 → 운영" 순서를 SSOT_RULES.md에 명문화
- D205-4~9를 "튜닝/최적화" 필수 블록으로 삽입

### 3. "Gate PASS" 정의 모호성
**현황:**
- 현재: Gate 0 FAIL만 요구
- 누락: 실행 품질 지표 (latency, edge_after_cost)

**조치:**
- D205-4 이후부터는 Gate 3단 + ExecutionQuality 지표 모두 PASS 필수
- PASS 기준에 "가짜 낙관 방지" 조건 추가

### 4. "DONE" 선언 기준 불일치
**현황:**
- D205-3: "KPI 필드 추가 = DONE"
- 실제: KPI 필드 있어도 **현실성 검증 없으면 DONE 아님**

**조치:**
- D205-3 DONE 조건 재정의:
  - "KPI 스키마 확립" = DONE (맞음)
  - "수익성 검증 완료" = 아님 (명시)
- D205-9 통과 전까지는 "Profit Loop INCOMPLETE" 상태

---

## 🎯 다음 단계 (Step 1: D_ROADMAP.md 수정)

### 신설 섹션 위치
- D205-3 (현재 라인 2883~2931) 다음
- D206 (현재 없음, 신설 필요)

### 템플릿 (각 D-step 공통 구조)

```markdown
#### D205-X: [제목]
**상태:** PLANNED ⏳
**커밋:** [pending]
**테스트:** [pending]
**문서:** `docs/v2/reports/D205/D205-X_REPORT.md`
**Evidence:** `logs/evidence/d205_x_<timestamp>/`

**목표:**
- [1줄 요약]

**범위 (Do/Don't):**
- ✅ Do: [구체적 작업]
- ❌ Don't: [금지 사항]

**AC (증거 기반 검증):**
- [ ] [정량 기준 포함 AC]
- [ ] [정량 기준 포함 AC]

**Evidence 요구사항:**
- manifest.json
- kpi.json (edge_after_cost, latency_p95 포함)
- errors.ndjson (있으면)
- market.ndjson (D205-5부터)

**Gate 조건:**
- Gate Doctor/Fast/Regression: 0 FAIL
- ExecutionQuality: [구체적 기준]

**PASS/FAIL 판단 기준:**
- PASS: [정량 기준]
- FAIL: [가짜 낙관 방지 조건 포함]

**의존성:**
- Depends on: D205-X (이전 단계)
- Blocks: D205-X+1 (다음 단계)
```

---

## 📊 정합성 체크 (문서 관점)

### 체크리스트
- [ ] D_ROADMAP.md: D205-4~9 섹션 추가
- [ ] D_ROADMAP.md: D206 조건부 진입 명시
- [ ] D_ROADMAP.md: "Phase" 용어 전부 제거
- [ ] D_ROADMAP.md: D205-3 경고 추가 ("측정 도구 확립이지 수익성 검증 아님")
- [ ] SSOT_RULES.md: Profit Loop 순서 강제 규칙 추가
- [ ] SSOT_RULES.md: "Phase" 용어 제거
- [ ] SSOT_MAP.md: 신규 SSOT 4개 추가 (Replay/ExecQuality/Tuning/AdminControl)
- [ ] V2_ARCHITECTURE.md: Profit Loop 플로우 다이어그램 추가
- [ ] V2_ARCHITECTURE.md: "Phase" 용어 제거
- [ ] EVIDENCE_FORMAT.md: edge_after_cost 등 필드 추가
- [ ] REPORT_TEMPLATE.md: ExecutionQuality 섹션 추가

---

## 🚀 실행 계획

### Step 1: D_ROADMAP.md 수정 (최우선)
1. D205-4~9 섹션 신설 (각 템플릿 적용)
2. D206 조건부 진입 섹션 추가
3. "Phase" 용어 전부 제거
4. D205-3에 경고 추가

### Step 2: SSOT 문서 동기화
1. SSOT_RULES.md 업데이트
2. SSOT_MAP.md 신규 SSOT 추가
3. V2_ARCHITECTURE.md Profit Loop 플로우 추가
4. EVIDENCE_FORMAT.md 필드 추가
5. REPORT_TEMPLATE.md 섹션 추가

### Step 3: 정합성 체크
1. "Phase" 용어 grep 검색 → 0개 확인
2. D_ROADMAP ↔ SSOT_RULES ↔ SSOT_MAP 정의 충돌 확인
3. 모든 D-step AC에 정량 기준 포함 확인

### Step 4: Gate 3단 + 커밋
1. just doctor/fast/regression (0 FAIL)
2. git add -A
3. git commit -m "[D_ROADMAP][SSOT] Profit Loop(D205-4~9) 삽입, Grafana/Deploy 조건부 재배치"
4. git push

---

## 📝 결론

**현재 상태:** "튼튼한 깡통" 로드맵 (안죽지만 돈 못 버는 구조)  
**목표 상태:** "Profit Loop 통과 후 운영" 로드맵 (튜닝→검증→배포)  
**핵심 변경:** D205-4~9 신설, D206 조건부 진입, "Phase" 제거, 가짜 낙관 방지 규칙

**다음 턴 (코드 작업):** D205-4 Reality Wiring 구현 (이번 턴은 문서만)
