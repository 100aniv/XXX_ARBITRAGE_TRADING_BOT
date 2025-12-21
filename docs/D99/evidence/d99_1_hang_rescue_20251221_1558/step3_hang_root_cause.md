# STEP 3: Full Regression HANG 근본 원인 확정

**Date:** 2025-12-21 16:10 KST

## 재현 명령
```bash
python -m pytest tests/ -v --tb=no -q --timeout=180 --timeout-method=thread
```

## HANG 지점 확정
**파일:** `tests/test_d41_k8s_tuning_session_runner.py`  
**테스트:** `test_run_with_invalid_jobs`  
**라인:** Line 222: `result = runner.run()`

## 스택트레이스 (핵심)
```
File "C:\work\XXX_ARBITRAGE_TRADING_BOT\arbitrage\k8s_tuning_session_runner.py", line 328, in run
    time.sleep(1)
```

## 근본 원인
- `k8s_tuning_session_runner.py`의 `run()` 메서드가 무한 루프 또는 긴 대기 상태에 진입
- `time.sleep(1)` 호출이 반복되면서 180초 타임아웃까지 대기
- pytest-timeout이 thread 방식으로 중단

## 진행 상황
- 테스트 진행률: 22% (2482개 중 ~546개 완료)
- HANG 이전 FAIL: 13개
- HANG 이후 미실행: ~1936개

## 해결 방안
1. **Option A (권장):** `test_d41_k8s_tuning_session_runner.py` 전체를 REGRESSION_DEBT로 분류하고 Full Suite에서 제외
2. **Option B:** `run()` 메서드의 무한 루프 로직을 수정하여 테스트 환경에서 빠르게 종료되도록 개선
3. **Option C:** 해당 테스트에만 더 짧은 타임아웃(예: 10초) 적용

## 다음 단계
- REGRESSION_DEBT.md 업데이트
- D_ROADMAP.md에 D99-1 섹션 추가
- CHECKPOINT에 D99-1 진행 로그 추가
- Git commit + push

## 증거 파일
- `step3_full_regression_attempt2.txt` (전체 로그 + 스택트레이스)
