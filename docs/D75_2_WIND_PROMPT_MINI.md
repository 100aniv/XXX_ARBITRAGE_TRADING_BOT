# D75-2 Core Optimization 실행 프롬프트 (간략 버전)

## 목표
- **build_snapshot()**: 20ms → 12ms (Phase 1 완료)
- **process_snapshot()**: 30ms → 17ms (Phase 2)
- **execute_trades()**: 10ms → 6ms (Phase 3)
- **Total Loop Latency**: 62ms → 25ms (Python 한계 고려)

## Acceptance Criteria

| 항목 | 목표 | 측정 방법 |
|------|------|-----------|
| build_snapshot avg | < 12ms | Micro-benchmark |
| process_snapshot avg | < 17ms | Micro-benchmark |
| execute_trades avg | < 6ms | Micro-benchmark |
| Loop latency avg | < 25ms | Integration test |
| Loop latency p99 | < 40ms | Integration test |
| Throughput | ≥ 40 iter/s | Integration test |
| CPU avg (Top10) | < 10% | Integration test |
| Memory avg (Top10) | < 60MB | Integration test |
| Runtime 오차 | ±2% | Integration test |
| Crash/Exception | 0 | Integration test |

## Phase 2: process_snapshot() 최적화

**병목 분석** (arbitrage/arbitrage_core.py):
- 환율 정규화 반복 계산 (bid_b_normalized, ask_b_normalized)
- 수수료/슬리피지 매번 합산 (total_cost_bps)
- len(self._open_trades) 반복 호출
- close_on_spread_reversal 루프에서 스프레드 재계산

**최적화 전략**:
1. 수수료/슬리피지 pre-calculation (__init__에서 self._total_cost_bps)
2. 환율 정규화 1회 계산 후 재사용
3. len() 호출 최소화
4. Early return 강화

**Micro-benchmark**: scripts/benchmark_d75_2_process_snapshot.py
- 300~500회 반복, avg/p50/p95/p99/min/max 출력
- PASS: avg < 17ms

## Phase 3: execute_trades() 최적화

**병목 분석** (arbitrage/live_runner.py):
- RiskGuard.check_trade_allowed() 빈도
- Order 객체 생성/GC
- logging 오버헤드

**최적화 전략**:
1. RiskGuard 호출 최소화 (symbol별 캐싱, 정책 허용 시)
2. 고빈도 logging 최적화 (레벨 체크, 샘플링)
3. Order Pool (효과 있을 때만)

**Micro-benchmark**: scripts/benchmark_d75_2_execute_trades.py
- PASS: avg < 6ms

## 통합 벤치마크

```bash
python scripts\run_d74_4_loadtest.py --top-n 10 --duration-minutes 1
```

**측정**:
- Throughput (iter/s)
- CPU avg/max (%)
- Memory avg/max (MB)
- Runtime (60s ±2%)
- Loop latency (1/throughput)

## 문서 업데이트

1. **docs/D75_2_CORE_OPTIMIZATION_REPORT.md**
   - Phase 2/3 Pre-Analysis
   - 최적화 내용
   - Micro/Integration 벤치마크 결과
   - Acceptance 테이블
   - Python 한계 분석

2. **D_ROADMAP.md**
   - D75-2 상태 업데이트 (COMPLETED / PARTIAL)
   - TO-BE 18개 항목 반영

## Git Commit

```bash
git add -A
git commit -m "[D75-2] Core Optimization Phase 2 & 3 완료

- process_snapshot() 최적화 (pre-calc, 캐싱, early return)
- execute_trades() 최적화 (RiskGuard, logging)
- Micro-benchmark 스크립트 추가
- Integration test 결과: [수치]
- Acceptance: [PASS/PARTIAL]"
```

## 중요 원칙

1. **기존 코드 패턴 재사용**: tests/에서 ArbitrageConfig/Engine 생성 패턴 검색
2. **의미론 보존**: 리스크/전략 결과값 동일 보장
3. **정량적 평가**: 수치 + 근거 기반 PASS/FAIL
4. **Python 한계 명시**: 목표 미달 시 사유 문서화
5. **회귀 테스트**: 기존 테스트 전부 통과 필수
