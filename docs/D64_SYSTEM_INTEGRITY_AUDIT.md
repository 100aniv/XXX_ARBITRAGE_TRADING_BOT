# D64 SYSTEM_INTEGRITY_AUDIT – 전체 구조/기능 갭 점검

**작성일:** 2025-11-18 12:53  
**상태:** 🔍 진행 중  
**목적:** D_ROADMAP.md에 따라 현재 시스템의 실제 동작 여부를 점검하고 Gap Matrix 작성

---

## 🚨 CRITICAL FINDING: 이전 세션의 문제

### 문제 1: D 번호 오용
- **이전 세션:** "D64 Live Execution Integration"이라고 명명
- **실제 D_ROADMAP.md:** D64는 "SYSTEM_INTEGRITY_AUDIT"
- **결과:** MASTER_D_ROADMAP에 정의되지 않은 D 작업 수행
- **위반 규칙:** "MASTER_D_ROADMAP에 정의되지 않은 새로운 D를 즉흥으로 만들거나, D번호를 멋대로 점프하는 것 금지"

### 문제 2: "부분 완료" 선언
- **이전 세션:** "⚠️ 부분 완료 (구현 완료, 통합 테스트 미완성)"
- **실제 상태:** Exit/Winrate/PnL 모두 실패 (5/10 기준 충족)
- **위반 규칙:** "Acceptance 기준을 충족하지 못한 상태로 '완료/부분 완료'라고 선언하거나, 다음 D로 넘어가는 순간 이 프롬프트를 어기는 것"

### 문제 3: Critical 이슈를 다음 D로 미룸
- **이전 세션:** "D65에서 ArbitrageEngine의 Exit 로직 개선 필요"
- **실제 상태:** Exit 로직은 이미 구현되어 있음 (arbitrage_core.py Lines 198-232)
- **위반 규칙:** "'다음 D에서 해결하자' 식으로 미루는 Critical 버그는 허용 안 함"

---

## 📊 D_ROADMAP.md 기준 현재 위치

### 완료된 D 단계 (추정)
- D40~D63: 엔진/멀티심볼/가드/WS/롱런 인프라
- **현재:** D64 SYSTEM_INTEGRITY_AUDIT 수행 중

### D64의 실제 목표 (D_ROADMAP.md 기준)
```
🧩 D64 – SYSTEM_INTEGRITY_AUDIT (전체 구조/기능 갭 점검)
목표: 지금까지 만든 엔진/멀티심볼/가드/WS/롱런이
"문서 상 구현됨"이 아니라 "실제로 완전하게 동작하는지"를 시스템 관점에서 점검.

핵심 작업:
- PROJECT_VISION_TOBE, PHASE_MASTER_ROADMAP, D40~D63 FINAL_REPORT 정독
- "기능 리스트 vs 현재 구현 vs 실제 동작 여부" Gap Matrix 작성
- Exit/TP/SL 로직: ⚠ 코드 존재 / ❌ 실제로 트리거 안됨
- 테스트/캠페인 설계 문서 작성

검증 기준:
- D64_SYSTEM_AUDIT.md에 "현 시점의 구멍 리스트"가 정리되어 있어야 함
- 아직 문제 해결은 안 해도 됨
- 대신 "D65~D66에서 무조건 손볼 리스트"가 명확해야 함
```

---

## 🔍 Gap Matrix: 기능 리스트 vs 현재 구현 vs 실제 동작

### 1. 엔진 (ArbitrageEngine)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| Entry 신호 생성 | ✅ 구현 (Lines 103-186) | ✅ 동작 (299회 발생) | - |
| Exit 신호 생성 (스프레드 역전) | ✅ 구현 (Lines 198-232) | ❌ **트리거 안 됨** | **CRITICAL** |
| PnL 계산 | ✅ 구현 (Lines 72-91) | ❌ Exit 없어서 미실행 | **CRITICAL** |
| 최대 동시 거래 수 제한 | ✅ 구현 (Lines 168-169) | ✅ 동작 | - |
| 환율 정규화 | ✅ 구현 (Lines 135-138) | ✅ 동작 | - |

**Exit 로직 상세 분석:**
```python
# arbitrage_core.py Lines 198-232
if self.config.close_on_spread_reversal:
    for trade in self._open_trades:
        # 스프레드 계산
        if trade.side == "LONG_A_SHORT_B":
            current_spread = (bid_b_normalized - ask_a) / ask_a * 10_000.0
        else:
            current_spread = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0
        
        # 스프레드가 음수가 되면 종료
        if current_spread < 0:  # ← 이 조건이 절대 만족되지 않음
            trades_to_close.append(trade)
```

**근본 원인:**
- Paper 모드에서 스프레드가 항상 양수로 유지됨
- `_inject_paper_prices()` 로직이 Entry만 생성하도록 설계됨
- Exit를 트리거하려면 스프레드가 음수가 되어야 하는데, 이런 상황이 발생하지 않음

