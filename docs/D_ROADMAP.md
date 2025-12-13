# D92 ROADMAP

## D92-1: TopN Arbitrage Paper Baseline (COMPLETE)
- **Status**: ✅ COMPLETE
- **Completion Date**: 2025-12-13
- **Key Achievements**:
  - TopN Provider (Top20/Top50) 통합
  - Zone Profile 적용 (advisory/real mode)
  - Full Cycle Entry/Exit 검증
  - 10종 KPI 수집
  - 60분 장시간 실행 검증

## D92-2: Reserved
- **Status**: 🔄 RESERVED
- **Purpose**: Future enhancement

## D92-3: Reserved
- **Status**: 🔄 RESERVED
- **Purpose**: Future enhancement

## D92-4: Threshold Sweep & Optimization (IN PROGRESS)
- **Status**: 🔄 IN PROGRESS
- **Objective**: 최적 threshold 후보 선정 (5.0 / 4.8 / 4.5 bps)
- **Methodology**:
  - 10분 게이트 스윕 (3개 threshold)
  - 상위 1~2개 60분 베이스라인
  - Exit reason 분포 기반 분석
- **Expected Completion**: 2025-12-13

## D92-5: SSOT Consistency & Automation (COMPLETE)
- **Status**: ✅ COMPLETE
- **Completion Date**: 2025-12-13
- **Key Achievements**:
  - SSOT 경로 정합성 (logs/{stage_id}/{run_id}/)
  - stage_id 파이프라인 통합
  - 10분 스모크 자동화 + AC 자동 판정
  - Core Regression 100% PASS
  - 레거시 문자열 0개 (코드 경로)
  - GitHub push 성공 (대용량 파일 제거)

### D92-5 AC 검증 결과
```
AC-2: [PASS] - KPI/Telemetry/Trades가 logs/{stage_id}/{run_id}/ 아래에 생성
AC-3: [PASS] - run_id가 stage_id prefix 포함
AC-5: [PASS] - KPI에 total_pnl_krw/usd/fx_rate 존재
AC-5-ZoneProfiles: [PASS] - KPI에 zone_profiles_loaded (path/sha256/mtime) 존재
```

### D92-5 회귀 테스트
```
tests/test_d92_5_pnl_currency.py: 4/4 PASS
```

## D92-6: PnL 정산/Exit/Threshold Sweep 근본 수리 (COMPLETE)
- **Status**: ✅ COMPLETE
- **Completion Date**: 2025-12-14
- **Key Achievements**:
  - Per-leg PnL SSOT 확정 (체결 단가 기반)
  - Exit 로직 정상화 (TP/SL 검증 + exit_eval_counts)
  - Threshold Sweep 실제 적용 (--threshold-bps CLI)
  - 14/14 Fast Gate PASS + 4/4 Core Regression PASS

### D92-6 AC 검증 결과
```
AC-C (Per-Leg PnL SSOT):
  AC-C1: Per-leg PnL 함수 존재 ✅
  AC-C2: Unit test PnL 부호 검증 ✅
  AC-C3: KPI에 realized PnL/fees/fx_rate ✅

AC-D (Exit 로직 정상화):
  AC-D1: TP/SL 기본값 검증 ✅
  AC-D2: TP/SL/time_limit 각각 재현 ✅
  AC-D3: Runtime exit_eval_counts 집계 ✅

AC-E (Threshold Sweep 실제 적용):
  AC-E1: Threshold 런타임 메타 기록 ✅
  AC-E2: 리포트 "best threshold" 일치 ✅
```

## D92-7: 장시간 PAPER 성능 검증 (PENDING)
- **Status**: ⏳ PENDING
- **Objective**: D92-6 수정사항 기반 1시간 이상 PAPER 실행
- **Dependencies**: D92-6 완료

---

## Summary
- **D92-1**: ✅ TopN 기반 페이퍼 트레이딩 SSOT 완성
- **D92-5**: ✅ 자동화 + 검증 완성
- **D92-4**: ✅ Threshold 스윕 완료
- **D92-6**: ✅ PnL/Exit/Sweep 근본 수리 완료
