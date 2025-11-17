# PHASE B MASTER – Paper 모드 안정화 & PnL 검증

## 1. PHASE B 목표 (Scope)

### 1.1 이 PHASE에서 달성해야 할 것

1. Paper 모드에서 다음이 **동시에** 성립해야 한다:
   - Signal OPEN/CLOSE가 콘솔에 명확하게 보이고
   - positions.csv / trades.csv / debug log에 포지션/체결이 기록되며
   - PnL 계산이 직관적으로 맞는다(수수료/슬리피지 제외한 값이라도).

2. 최소 1번 이상:
   - 실제 시세 상황에서 **포지션 OPEN → HOLD → CLOSE**까지 전 과정을 Paper로 검증
   - 이 과정을 “테스트 시나리오”로 문서에 기록

3. 코드 변경 범위 제한:
   - 이 PHASE에서는 **아래 파일만 수정 가능**:
     - `scripts/run_paper.py`
     - `arbitrage/executor.py`
     - `arbitrage/risk.py`
     - `arbitrage/storage.py`
   - collector/engine/config 구조는 건드리지 않는다 (다음 PHASE로 미룬다).

### 1.2 이 PHASE에서 절대 하지 않는 것

- 멀티 심볼(BTC 외 다른 심볼) 추가 X
- FX 구조 변경 X
- DB 도입 X
- Web UI / 대시보드 X
- Live 모드의 리스크/실거래 로직 확장 X  
  → **Paper 모드 안정화에만 집중**

---

## 2. 기능 요구사항 (Functional Requirements)

1. **포지션 생성/종료**
   - TradeSignal(action="OPEN") → PaperExecutor → Position 객체 생성
   - TradeSignal(action="CLOSE") → 기존 Position 닫기
   - 각 포지션에 대해:
     - entry_upbit_price / entry_binance_price
     - exit_upbit_price / exit_binance_price
     - entry_spread_pct / exit_spread_pct
     - pnl_krw / pnl_pct
     - status(CLOSED)

2. **로그 및 저장**
   - `logs/positions.csv`:
     - 각 포지션당 1행 이상
   - `logs/trades.csv`:
     - OPEN/CLOSE 각 체결당 1행 이상 (총 2N 행)
   - `logs/run_paper_debug.log`:
     - position_open / position_close 이벤트 로그

3. **리스크 체크**
   - `arbitrage/risk.py`:
     - can_open_new_position(...)이 정상동작
     - max_notional_krw, max_open_positions, 기타 안전장치 동작
   - 단, 이 PHASE에서는 리스크 모델을 “복잡하게 확장”하지 않고,  
     “작동만 제대로 하게” 맞춘다.

4. **디버그용 강제 진입 플래그 (옵션)**
   - `config/base.yml`에:
     ```yaml
     debug:
       force_first_entry: true
     ```
   - 이 값이 true일 경우:
     - 첫 기회에서 **한 번은 무조건 진입**하게 구현 가능 (테스트용)
   - 실제 운영 시에는 false로 유지.

---

## 3. 기술 제약 (Constraints)

- Python 버전: 3.14
- OS: Windows, PowerShell, cp949 콘솔 → 이모지 사용 금지
- 출력:
  - `[INFO]`, `[WARN]`, `[ERROR]`, `[OPEN]`, `[CLOSE]` 같은 ASCII 태그 사용
- 모듈 구조:
  - `arbitrage/` 이하의 모듈 분리는 유지
  - 함수/클래스 이름은 가능하면 변경하지 않는다 (다른 PHASE와 호환성 유지)

---

## 4. LLM/AI 작업 규칙 (이 PHASE 전용)

- AI에게 요청할 때 항상 명시:
  - “PHASE B MASTER 규칙을 벗어나지 말 것”
  - “아래 파일만 수정 가능: scripts/run_paper.py, arbitrage/executor.py, arbitrage/risk.py, arbitrage/storage.py”

- 금지 요청 예:
  - “프로젝트 전체 리팩토링 해줘”
  - “폴더 구조 개선해줘”
  - “모든 모듈 DRY하게 정리해줘”

- 허용 요청 예:
  - “arbitrage/executor.py에서 PaperExecutor.on_opportunity가 TradeSignal을 Position으로 잘 변환하는지 검토하고, 문제가 있으면 이 함수만 수정해줘.”
  - “scripts/run_paper.py에 테스트용 강제 진입 플래그를 추가하되, PHASE B MASTER에 정의된 범위 안에서만 수정해줘.”