### 2. Executor (PaperExecutor / LiveExecutor)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| PaperExecutor | ✅ 구현 | ✅ 동작 | - |
| LiveExecutor | ✅ 구현 (이전 세션) | ⚠️ 미검증 | **D_ROADMAP 외 작업** |
| 거래 실행 | ✅ 구현 | ✅ 동작 (Entry만) | - |
| 포지션 관리 | ✅ 구현 | ⚠️ 부분 동작 (열림만) | **CRITICAL** |
| PnL 추적 | ✅ 구현 | ❌ Exit 없어서 미실행 | **CRITICAL** |

**LiveExecutor 관련:**
- D_ROADMAP.md에 정의되지 않은 작업
- 실제 필요한 작업은 D65 TRADE_LIFECYCLE_FIX에서 다뤄야 할 내용
- 현재 구현된 LiveExecutor는 보류하고, D65에서 재검토 필요

### 3. 멀티심볼 (MultiSymbolLongrunRunner)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| 멀티심볼 실행 | ✅ 구현 (D62) | ✅ 동작 | - |
| 심볼별 독립 상태 | ✅ 구현 | ✅ 동작 | - |
| 심볼별 PnL 추적 | ✅ 구현 | ❌ Exit 없어서 미실행 | **CRITICAL** |
| 심볼별 리스크 한도 | ✅ 구현 (D60) | ✅ 동작 | - |

### 4. 가드 (RiskGuard)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| 심볼별 리스크 한도 | ✅ 구현 | ✅ 동작 | - |
| 일일 손실 한도 | ✅ 구현 | ⚠️ 미검증 (Exit 없음) | **CRITICAL** |
| 포지션 수 제한 | ✅ 구현 | ✅ 동작 | - |
| 노출 한도 | ✅ 구현 | ✅ 동작 | - |

### 5. WS 최적화 (D63)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| WS 큐 | ✅ 구현 | ⚠️ 미검증 | 별도 검증 필요 |
| WS 메트릭 | ✅ 구현 | ⚠️ 미검증 | 별도 검증 필요 |
| REST 폴백 | ✅ 구현 | ✅ 동작 | - |

### 6. 롱런 인프라 (D62)

| 기능 | 구현 상태 | 실제 동작 | Gap |
|------|----------|----------|-----|
| 환경 초기화 | ✅ 구현 | ✅ 동작 | - |
| 멀티심볼 롱런 | ✅ 구현 | ✅ 동작 | - |
| 로그/메트릭 수집 | ✅ 구현 | ✅ 동작 | - |
| 결과 분석 | ✅ 구현 | ⚠️ 부분 동작 (Exit 없음) | **CRITICAL** |

---

## 🚨 CRITICAL 이슈 리스트

### Issue #1: Exit 신호가 트리거되지 않음 (최우선)

**증상:**
- Entry: 299회 발생 ✅
- Exit: 0회 발생 ❌
- Winrate: 0% (계산 불가) ❌
- PnL: $0.00 (변화 없음) ❌

**원인:**
```python
# arbitrage_core.py Line 220
if current_spread < 0:  # ← 이 조건이 절대 만족되지 않음
    trades_to_close.append(trade)
```

**Paper 모드 스프레드 주입 로직 분석 필요:**
```python
# arbitrage/live_runner.py Lines 550-599
def _inject_paper_prices(self) -> None:
    # 5초마다 스프레드를 주입하여 거래 신호 생성
    # 문제: Entry만 생성하도록 설계됨
    # Exit를 위한 스프레드 역전 시나리오 없음
```

**해결 방안 (D65에서 수행):**
1. Paper 모드 스프레드 주입 로직 개선
   - Entry 후 일정 시간 후 스프레드 역전 시나리오 추가
   - 또는 TP/SL 로직 추가
2. Exit 조건 완화
   - `current_spread < 0` → `current_spread < threshold` (예: -10 bps)
3. 시간 기반 Exit 추가
   - 일정 시간 후 자동 청산

### Issue #2: PnL 계산이 실행되지 않음

**증상:**
- PnL이 항상 $0.00
- 포지션이 닫히지 않아 PnL 계산 불가

**원인:**
- Issue #1과 동일 (Exit 없음)

**해결 방안:**
- Issue #1 해결 시 자동 해결됨

### Issue #3: Winrate 계산 불가

**증상:**
- Winrate: 0% (0/0)
- Exit가 없어 승률 계산 불가

**원인:**
- Issue #1과 동일 (Exit 없음)

**해결 방안:**
- Issue #1 해결 시 자동 해결됨

### Issue #4: LiveExecutor는 D_ROADMAP 외 작업

**증상:**
- 이전 세션에서 LiveExecutor 구현
- D_ROADMAP.md에 정의되지 않은 작업

**원인:**
- D 번호 오용
- MASTER_D_ROADMAP 미준수

**해결 방안:**
- LiveExecutor 코드는 보류
- D65 TRADE_LIFECYCLE_FIX에서 재검토
- 필요 시 별도 D 번호 할당 (예: D67.5)

