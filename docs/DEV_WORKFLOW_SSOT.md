# Dev Workflow: SSOT Gate 3단 + watchdog

**목적:** 명령 표준화 + 중간 멈춤 최소화 + 파일 변경 감지 자동 재실행

**최종 업데이트:** 2025-12-26 01:37 UTC+09:00

---

## 1. 빠른 시작

### 1.1 사전진단 (doctor)

```powershell
just doctor
```

**확인 사항:**
- Python 버전 (3.13.11)
- pytest import 가능 여부
- git status (커밋 상태)

### 1.2 Core Regression (fast / regression)

```powershell
just fast
# 또는
just regression
```

**실행 내용:**
- pytest.ini 기반 Core Regression
- 마커: `-m "not optional_ml and not optional_live"`
- 예상 시간: 3-5분
- 예상 결과: 2403 PASS, 39 FAIL (D99-12 P11 기준)

### 1.3 전체 테스트 (full)

```powershell
just full
```

**실행 내용:**
- 모든 테스트 (live_api, fx_api 포함)
- 예상 시간: 4-5분
- 예상 결과: 2403 PASS, 39 FAIL (D99-12 P11 기준)

---

## 2. Watchdog 모드 (파일 변경 감지 자동 재실행)

### 2.1 설치 (단발 실행)

**watchexec 설치 (winget 기반):**

```powershell
winget install --id watchexec.watchexec -e
```

**just 설치 (winget 기반):**

```powershell
winget install --id Casey.Just -e
```

**설치 확인:**

```powershell
just --version
watchexec --version
```

### 2.2 watchdog 실행

```powershell
.\scripts\watchdog.ps1 fast
# 또는
.\scripts\watchdog.ps1 regression
.\scripts\watchdog.ps1 full
```

**동작:**
- 파일 변경 감지 (확장자: py, md, toml, yml, yaml, json)
- 자동으로 `just <mode>` 재실행
- Ctrl+C로 종료

**무시 대상:**
- .git, .venv, __pycache__, .pytest_cache, logs, dist, build, node_modules, .mypy_cache, .ruff_cache

### 2.3 Watchdog 스모크 테스트

```powershell
# 터미널 1: watchdog 시작
.\scripts\watchdog.ps1 fast

# 터미널 2: 파일 변경 (예: docs/DEV_WORKFLOW_SSOT.md에 공백 추가)
# 파일 저장 후 watchexec가 자동으로 just fast 재실행하는지 확인

# 파일 원복 후 watchdog 종료 (Ctrl+C)
```

---

## 3. FAIL 대응 절차

### 3.1 FAIL 발생 시

```
FAILED tests/test_d37_arbitrage_mvp.py::test_example - AssertionError: ...
39 failed, 2403 passed, 31 skipped
```

### 3.2 즉시 수정 → 재실행

1. **원인 파악:** 로그에서 FAIL 테스트 확인
2. **코드 수정:** 해당 모듈/테스트 수정
3. **재실행:** `just regression` 또는 `just fast`
4. **PASS 증거:** 로그 저장 (logs/evidence/<timestamp>/)

### 3.3 증거 저장

```powershell
# 수동으로 증거 저장
just regression > logs/evidence/20251226_0137/regression.txt 2>&1
```

---

## 4. 타깃별 상세 정보

### 4.1 doctor (사전진단)

**실행 시간:** ~10초  
**설치/업데이트 금지:** 빠르고 안전해야 함  
**확인 항목:**
- Python 버전/경로
- pytest import 가능 여부
- git status

### 4.2 fast / regression

**실행 시간:** 3-5분  
**마커:** `-m "not optional_ml and not optional_live"`  
**근거:** pytest.ini (Core Regression SSOT)  
**예상 결과:** 2403 PASS, 39 FAIL (D99-12 P11)

**주의:** fast와 regression이 동일한 이유:
- 명시적 "fast gate" 정의 없음 (문서/CI 근거 부족)
- 안전하게 "항상 돌리던 Core Regression"으로 통일
- 필요 시 다음 PR에서 fast를 더 가볍게 분리 가능

### 4.3 full

**실행 시간:** 4-5분  
**마커:** 없음 (모든 테스트)  
**포함:** live_api, fx_api 테스트  
**예상 결과:** 2403 PASS, 39 FAIL (D99-12 P11)

---

## 5. 주의사항

### 5.1 watch 모드에서 금지 사항

❌ 패키지 설치 (pip install, poetry add 등)  
❌ 대화형 프롬프트 (Yes/No 입력)  
❌ 환경 변수 설정 (conda activate 등)  
✅ 테스트 실행만 (just fast/regression/full)

### 5.2 터미널 멈춤 방지

- watch 모드에서 대화형 명령 금지
- 멈춘 것처럼 보이면 Ctrl+C로 즉시 중단
- 해당 명령은 자동화 파이프라인에서 제외

### 5.3 full 실행 시기

- **개발 중:** regression만 사용 (빠름)
- **PR/merge 전:** full 실행 (모든 테스트 확인)
- **야간/릴리즈:** full 실행 (시간 충분할 때)

---

## 6. 문제 해결

### 6.1 "just: command not found"

```powershell
winget install --id Casey.Just -e
# 또는 PATH 재로드
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

### 6.2 "watchexec: command not found"

```powershell
winget install --id watchexec.watchexec -e
```

### 6.3 pytest hang (5분 이상 응답 없음)

```powershell
# 프로세스 강제 종료
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force

# pytest 캐시 정리
Remove-Item -Recurse -Force -Path ".pytest_cache"
Remove-Item -Recurse -Force -Path "tests\__pycache__"

# 재실행
just regression
```

### 6.4 watchdog 폭주 (연속 재실행)

- 임시 파일(.tmp, .swp) 생성 시 발생 가능
- scripts/watchdog.ps1의 ignore 패턴 확인
- 필요 시 추가 패턴 추가

---

## 7. SSOT 근거

| 항목 | 근거 파일 | 라인 | 내용 |
|------|----------|------|------|
| **Core Regression** | pytest.ini | 5-14 | 마커 정의 + 실행 명령 |
| **M1 Gate SSOT** | D_ROADMAP.md | 37-42 | D93/D94 재현성/안정성 |
| **M2 Gate SSOT** | D_ROADMAP.md | 44-48 | D95 성능 |
| **D99-12 P11** | CHECKPOINT | 56-74 | Full Regression 45→39 FAIL |

---

## 8. 다음 단계

1. **설치:** `winget install just watchexec`
2. **테스트:** `just doctor` → `just fast` → `just full`
3. **watchdog:** `.\scripts\watchdog.ps1 fast` (스모크 테스트)
4. **증거:** logs/evidence/<timestamp>/ 저장
5. **커밋:** git commit -m "dev: SSOT gate + watchdog workflow"

---

**작성자:** Cascade AI  
**상태:** ✅ COMPLETE
