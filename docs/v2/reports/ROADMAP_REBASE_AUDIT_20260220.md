# ROADMAP REBASE AUDIT REPORT

**Date:** 2026-02-20
**Branch:** feature/v2-factory-hard-reset
**Model:** Windsurf Cascade (최상급 Reasoning)
**Mission:** SSOT Roadmap Slim Index + V2-Only Rail Reconstruction (NO DESTRUCTIVE LOSS)

---

## 1. 변경/생성 파일 리스트

| 파일 | 동작 | 설명 |
|---|---|---|
| docs/archive/ROADMAP_LEGACY_FULL_20260220.md | CREATE (복사) | D_ROADMAP.md 전체 7962줄 동결 보존 |
| docs/archive/AC_LEDGER_BACKUP_20260220.md | CREATE (복사) | AC_LEDGER.md 전체 394줄 동결 보존 |
| docs/v2/ROADMAP_V2.md | CREATE | V2-only 운영 레일 (D200+/D_ALPHA, Alpha 최우선) |
| D_ROADMAP.md | REWRITE | 7962줄 -> 233줄 Slim SSOT Index |
| docs/v2/design/AC_LEDGER.md | REWRITE | 394줄 -> 200줄 V2-only 순차 큐 |
| docs/v2/reports/ROADMAP_REBASE_AUDIT_20260220.md | CREATE | 이 리포트 |

---

## 2. 격리 대상 목록 (Non-Destructive Cleanup Plan)

### 카테고리 A: 레거시 테스트 파일 (D200 미만, 185개)

**정책:** 수정 금지. 게이트 방해 시 docs/archive/legacy_tests/ 로 물리 이동.
**현재 상태:** tests/ 루트에 잔존. D208-SLIM-2 단계에서 일괄 이동 예정.

대표 파일 (185개 중 상위 40개):
- tests/test_d10_alert.py
- tests/test_d10_live_guard.py
- tests/test_d11_logging.py
- tests/test_d11_sys_monitor.py
- tests/test_d11_watchdog.py
- tests/test_d12_stress.py
- tests/test_d13_env_loader.py
- tests/test_d13_risk_model.py
- tests/test_d14_position_adv.py
- tests/test_d15_portfolio.py
- tests/test_d15_risk_quant.py
- tests/test_d15_volatility.py
- tests/test_d16_safety.py
- tests/test_d16_state_manager.py
- tests/test_d16_types.py
- tests/test_d17_paper_engine.py
- tests/test_d17_simulated_exchange.py
- tests/test_d19_live_mode.py
- tests/test_d21_state_manager_redis.py
- tests/test_d23_advanced_tuning.py
- tests/test_d24_tuning_session.py
- tests/test_d25_tuning_integration.py
- tests/test_d26_parallel_and_distributed.py
- tests/test_d27_monitoring.py
- tests/test_d28_orchestrator.py
- tests/test_d37_arbitrage_mvp.py
- tests/test_d38_arbitrage_tuning.py
- tests/test_d41_k8s_tuning_session_runner.py
- tests/test_d42_binance_futures.py
- tests/test_d53_performance_loop.py
- tests/test_d77_0_topn_arbitrage_paper.py
- tests/test_d80_fix_trade_closure.py
- tests/test_d82_fill_model.py
- tests/test_d86_fill_calibration.py
- tests/test_d87_3_duration_guard.py
- tests/test_d90_integration.py
- tests/test_d95_performance_gate.py
- tests/test_d98_4_live_key_guard.py

### 카테고리 B: 레거시 docs 폴더 (D82~D106, 19개 디렉토리)

**정책:** 삭제 금지. D208-SLIM-1 단계에서 docs/archive/legacy_docs/ 로 이동.

- docs/D82/
- docs/D83/
- docs/D84/
- docs/D85/
- docs/D86/
- docs/D87/
- docs/D88/
- docs/D89/
- docs/D90/
- docs/D91/
- docs/D92/
- docs/D93/
- docs/D94/
- docs/D95/
- docs/D96/
- docs/D97/
- docs/D98/
- docs/D99/
- docs/D106/

### 카테고리 C: 레거시 스크립트 (D200 미만 전용)

**정책:** 삭제 금지. D208-SLIM-1 단계에서 legacy_archive/scripts/ 로 이동.

대표 파일:
- scripts/analyze_d82_7_edge_and_thresholds.py
- scripts/analyze_d82_9_kpi_deepdive.py
- scripts/analyze_d82_9_tp_candidates.py
- scripts/analyze_d83_0_5_fill_events.py
- scripts/analyze_d84_2_fill_results.py
- scripts/analyze_d85_1_fill_results.py
- scripts/analyze_d86_fill_data.py
- scripts/analyze_d87_3_fillmodel_ab_test.py
- scripts/analyze_d90_3_results.py
- scripts/apply_d72_4_migration.py
- scripts/apply_d72_migration.py
- scripts/apply_d73_d77_restructure.py
- scripts/apply_d76_alert_migration.py