---

## 5. 완료 조건 (Definition of Done)

이 PHASE를 끝났다고 선언하려면, 아래가 모두 만족해야 한다:

1. `python scripts/run_paper.py` 실행 시:
   - 최소 1번 이상:
     - `[OPEN]` 로그
     - `[CLOSE]` 로그
     - 포지션 요약 로그 출력

2. `logs/positions.csv`, `logs/trades.csv`, `logs/run_paper_debug.log`에:
   - 포지션/체결 이벤트가 실제로 기록된 샘플이 존재
   - 샘플 PnL이 수작업 계산과 큰 차이가 없음

3. 이 내용을 `docs/phase_B_master.md` 맨 아래에 “검증 로그 예시” 섹션으로 추가

```markdown
## 6. 검증 로그 예시 (실행 결과 캡처 요약)

- 2025-11-XX Paper 테스트 1회:
  - BTC 포지션 1건 OPEN/CLOSE
  - positions.csv 행 1개 추가 확인
  - trades.csv 행 2개 추가 확인
  - run_paper_debug.log에 position_open/close 로그 확인

---

## 4. ARB_DEV_RULES 템플릿 (AI/RULE 파일)

파일명: `docs/ARB_DEV_RULES.md`

```markdown
# ARB_DEV_RULES – Arbitrage Bot 개발 RULE

## 1. 공통 원칙

1. 이 Repo(`arbitrage-lite`)는 "아비트라지 봇 전용"이다.
   - 앙상블 봇, 다른 전략 코드, 실험용 스크립트는 이 Repo에 섞지 않는다.
2. 모든 변경은 **현재 활성 PHASE**와 **해당 PHASE master**에 맞춰 진행한다.
3. 한 번에 수정하는 범위는 **최소 단위(파일 단위 or 함수 단위)**로 제한한다.

---

## 2. LLM/AI 사용 RULE

### 2.1 절대 금지 프롬프트

아래와 같은 요청은 절대 하지 않는다:

- "프로젝트 전체 구조를 리팩토링해줘"
- "모든 코드 더 깔끔하게 정리해줘"
- "폴더 구조/모듈 구조를 다시 설계해줘"
- "이 Repo 전체를 DRY하게 개선해줘"

이런 요청은 기존 설계/Phase 분리를 깨고, 난개발을 유발한다.

### 2.2 권장 프롬프트 패턴

LLM/AI에게는 항상 다음 패턴으로 요청한다:

1. **현재 PHASE와 범위 명시**
   - "지금은 PHASE B이고, Paper 모드 안정화에만 집중한다."
2. **수정 가능한 파일 명시**
   - "이번 요청에서 수정 가능한 파일은 arbitrage/executor.py 하나뿐이다."
3. **수정 대상 함수/기능 명시**
   - "PaperExecutor.on_opportunity와 관련된 코드만 분석/수정해라."
4. **금지 사항 명시**
   - "collector/engine/config 구조는 변경하지 말 것."

예시:

> "현재 PHASE B이며, Paper 모드 안정화 중이다.  
> 이번 요청에서는 `arbitrage/executor.py` 내 `PaperExecutor.on_opportunity` 함수만 수정 가능하다.  
> 이 함수가 TradeSignal(action='OPEN'/'CLOSE')를 Position/로그로 제대로 반영하는지 분석하고, 문제가 있다면 이 함수 범위 안에서만 수정해라.  
> 다른 파일/모듈/구조는 절대 변경하지 마라."

---

## 3. 코드 변경 규칙

1. 기존 API/인터페이스(함수 시그니처, 클래스명)는 최대한 유지한다.
2. 새 기능을 추가해야 할 경우:
   - PHASE master 문서에 목적/범위/파일을 먼저 기록하고
   - 그 다음에 코드를 변경한다.
3. 로그 메시지는:
   - ASCII만 사용 (`[INFO]`, `[WARN]`, `[ERROR]`, `[OPEN]`, `[CLOSE]`)
   - 한국어/영어 혼용 가능하지만, cp949에서 깨지는 이모지는 금지.

---

## 4. 버전 관리

1. 각 PHASE가 완료될 때마다:
   - Git 태그: `arb-phase-A-done`, `arb-phase-B-done` 등으로 마킹
2. 크리티컬 변경 전에는:
   - 반드시 마지막 안정 태그에서 브랜치 생성 후 작업
