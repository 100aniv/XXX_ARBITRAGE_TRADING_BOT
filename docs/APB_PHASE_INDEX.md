# Arbitrage Bot – PHASE INDEX (아비트라지 봇 페이즈 인덱스)

## 0. 프로젝트 개요

- 프로젝트명: `arbitrage-lite`
- 목적:
  - Upbit ↔ Binance (Spot/Futures) 간 스프레드 아비트라지
  - 단일 봇, 단일 전략이지만 상용급에 준하는 안정성과 운영성을 목표
- 현재 상태:
  - PHASE A: MVP 스캐폴딩 + Collect/Paper/Live 구조 완료
  - PHASE B: Paper 모드 안정화 + 포지션/PNL 검증 (진행 예정)
  - PHASE C 이후: 다심볼, 리스크/계좌/운영 고도화

---

## 1. PHASE 목록

### PHASE A – MVP 엔진 구축 (완료)
- 목표:
  - 단일 심볼(BTC) 기준으로:
    - 시세 수집 (Upbit/Binance Futures)
    - 스프레드/순 스프레드 계산
    - Paper/Live 모드 골격 구축
  - config/base.yml, secrets.yml, 모듈 구조(arbitrage/*) 확정
- 마스터 문서:
  - `docs/phase_A_master.md` (필요 시 추가)

### PHASE B – Paper 모드 안정화 & PnL 검증
- 목표:
  - Paper 모드에서 **포지션 OPEN/CLOSE + PnL**이 100% 신뢰 가능하게 만들기
  - positions.csv / trades.csv / debug log가 “상용에서 쓰기 충분한 수준”까지
  - 최소 1개의 강제 진입 테스트(debug.force_first_entry)로 파이프라인 자체를 검증
- 마스터 문서:
  - `docs/phase_B_master.md`

### PHASE C – Multi-Symbol & FX/리스크 고도화
- 목표(초기안):
  - BTC + ETH + 주요 알트 N개 동시 스캔
  - 실시간 FX(USD/KRW) 피드 연동
  - 심볼별 설정(스프레드, 리스크, max_notional 등) 분리
- 마스터 문서:
  - `docs/phase_C_master.md`

### PHASE D – 계좌/포지션 관리 + DB
- 목표(초기안):
  - DB(SQLite/PostgreSQL) 기반 계좌/포지션/트레이드 영속화
  - 재기동 시 기존 포지션 복원
  - 심볼/거래소/전략별 PnL 리포팅

### PHASE E – 운영/모니터링/알림
- 목표(초기안):
  - Slack/Telegram 알림
  - 간단한 대시보드(Web/CLI)
  - Kill-switch, 신규 진입 중지 토글 등 운영 기능

---

## 2. 현재 활성 PHASE

- `active_phase: B`
- 이번 PHASE 작업은 **반드시 `docs/phase_B_master.md` 기준으로 진행**한다.
- AI/LLM에게 요청 시:
  - 항상 `ARB_DEV_RULES.md`와 **현재 PHASE master** 기준으로 제한을 걸어야 한다.

---

## 3. 변경 기록 (요약)

- 2025-11-15
  - PHASE INDEX 초안 작성
  - PHASE B: Paper 모드 안정화 범위 설정
