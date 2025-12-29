# [D200-3] Docs Policy Lock + Watchdog(4종) + Evidence 실동작 정합성 마감

**작성일:** 2025-12-29  
**상태:** IN_PROGRESS  
**커밋:** (진행 중)

---

## 📋 목표 (Goal)

V2 SSOT(문서/룰/로드맵/테스트/증거)가 서로 100% 일치하도록 정합성 구멍을 닫고, watchdog/just 게이트 실행 시 evidence가 실제로 남는 최소 통합을 완료한다.

---

## ✅ AC (Acceptance Criteria)

| AC | 설명 | 상태 |
|----|------|------|
| AC-1 | docs/v2 구조 (design/reports/runbooks/templates) 물리적 정리 | ⏳ IN_PROGRESS |
| AC-2 | SSOT_RULES/SSOT_MAP 정합성 (Evidence 경로 logs/evidence로 고정) | ⏳ PENDING |
| AC-3 | .windsurfrule [WATCHDOG] 섹션 추가 (doctor/fast/regression/full) | ⏳ PENDING |
| AC-4 | Evidence 실동작 최소 통합 (tools/evidence_pack.py 검증 + 테스트) | ⏳ PENDING |
| AC-5 | v2 네이밍 정책 문서화 (NAMING_POLICY.md) | ⏳ PENDING |
| AC-6 | D_ROADMAP.md 업데이트 (D200-3 반영) | ⏳ PENDING |
| AC-7 | GATE 100% PASS (doctor/fast/regression) | ⏳ PENDING |
| AC-8 | Evidence 경로 1개 이상 생성 확인 | ⏳ PENDING |

---

## 📐 계획 (Plan Checklist)

- [x] Step 0: 부트스트랩 (SSOT 문서 검토)
- [x] P1: docs/v2 구조 물리적 정리 (폴더/템플릿 생성)
- [ ] P2: SSOT_RULES/SSOT_MAP 정합성 마감
- [ ] P3: .windsurfrule [WATCHDOG] 섹션 추가
- [ ] P4: Evidence 실동작 최소 통합
- [ ] P5: v2 네이밍 정책 문서화
- [ ] P6: D_ROADMAP.md 업데이트
- [ ] GATE: doctor/fast/regression 100% PASS
- [ ] GIT: 커밋 + 푸시

---

## 🔧 실행 노트 (Execution Notes)

### Step 0: 부트스트랩 검토 결과

**충돌/누락 요약:**
1. **경로 충돌**: SSOT_RULES.md에서 `docs/v2/evidence/` 언급 vs EVIDENCE_SPEC.md에서 `logs/evidence/` 정의
2. **문서명 불일치**: SSOT_MAP.md는 "Evidence SSOT"를 정의하지만 실제 파일명은 EVIDENCE_SPEC.md
3. **docs/v2 구조 미정의**: design/reports/runbooks/templates 폴더 구조가 SSOT_RULES에 없음
4. **watchdog 규칙 누락**: .windsurfrule에 [BOOTSTRAP]만 있고 [WATCHDOG] 섹션 없음
5. **justfile 기존 구조**: doctor/fast/regression 명령 이미 존재 → evidence 후킹만 추가하면 됨

### P1: docs/v2 구조 물리적 정리 (완료)

**생성된 폴더:**
- ✅ `docs/v2/reports/` - D별 리포트 저장소
- ✅ `docs/v2/runbooks/` - 운영 런북 저장소
- ✅ `docs/v2/templates/` - 템플릿 저장소

**생성된 파일:**
- ✅ `docs/v2/templates/REPORT_TEMPLATE.md` - 리포트 표준 템플릿
- ✅ `docs/v2/reports/D200/D200-3_REPORT.md` - 현재 리포트 (본 파일)

---

## 🧪 GATE 결과 (진행 중)

| Gate | 결과 | 세부 |
|------|------|------|
| Doctor | ⏳ PENDING | [테스트 수] |
| Fast | ⏳ PENDING | [테스트 수] (시간) |
| Regression | ⏳ PENDING | [테스트 수] (시간) |

---

## 📁 증거 (Evidence)

**Evidence 경로:** `logs/evidence/<run_id>/` (생성 예정)

**포함 파일:**
- manifest.json
- gate.log
- git_info.json
- cmd_history.txt

---

## 📊 변경 요약 (Diff Summary)

**커밋 해시:** (진행 중)

### Added (진행 중)
- `docs/v2/reports/D200/D200-3_REPORT.md`: D200-3 리포트
- `docs/v2/templates/REPORT_TEMPLATE.md`: 리포트 표준 템플릿
- `docs/v2/design/NAMING_POLICY.md`: v2 네이밍 정책 (예정)
- `docs/v2/design/EVIDENCE_FORMAT.md`: Evidence SSOT (EVIDENCE_SPEC.md → rename 예정)

### Modified (진행 중)
- `docs/v2/SSOT_RULES.md`: Evidence 경로 정정 (logs/evidence)
- `docs/v2/design/SSOT_MAP.md`: 문서명 정합화
- `.windsurfrule`: [WATCHDOG] 섹션 추가
- `D_ROADMAP.md`: D200-3 상태 반영

---

## 🎯 PASS/FAIL 판정 (진행 중)

**현재 상태:** ⏳ IN_PROGRESS

**다음 단계:**
1. P2: SSOT_RULES/SSOT_MAP 정합성 마감
2. P3: .windsurfrule [WATCHDOG] 추가
3. P4: Evidence 실동작 통합
4. GATE 실행 및 증거 생성
5. 최종 PASS 판정

---

## 🔗 참고

- SSOT_MAP: `docs/v2/design/SSOT_MAP.md`
- SSOT_RULES: `docs/v2/SSOT_RULES.md`
- D_ROADMAP: `D_ROADMAP.md`
- Evidence SSOT: `docs/v2/design/EVIDENCE_SPEC.md` (→ EVIDENCE_FORMAT.md로 rename 예정)