### 카테고리 D: 레거시 로그 디렉토리

**정책:** 삭제 금지. D208-SLIM-3 단계에서 정리.

- logs/d77-0/
- logs/d77-0-rm-ext/
- logs/d82-11/
- logs/d82-12/
- logs/d82-9/
- logs/d92-1/
- logs/d92-2/

---

## 3. V2에서 참조/사용 중인 파일 (보존 필수)

### 코드 (arbitrage/v2/**)
- arbitrage/v2/core/ (orchestrator, engine_report, monitor, run_watcher, metrics, opportunity_source, runtime_factory, feature_guard)
- arbitrage/v2/domain/ (pnl_calculator 등)
- arbitrage/v2/marketdata/ (ratelimit, ws/)
- arbitrage/v2/universe/ (builder.py)
- arbitrage/v2/funding/ (provider.py)
- arbitrage/v2/alpha/ (obi_calculator 등)

### 공유 코드 (V1/V2 공용, 이동 금지)
- arbitrage/domain/ (fee_model.py, topn_provider.py)
- arbitrage/exchanges/ (binance_public_data.py, ws_client.py, binance_l2_ws_provider.py)
- arbitrage/alerting/ (models.py, storage/)

### 설정
- config/v2/config.yml
- ops/factory/ (controller.py, supervisor.py, worker.py)

### 테스트 (V2 게이트 필수)
- tests/test_d_alpha_*.py
- tests/test_d20[5-9]_*.py
- tests/test_d207_*.py
- tests/v2/ (존재 시)
- tests/conftest.py

### 문서 (SSOT)
- D_ROADMAP.md (Slim Index)
- docs/v2/ROADMAP_V2.md
- docs/v2/design/AC_LEDGER.md
- docs/v2/SSOT_RULES.md
- docs/v2/V2_ARCHITECTURE.md
- docs/v2/design/ (SSOT_MAP, EVIDENCE_FORMAT, NAMING_POLICY 등)

---

## 4. 삭제 금지 원칙 확인

1. **레거시 코드/테스트/문서는 절대 삭제하지 않는다.** 이동(격리)만 허용.
2. **이동 시 원본 경로와 목적지를 문서화한다.**
3. **V2에서 참조하는 공유 코드(arbitrage/domain, arbitrage/exchanges)는 이동 금지.**
4. **archive 파일은 수정 금지 (동결 보존).**

---

## 5. 공장 입력(큐) 단일 정의 요약

```
큐 파일:    docs/v2/design/AC_LEDGER.md
파서:       ops/factory/controller.py::parse_ledger_rows()
선택 규칙:  ops/factory/controller.py::pick_safe_open_ticket()
            - 최상단 첫 번째 OPEN 행 포인팅
            - D200 미만 자동 SKIP (_is_v2_alpha_ticket)
            - D_ALPHA/ALPHA 키워드 허용
포인터:     현재 D_ALPHA-0::AC-2 (첫 OPEN)
```

---

## 6. Status Truth Sync 적용 결과

| 구분 | AS-IS (기존 로드맵) | TO-BE (evidence 기반) |
|---|---|---|
| DONE AC (D_ALPHA) | 다수 COMPLETED 표시 | 8개만 DONE (evidence 존재) |
| OPEN AC | 혼재 | 약 190개 OPEN (evidence 없음) |
| LOST_EVIDENCE AC | 없음 | 해당 없음 (기존 표기 제거, 모두 OPEN 처리) |
| 레거시 AC (D200 미만) | 약 230개 (AC_LEDGER 기존) | 0개 (AC_LEDGER에서 제거, archive 보존) |

---

## 7. CTO ADD-ON 준수 확인

| 규칙 | 준수 | 근거 |
|---|---|---|
| Zero-Touch Legacy Policy | O | 레거시 테스트 수정 0건. 이동 계획만 문서화 (D208-SLIM-2) |
| Status Truth Sync | O | evidence 기반 DONE 8개만 인정. 나머지 OPEN 처리 |
| Linear Queue Integrity | O | AC_LEDGER에서 D208(Refactoring) Alpha 직후 배치 |
| SSH Push Proof | - | Git commit + push 후 별도 기록 예정 |

---

## 8. 참조

- 레거시 전문: docs/archive/ROADMAP_LEGACY_FULL_20260220.md (7962줄, 동결)
- 레거시 AC_LEDGER: docs/archive/AC_LEDGER_BACKUP_20260220.md (394줄, 동결)
- V2 운영 레일: docs/v2/ROADMAP_V2.md
- SSOT Index: D_ROADMAP.md (233줄)
- AC 큐: docs/v2/design/AC_LEDGER.md (200줄)
