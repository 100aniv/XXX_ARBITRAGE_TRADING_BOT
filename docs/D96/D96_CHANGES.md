# D96 변경 파일 목록 (Changes)

**작성일**: 2025-12-17
**커밋**: (Git commit 후 업데이트 예정)

---

## 1. 신규 파일 (Added)

| 파일 | 설명 |
|------|------|
| `docs/D96/D96_0_OBJECTIVE.md` | D96 목표/AC 문서 |
| `docs/D96/D96_1_REPORT.md` | D96 실행 보고서 |
| `docs/D96/D96_CHANGES.md` | 변경 파일 목록 |
| `docs/D96/evidence/d96_top50_20m_kpi.json` | 20m smoke KPI |
| `docs/CORE_REGRESSION_SSOT.md` | Core Regression SSOT 정의 |

---

## 2. 수정 파일 (Modified)

| 파일 | 변경 내용 |
|------|----------|
| `pytest.ini` | Core Regression SSOT 마커 정의 추가 |
| `tests/conftest.py` | Optional 테스트 collect_ignore 설정 |
| `tests/test_d15_volatility.py` | optional_ml 마커 추가 |
| `tests/test_d19_live_mode.py` | optional_live 마커 추가 |
| `tests/test_d20_live_arm.py` | optional_live 마커 추가 |
| `config/arbitrage/zone_profiles_v2.yaml` | BTC threshold 테스트 호환 복원 |
| `config/environments/staging.py` | min_spread_bps validation 수정 |
| `CHECKPOINT_2025-12-17_ARBITRAGE_LITE_MID_REVIEW.md` | D95 PASS 상태 업데이트, 상태표 추가 |
| `D_ROADMAP.md` | D97/D98 추가, M7~M9 마일스톤 추가, Core Regression SSOT 섹션 |

---

## 3. Raw 링크 (Git push 후 업데이트)

```
# SHA: <COMMIT_SHA>
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/docs/D96/D96_0_OBJECTIVE.md
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/docs/D96/D96_1_REPORT.md
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/docs/CORE_REGRESSION_SSOT.md
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/D_ROADMAP.md
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/<SHA>/CHECKPOINT_2025-12-17_ARBITRAGE_LITE_MID_REVIEW.md
```

---

## 4. Compare 링크

```
https://github.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/compare/04f8da3...<NEW_SHA>
```
