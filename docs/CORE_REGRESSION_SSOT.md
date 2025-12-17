# Core Regression SSOT (Single Source of Truth)

**상태**: ✅ 100% PASS (44/44 테스트)
**최종 업데이트**: 2025-12-17

---

## 1. Core Regression 정의

Core Regression은 **항상 100% PASS**여야 하는 핵심 테스트 스위트입니다.
환경 의존(ML/torch, Live 모드 등) 테스트는 Optional Suite로 분리됩니다.

---

## 2. Core Regression 테스트 목록

```bash
# Core Regression 실행 명령어
python -m pytest tests/test_d27_monitoring.py tests/test_d82_0_runner_executor_integration.py tests/test_d82_2_hybrid_mode.py tests/test_d92_1_fix_zone_profile_integration.py tests/test_d92_7_3_zone_profile_ssot.py -v --tb=short
```

### 포함된 테스트 파일 (5개, 44 테스트)

| 파일 | 테스트 수 | 설명 |
|------|----------|------|
| `test_d27_monitoring.py` | 8 | 모니터링 시스템 |
| `test_d82_0_runner_executor_integration.py` | 4 | Runner-Executor 통합 |
| `test_d82_2_hybrid_mode.py` | 8 | Hybrid 모드 |
| `test_d92_1_fix_zone_profile_integration.py` | 16 | Zone Profile 통합 |
| `test_d92_7_3_zone_profile_ssot.py` | 8 | Zone Profile SSOT |

---

## 3. Optional Suite (환경 의존)

### 3.1 Optional ML (torch 의존)
```bash
# conftest.py에서 collect_ignore로 제외됨
tests/test_d15_volatility.py
```

### 3.2 Optional Live (LiveTrader 의존)
```bash
# conftest.py에서 collect_ignore로 제외됨
tests/test_d19_live_mode.py
tests/test_d20_live_arm.py
```

### 3.3 Configuration-Dependent (설정 변경에 민감)
나머지 테스트들은 zone_profiles, 환경 설정 등에 의존하여 설정 변경 시 실패할 수 있음.
별도의 Integration/E2E 스위트로 관리.

---

## 4. 실행 정책

1. **모든 커밋 전**: Core Regression 100% PASS 필수
2. **설정 변경 시**: Configuration-Dependent 테스트 검토 필요
3. **ML 환경 변경 시**: Optional ML 테스트 별도 실행

---

## 5. pytest.ini 설정

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

markers =
    optional_ml: ML/torch 종속성 테스트 (환경 의존, Core에서 제외)
    optional_live: Live 환경 종속성 테스트 (환경 의존, Core에서 제외)
```

---

## 6. conftest.py 설정

```python
# Core Regression SSOT: Exclude environment-dependent tests from collection
collect_ignore = [
    "test_d15_volatility.py",  # ML/torch dependency
    "test_d19_live_mode.py",   # LiveTrader/ML dependency  
    "test_d20_live_arm.py",    # LiveTrader/ML dependency
]
```
