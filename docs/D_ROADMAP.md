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

## D92-6: Production Deployment (PENDING)
- **Status**: ⏳ PENDING
- **Objective**: D92-4 결과 기반 프로덕션 배포
- **Dependencies**: D92-4 완료

---

## Summary
- **D92-1**: ✅ TopN 기반 페이퍼 트레이딩 SSOT 완성
- **D92-5**: ✅ 자동화 + 검증 완성
- **D92-4**: 🔄 진행 중 (threshold 스윕)
