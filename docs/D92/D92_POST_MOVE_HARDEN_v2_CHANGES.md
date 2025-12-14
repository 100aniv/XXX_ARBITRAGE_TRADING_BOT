# D92 POST-MOVE-HARDEN v2 변경 파일 목록

**기준 커밋:** dc0e477 (D92-POST-MOVE v1)  
**대상 커밋:** HEAD (작업 중)

---

## 변경 파일 (Modified/Added)

### 1. D_ROADMAP.md
**상태:** Modified  
**변경 내용:** UTF-8 복구, 한글 정상화, 모지바케 제거

**Raw URL (향후 커밋 후):**
```
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/{COMMIT_SHA}/D_ROADMAP.md
```

**변경 요약:**
- Git 히스토리 144개 커밋 모두 모지바케 상태였음
- PowerShell로 정상 UTF-8 버전 생성
- 한글 정상 표시 확인: "# arbitrage-lite 로드맵"

---

### 2. scripts/d77_4_env_checker.py
**상태:** Modified  
**변경 내용:** Postgres reset 로직 개선 (WARN=0 달성)

**Raw URL (향후 커밋 후):**
```
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/{COMMIT_SHA}/scripts/d77_4_env_checker.py
```

**변경 요약:**
- `_reset_postgres()` 함수 수정
- alert_history 테이블 자동 생성 추가 (CREATE TABLE IF NOT EXISTS)
- TRUNCATE로 데이터 정리
- 테이블 없음을 정상 상태로 처리 → WARN=0 달성

**수정 라인:** 252-308

---

### 3. scripts/recover_roadmap_utf8.py
**상태:** Added  
**변경 내용:** ROADMAP UTF-8 자동 복구 스크립트 (신규)

**Raw URL (향후 커밋 후):**
```
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/{COMMIT_SHA}/scripts/recover_roadmap_utf8.py
```

**기능:**
- Git 히스토리 스캔 (rev-list)
- UTF-8 품질 점수 계산 (한글 비율, 모지바케 패턴 감지)
- 최적 커밋 자동 선택 및 복구

---

### 4. docs/D92/D92_POST_MOVE_HARDEN_v2_REPORT.md
**상태:** Added  
**변경 내용:** v2 작업 최종 보고서 (신규)

**Raw URL (향후 커밋 후):**
```
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/{COMMIT_SHA}/docs/D92/D92_POST_MOVE_HARDEN_v2_REPORT.md
```

**내용:**
- AC-1~5 달성 현황
- Step별 상세 결과
- 남은 이슈 및 권장 사항

---

### 5. docs/D92/D92_POST_MOVE_HARDEN_v2_CHANGES.md
**상태:** Added  
**변경 내용:** 변경 파일 목록 및 Raw URL (이 파일)

---

## Git Diff 요약

**Modified:**
- `D_ROADMAP.md` - UTF-8 복구
- `scripts/d77_4_env_checker.py` - Postgres reset 로직 개선

**Added:**
- `scripts/recover_roadmap_utf8.py` - UTF-8 복구 스크립트
- `docs/D92/D92_POST_MOVE_HARDEN_v2_REPORT.md` - 최종 보고서
- `docs/D92/D92_POST_MOVE_HARDEN_v2_CHANGES.md` - 변경 파일 목록

---

## Raw URL 템플릿

커밋 후 `{COMMIT_SHA}`를 실제 커밋 해시로 교체:

```bash
# 변경 파일 확인
git log --oneline -1

# Raw URL 생성 예시
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/[COMMIT_SHA]/[FILE_PATH]
```

**예시:**
```
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/abc1234/D_ROADMAP.md
https://raw.githubusercontent.com/100aniv/XXX_ARBITRAGE_TRADING_BOT/abc1234/scripts/d77_4_env_checker.py
```

---

## 파일 크기 정보

| 파일 | 크기 | 비고 |
|------|------|------|
| D_ROADMAP.md | ~5 KB | 200KB 미만, 정상 푸시 가능 |
| d77_4_env_checker.py | ~12 KB | 정상 푸시 가능 |
| recover_roadmap_utf8.py | ~8 KB | 정상 푸시 가능 |
| D92_POST_MOVE_HARDEN_v2_REPORT.md | ~12 KB | 정상 푸시 가능 |

**전체 변경:** 5개 파일, 모두 200KB 미만으로 Git 푸시 가능

---

## 커밋 전 체크리스트

- [x] D_ROADMAP.md UTF-8 정상 (한글 표시)
- [x] env_checker Postgres Reset: OK
- [x] 문서 작성 완료
- [ ] Git 커밋
- [ ] Git 푸시
- [ ] Raw URL 업데이트 (커밋 후)