---

## ⚠️ WARNING 이슈 리스트

### Warning #1: WS 최적화 미검증

**증상:**
- D63에서 WS 큐/메트릭 구현
- 실제 WS 모드 실행 미검증

**해결 방안:**
- D64에서 WS Paper 실행 및 검증
- WS 큐 지연/메트릭 확인

### Warning #2: 장시간 롱런 미검증

**증상:**
- 최대 15분 롱런만 수행
- 12H/24H 롱런 미검증

**해결 방안:**
- D64에서 6H 롱런 수행
- 메모리 leak/크래시 확인

---

## 📋 D65~D66에서 무조건 손볼 리스트

### D65 TRADE_LIFECYCLE_FIX (최우선)

**목표:**
- "진입은 하는데 엑싯이 없다, 승률이 없다" 같은 상태를 끝내고,
- 최소한 단일 심볼·Paper 모드에서 완전한 트레이드 라이프사이클이 돈다는 걸 보장.

**필수 작업:**
1. ✅ Paper 모드 스프레드 주입 로직 개선
   - Entry 후 Exit 시나리오 추가
   - 스프레드 역전 또는 TP/SL 트리거
2. ✅ Exit 조건 검증
   - `current_spread < 0` 조건 완화 또는 대체
3. ✅ PnL 계산 검증
   - Exit 후 PnL이 정상 계산되는지 확인
4. ✅ Winrate 계산 검증
   - 최소 N회 Entry/Exit 후 승률 계산

**Done 조건:**
- 최소 2~3개의 캠페인 결과에서:
  - Entry/Exit이 기대대로 발생
  - PnL/승률/슬리피지/수수료가 상식적으로 보임
- D65_FINAL_REPORT.md에:
  - 정상 동작 예시 로그/스냅샷/통계 캡처 포함

### D66 MULTISYMBOL_LIFECYCLE_FIX

**목표:**
- D65에서 단일 심볼 기준으로 확보한 "정상적인 트레이드 라이프사이클"을
- 멀티심볼(최소 BTC+ETH)에서도 동일하게 보장.

**필수 작업:**
1. ✅ 심볼별 Entry/Exit 독립성 확인
2. ✅ 심볼별 PnL 추적 검증
3. ✅ 포트폴리오 수준 PnL 합산 검증

---

## 📝 D64 Done 조건 (현재 단계)

D64는 **"문제 해결"이 아니라 "문제 점검"**이 목표입니다.

**Done 조건:**
- ✅ D64_SYSTEM_AUDIT.md에 "현 시점의 구멍 리스트" 정리
- ✅ "D65~D66에서 무조건 손볼 리스트" 명확화
- ✅ Critical 이슈 리스트 작성
- ❌ 문제 해결은 D65에서 수행

**현재 상태:**
- ✅ Gap Matrix 작성 완료
- ✅ Critical 이슈 4개 식별
- ✅ Warning 이슈 2개 식별
- ✅ D65~D66 작업 리스트 명확화

---

## 🎯 다음 단계

### 즉시 수행 (D64 완료)
1. ✅ 이 문서 작성 완료
2. ⏳ 테스트/캠페인 설계 문서 작성
3. ⏳ Git 정리 (이전 잘못된 커밋 수정)
4. ⏳ D64_FINAL_REPORT.md 작성

### D65에서 수행
1. Paper 모드 스프레드 주입 로직 개선
2. Exit 조건 검증 및 수정
3. PnL/Winrate 계산 검증
4. 단일 심볼 1H Paper 캠페인 실행
5. Entry/Exit/PnL/Winrate 정상 동작 확인

### D66에서 수행
1. 멀티심볼 Entry/Exit 독립성 확인
2. 심볼별 PnL 추적 검증
3. 멀티심볼 3H Paper 캠페인 실행

---

## 📊 요약

**D64 SYSTEM_INTEGRITY_AUDIT 결과:**
- ✅ 엔진/멀티심볼/가드/WS/롱런 인프라: 구현 완료
- ❌ **Exit/PnL/Winrate: 실제로 동작하지 않음 (CRITICAL)**
- ⚠️ WS 최적화/장시간 롱런: 미검증

**핵심 발견:**
- Exit 로직은 구현되어 있지만, Paper 모드에서 트리거되지 않음
- 근본 원인: 스프레드 주입 로직이 Entry만 생성하도록 설계됨
- 해결: D65에서 Paper 모드 개선 필요

**D64 상태:**
- ✅ "문제 점검" 목표 달성
- ✅ D65~D66 작업 리스트 명확화
- ✅ Critical 이슈 식별 완료

**다음 단계:**
- D64 완료 (테스트/캠페인 설계 문서 작성)
- D65 TRADE_LIFECYCLE_FIX 시작

---

**작성자:** Windsurf Cascade (AI)  
**검증:** Gap Matrix 기반 시스템 분석  
**상태:** 🔍 D64 진행 중 (문서 작성 단계)
