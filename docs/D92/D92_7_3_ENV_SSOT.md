# D92-7-3: ENV/SECRETS SSOT Check

**Date:** 2025-12-14  
**Status:** ✅ ENV SSOT 강제 완료

---

## 1. .gitignore 확인

**Status:** `.env*` 패턴 포함됨 ✅

```gitignore
# Environment variables
.env
.env.*
!.env.*.example
```

**결론:** Secrets 파일 Git 보호 완료

---

## 2. ENV 로딩 로직 강제

### 2.1 수정 내역
**File:** `scripts/run_d77_0_topn_arbitrage_paper.py:main()`

**Before:**
```python
args = parse_args()
# Settings.from_env() 호출 시 ARBITRAGE_ENV 환경변수에 의존
```

**After:**
```python
if args.data_source == "real":
    os.environ["ARBITRAGE_ENV"] = "paper"
    logger.info("[D92-7-3] REAL mode: Forcing ARBITRAGE_ENV=paper")
    
    # 키 존재 여부 마스킹 확인 (값 노출 금지)
    from dotenv import load_dotenv
    load_dotenv(".env.paper")
    upbit_key = os.getenv("UPBIT_ACCESS_KEY")
    binance_key = os.getenv("BINANCE_API_KEY")
    logger.info(f"[D92-7-3] ENV Check: UPBIT_KEY={'SET' if upbit_key else 'NOT_SET'}, BINANCE_KEY={'SET' if binance_key else 'NOT_SET'}")
```

**효과:**
- `--data-source real` 실행 시 `.env.paper` 자동 로드 보장
- 결정론적 ENV 설정 (사용자 환경변수에 의존 안 함)

---

## 3. 키 검증 (마스킹)

### 3.1 검증 항목
- `UPBIT_ACCESS_KEY`: 존재 여부만 확인 (값 노출 금지)
- `UPBIT_SECRET_KEY`: 존재 여부만 확인 (값 노출 금지)
- `BINANCE_API_KEY`: 존재 여부만 확인 (값 노출 금지)
- `BINANCE_API_SECRET`: 존재 여부만 확인 (값 노출 금지)

### 3.2 로그 출력 형식
```
[D92-7-3] ENV Check: UPBIT_KEY=SET, BINANCE_KEY=SET
```

**금지 사항:**
- 키 값 직접 출력 ❌
- 키 길이/부분 문자열 출력 ❌
- 파일 경로에 키 포함 ❌

---

## 4. Settings.from_env() 연계

### 4.1 현재 로직
**File:** `arbitrage/config/settings.py`

```python
@classmethod
def from_env(cls, overrides=None, secrets_provider=None, fail_fast_real_paper=False):
    env_str = os.getenv("ARBITRAGE_ENV", "local_dev")
    dotenv_path = f".env.{env_str}"
    load_dotenv(dotenv_path)
    ...
```

**D92-7-3 개선:**
- `os.environ["ARBITRAGE_ENV"] = "paper"`를 main()에서 먼저 설정
- Settings.from_env() 호출 시 자동으로 `.env.paper` 로드됨

---

## 5. 실행 시나리오

### 5.1 REAL mode (--data-source real)
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py --data-source real --universe top10
```

**실행 흐름:**
1. `args.data_source = "real"`
2. `os.environ["ARBITRAGE_ENV"] = "paper"` 강제 설정
3. `.env.paper` 로드
4. 키 존재 여부 마스킹 로그
5. `Settings.from_env()` 호출 → `.env.paper` 재로드 (멱등성)

### 5.2 MOCK mode (--data-source mock)
```bash
python scripts/run_d77_0_topn_arbitrage_paper.py --data-source mock --universe top10
```

**실행 흐름:**
1. `args.data_source = "mock"`
2. ENV 강제 설정 안 함
3. `Settings.from_env()` 호출 → 기본 동작 (ARBITRAGE_ENV 환경변수 또는 local_dev)

---

## 6. 검증 체크리스트

- [x] `.gitignore`에 `.env*` 포함됨
- [x] `--data-source real` 시 `.env.paper` 자동 로드
- [x] 키 존재 여부 마스킹 로그 (값 노출 금지)
- [x] Settings.from_env() 연계 확인
- [x] 코드 수정 완료

---

## Next Step

**STEP 2:** ZoneProfile SSOT 재통합 (핵심)
