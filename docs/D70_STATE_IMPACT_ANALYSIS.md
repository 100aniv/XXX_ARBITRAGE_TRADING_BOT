# D70 – STATE_PERSISTENCE & RECOVERY: Impact Analysis

**작성일:** 2025-11-20  
**상태:** D70-1 (설계 & 영향도 분석)  
**목적:** 상태 영속화/복원 구현 시 모듈별 변경 사항 및 잠재적 리스크 분석

---

## 1. Module-Level Impact Summary (모듈별 영향도 요약)

| 모듈 | 변경 유형 | 예상 라인 수 | 리스크 레벨 | 우선순위 |
|------|----------|-------------|------------|---------|
| `ArbitrageLiveRunner` | 메서드 추가 + 수정 | ~300 | High | P1 |
| `RiskGuard` | 메서드 추가 | ~50 | Medium | P1 |
| `StateManager` | 메서드 추가 | ~100 | Medium | P2 |
| `StateStore` (새 모듈) | 새 모듈 생성 | ~500 | High | P1 |
| PostgreSQL Schema | 새 테이블 생성 | ~150 (SQL) | Medium | P1 |
| Test Scripts | 새 스크립트 | ~300 | Low | P2 |
| **Total** | - | **~1400 lines** | - | - |

---

## 2. ArbitrageLiveRunner 변경 사항

### 2.1 추가 메서드

```python
def _initialize_session(mode, session_id)
def _initialize_clean_state()
def _restore_state_from_snapshot()
def _validate_snapshot(snapshot)
def _restore_positions(positions_data)
def _restore_metrics(metrics_data)
def _save_state_to_redis()
def _save_snapshot_to_db_async(snapshot_type)
def _serialize_active_orders()
def _deserialize_trade(data)
def _deserialize_order(data)
```

### 2.2 기존 메서드 수정

```python
__init__()  # state_store 파라미터 추가
_execute_open_trade()  # Redis 상태 업데이트 추가
_execute_close_trade()  # Redis + PostgreSQL 스냅샷 추가
run_forever()  # 주기적 스냅샷 로직 추가
```

### 2.3 잠재적 리스크

**High Risk:**
- 복원 로직 버그 시 포지션 소실
- 성능 오버헤드 (Redis 쓰기)

**완화 전략:**
- 철저한 단위 테스트
- 비동기 쓰기
- 검증 로직 강화

---

## 3. RiskGuard 변경 사항

### 3.1 추가 메서드

```python
def get_state() -> Dict
def restore_state(state_data: Dict)
```

### 3.2 잠재적 리스크

**Medium Risk:**
- 일일 손실 누적 오류
- 심볼별 상태 누락

**완화 전략:**
- 검증 로직
- 기본값 설정

---

## 4. StateStore (새 모듈)

### 4.1 책임

- Redis/PostgreSQL 통합 상태 저장/로드
- 스냅샷 관리
- 일관성 검증

### 4.2 핵심 메서드

```python
save_state_to_redis(session_id, state_data)
load_state_from_redis(session_id)
save_snapshot_to_db(session_id, snapshot_type)
load_latest_snapshot(session_id)
delete_session_state(session_id)
save_initial_snapshot(session_id, config)
```

### 4.3 잠재적 리스크

**High Risk:**
- DB 연결 실패
- 스냅샷 크기 증가
- 동시성 충돌

**완화 전략:**
- Redis 상태만 유지 (DB 실패 시)
- 압축, 오래된 스냅샷 정리
- 세션 ID 기반 격리

---

## 5. PostgreSQL Schema

### 5.1 새 테이블

```sql
CREATE TABLE session_snapshots (...)
CREATE TABLE position_snapshots (...)
CREATE TABLE metrics_snapshots (...)
CREATE TABLE risk_guard_snapshots (...)
```

### 5.2 잠재적 리스크

**Medium Risk:**
- 스키마 마이그레이션
- 인덱스 성능
- 스토리지 용량

**완화 전략:**
- `CREATE TABLE IF NOT EXISTS`
- 적절한 인덱스 설계
- 주기적 정리 (> 7일 삭제)

---

## 6. Risk Assessment (리스크 평가)

### 6.1 High Risk

#### 복원 실패 시 데이터 손실

**완화:**
- 다중 스냅샷 (최근 3개 유지)
- 검증 로직
- Fallback (CLEAN_RESET 권장)

#### 성능 저하

**완화:**
- 비동기 쓰기
- 배치 업데이트
- 백그라운드 스레드

### 6.2 Medium Risk

#### Redis/PostgreSQL 일관성

**완화:**
- Redis 우선 (SSOT)
- PostgreSQL 비동기
- 스냅샷 ID 추적

#### 메모리 증가

**완화:**
- 즉시 해제
- 스레드 풀 제한
- 메모리 모니터링

### 6.3 Low Risk

#### 스냅샷 스토리지 용량

**완화:**
- 주기적 정리
- 압축

---

## 7. Implementation Priority (구현 우선순위)

### P1 (필수)

1. **StateStore 모듈 생성**
2. **PostgreSQL 스키마 생성**
3. **ArbitrageLiveRunner 복원 로직**
4. **RiskGuard 상태 저장/복원**

### P2 (권장)

1. **StateManager 확장**
2. **Test Scripts**
3. **성능 최적화**

### P3 (향후)

1. **압축**
2. **분산 시스템 지원**
3. **실시간 백업**

---

## 8. Testing Strategy (테스트 전략)

### 8.1 Unit Tests

- `StateStore` 메서드별 테스트
- 직렬화/역직렬화 테스트
- 검증 로직 테스트

### 8.2 Integration Tests

- Scenario 1~5 자동화
- CLEAN_RESET vs RESUME 비교
- Redis/PostgreSQL 통합 테스트

### 8.3 Performance Tests

- 루프 시간 측정
- Redis 쓰기 오버헤드
- PostgreSQL 스냅샷 시간

---

## 9. Rollout Plan (배포 계획)

### Phase 1: D70-2 (구현)

- StateStore 모듈 생성
- ArbitrageLiveRunner 훅 추가
- PostgreSQL 스키마 생성

### Phase 2: D70-3 (테스트)

- Scenario 1~5 실행
- 회귀 테스트 (D65~D69)
- 성능 측정

### Phase 3: D70-4 (최적화)

- 비동기 쓰기 최적화
- 압축 적용
- 모니터링 추가

---

## 10. Success Criteria (성공 기준)

### 10.1 기능

- ✅ CLEAN_RESET 모드 정상 동작
- ✅ RESUME_FROM_STATE 모드 정상 동작
- ✅ 포지션 복원 정확도 100%
- ✅ 메트릭 복원 정확도 100%

### 10.2 성능

- ✅ 루프 시간 증가 < 10%
- ✅ Redis 쓰기 오버헤드 < 2ms
- ✅ 복원 시간 < 1초

### 10.3 안정성

- ✅ 회귀 테스트 PASS (D65~D69)
- ✅ 스냅샷 손상 시 Fallback 동작
- ✅ Redis/PostgreSQL 실패 시 Graceful Degradation

---

**작성자:** Windsurf Cascade  
**검토 필요:** D70-2 구현 전 아키텍처 리뷰
