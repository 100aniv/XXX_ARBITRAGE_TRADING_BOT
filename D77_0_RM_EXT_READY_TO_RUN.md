# D77-0-RM-EXT 실행 준비 완료 ✅

**작성일:** 2025-12-03  
**상태:** 실행 준비 완료 (사용자 수동 실행 필요)

---

## 🎯 준비 완료 항목

### 1. 문서 업데이트 ✅
- [x] `docs/D77_0_RM_EXT_EXECUTION_PLAN.md`
  - Top50을 "필수" Scenario로 변경
  - Acceptance Criteria에 Top20 + Top50 각각 평가 명시
  - 최종 판단 기준 명확화

- [x] `docs/D77_0_RM_EXT_EXECUTION_GUIDE.md` (신규 작성)
  - 환경 준비부터 결과 분석까지 전체 플로우
  - 단계별 명령어 및 확인 사항
  - 트러블슈팅 가이드

### 2. 실행 스크립트 준비 ✅
- [x] `scripts/run_d77_0_rm_ext.py` (기존 확인)
  - smoke/primary/extended 시나리오 지원
  - Top20/Top50 자동 매핑

- [x] `scripts/prepare_d77_0_rm_ext_env.py` (신규 작성)
  - Docker 인프라 상태 확인
  - Redis/PostgreSQL 연결 테스트
  - Redis 상태 정리 (D77 관련 키)
  - 기존 프로세스 종료

- [x] `scripts/analyze_d77_0_rm_ext_results.py` (신규 작성)
  - Top20 + Top50 KPI 분석
  - Acceptance Criteria 자동 체크
  - 최종 판단 (GO/CONDITIONAL GO/NO-GO)

### 3. 실행 환경 ✅
- [x] 래퍼 스크립트 검증 완료
- [x] 테스트 파일 존재 확인
- [x] 문서 일관성 검증

---

## 🚀 실행 절차 (요약)

### Step 0: 환경 준비 (15분)

```powershell
# 가상환경 활성화
.\abt_bot_env\Scripts\Activate.ps1

# Docker 기동
docker-compose up -d redis postgres prometheus grafana

# 환경 정리
python scripts/prepare_d77_0_rm_ext_env.py --clean-all --kill-processes
```

### Step 1: Smoke Test (3분)

```powershell
python scripts/run_d77_0_rm_ext.py --scenario smoke
```

### Step 2: Top20 Primary (60분)

```powershell
python scripts/run_d77_0_rm_ext.py --scenario primary
```

**모니터링:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

### Step 3: Top50 Extended (60분)

```powershell
python scripts/run_d77_0_rm_ext.py --scenario extended
```

### Step 4: 결과 분석

```powershell
python scripts/analyze_d77_0_rm_ext_results.py \
    --top20-kpi logs/d77-0-rm-ext/run_*/1h_top20_kpi.json \
    --top50-kpi logs/d77-0-rm-ext/run_*/1h_top50_kpi.json
```

---

## 📊 예상 결과

### Critical Criteria (각 Universe)
- C1: 1h 연속 실행 (58~62분)
- C2: Round Trips ≥ 50
- C3: Memory 증가율 ≤ 10%/h
- C4: CPU ≤ 70% (평균)
- C5: Prometheus 스냅샷 저장

### 최종 판단
- **GO**: Top20 + Top50 모두 Critical 5/5 → D78 진행
- **CONDITIONAL GO**: 둘 중 하나 Critical 4/5 → Gap 명시 후 판단
- **NO-GO**: Critical < 4/5 → 재검증 필요

---

## ⚠️ 주의사항

1. **사용자 수동 실행 필수**
   - Windsurf AI는 스크립트 준비까지만 담당
   - 실제 1시간 실행은 사용자가 직접 수행

2. **수동 중단 금지**
   - Ctrl+C로 중단하지 말 것
   - Crash 발생 시에만 중단

3. **결과 솔직히 기록**
   - 실패 시 "성공"으로 위장 금지
   - 미달 항목은 정확히 보고

4. **엔진 코드 변경 금지**
   - 모든 작업은 실행/문서 레벨만
   - Core engine은 DO-NOT-TOUCH

---

## 📝 실행 후 작업

### 1. 리포트 업데이트

```powershell
# docs/D77_0_RM_EXT_REPORT.md 업데이트
# - Session Overview (Top20/Top50)
# - Trading KPI (실제 수치 반영)
# - Monitoring & Infrastructure
# - Gap Analysis
# - Conclusion (판단 결과)
```

### 2. D_ROADMAP.md 업데이트

```powershell
# D77-0-RM-EXT 섹션 수정
# - Status: PARTIAL → COMPLETE (조건 충족 시)
# - Done Criteria: Top20 + Top50 완료 명시
# - 판단: GO / CONDITIONAL GO / NO-GO
# - Next: D78 또는 재검증
```

### 3. Git Commit

```powershell
git add docs/D77_0_RM_EXT_*.md D_ROADMAP.md scripts/*.py
git commit -m "[D77-0-RM-EXT] Complete Top20+Top50 1h Real PAPER validation & update roadmap"
```

---

## 🔍 상세 가이드

**전체 절차:** `docs/D77_0_RM_EXT_EXECUTION_GUIDE.md` 참조

**Troubleshooting:**
- Redis 연결 실패 → `docker-compose restart redis`
- Prometheus 메트릭 없음 → `docker-compose restart prometheus`
- Crash 발생 → 로그 확인 후 환경 재초기화

---

**작성:** Windsurf AI  
**실행 담당:** 사용자 (수동 실행 및 모니터링 필수)  
**예상 소요 시간:** 약 2시간 15분 (Smoke 3분 + Top20 60분 + Top50 60분 + 정리 12분)  
**중요:** 실행 중 문제 발생 시 즉시 중단하고 실패로 보고할 것
