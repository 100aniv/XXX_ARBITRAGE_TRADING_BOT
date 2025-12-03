# D77-0-RM-EXT 실행 가이드 (Top20 + Top50 1시간 Real Market PAPER)

**작성일:** 2025-12-03  
**목적:** D77-0-RM-EXT Top20 + Top50 1시간 Real Market PAPER Validation 완료

---

## 🎯 실행 목표

- **Top20 (Primary):** 1시간 Real Market PAPER 완주
- **Top50 (Extended):** 1시간 Real Market PAPER 완주
- **Acceptance Criteria:** Top20 + Top50 각각 Critical 5/5 충족 → GO

---

## 📋 사전 준비 (15분)

### 1. 가상환경 활성화

```powershell
cd "c:\Users\bback\Desktop\부업\9) 코인 자동매매\arbitrage-lite"
.\abt_bot_env\Scripts\Activate.ps1
```

### 2. Docker 인프라 기동

```powershell
docker-compose up -d redis postgres prometheus grafana
```

### 3. 환경 준비 스크립트 실행

```powershell
# 상태 확인만
python scripts/prepare_d77_0_rm_ext_env.py --check-only

# 전체 정리 (권장)
python scripts/prepare_d77_0_rm_ext_env.py --clean-all --kill-processes
```

**확인 사항:**
- ✅ Redis 연결 성공
- ✅ PostgreSQL 연결 성공
- ✅ Prometheus 실행 중 (http://localhost:9090)
- ✅ Grafana 실행 중 (http://localhost:3000)

---

## 🚀 실행 단계 (총 약 2시간 15분)

### Step 1: Smoke Test (3분) - 환경 검증

```powershell
python scripts/run_d77_0_rm_ext.py --scenario smoke
```

**기대 결과:**
- Duration: 3분 완주
- Round Trips: ≥ 1
- Crash: 0
- KPI JSON 생성: `logs/d77-0-rm-ext/run_*/smoke_3m_kpi.json`

**확인:**
```powershell
# KPI 파일 확인
Get-ChildItem -Path logs/d77-0-rm-ext -Recurse -Filter *smoke*kpi.json | Select-Object FullName, Length, LastWriteTime

# Prometheus 메트릭 확인
curl http://localhost:9090/api/v1/query?query=up
```

---

### Step 2: Primary Scenario - Top20 1시간

```powershell
# 실행 시작 (약 60분 소요)
python scripts/run_d77_0_rm_ext.py --scenario primary
```

**모니터링 (별도 터미널):**

```powershell
# 1. Prometheus 메트릭 실시간 확인
curl "http://localhost:9090/api/v1/query?query=arbitrage_round_trips_total"

# 2. Grafana Dashboard
# 브라우저에서 http://localhost:3000 접속
# Dashboard: TopN Arbitrage Core

# 3. 로그 실시간 확인 (옵션)
Get-Content -Path "logs/d77-0-rm-ext/run_*/primary.log" -Wait -Tail 50
```

**중단 조건 (즉시 중단 후 실패 보고):**
- Crash 발생 (예외 발생)
- HANG 발생 (5분 이상 무응답)
- Memory 증가율 > 20%
- CPU > 90% 지속 (5분 이상)

**완료 후 확인:**
```powershell
# KPI JSON 존재 확인
Test-Path logs/d77-0-rm-ext/run_*/1h_top20_kpi.json

# KPI 내용 확인
Get-Content logs/d77-0-rm-ext/run_*/1h_top20_kpi.json | ConvertFrom-Json | Format-List
```

---

### Step 3: Extended Scenario - Top50 1시간

```powershell
# 실행 시작 (약 60분 소요)
python scripts/run_d77_0_rm_ext.py --scenario extended
```

**모니터링 (동일):**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- 로그 실시간 확인

**중단 조건 (동일):**
- Crash/HANG/Memory/CPU 이상 발생 시 즉시 중단

**완료 후 확인:**
```powershell
# KPI JSON 존재 확인
Test-Path logs/d77-0-rm-ext/run_*/1h_top50_kpi.json

# KPI 내용 확인
Get-Content logs/d77-0-rm-ext/run_*/1h_top50_kpi.json | ConvertFrom-Json | Format-List
```

---

## 📊 결과 수집 및 분석

### 1. KPI 수집 스크립트 (수동 실행)

```powershell
# Top20 결과
$top20_kpi = Get-Content logs/d77-0-rm-ext/run_*/1h_top20_kpi.json | ConvertFrom-Json

Write-Host "Top20 Results:"
Write-Host "  Duration: $($top20_kpi.actual_duration_minutes) min"
Write-Host "  Round Trips: $($top20_kpi.round_trips_completed)"
Write-Host "  Win Rate: $($top20_kpi.win_rate)%"
Write-Host "  PnL: $($top20_kpi.total_pnl)"
Write-Host "  CPU Avg: $($top20_kpi.cpu_usage_pct)%"
Write-Host "  Memory Avg: $($top20_kpi.memory_usage_mb) MB"

# Top50 결과
$top50_kpi = Get-Content logs/d77-0-rm-ext/run_*/1h_top50_kpi.json | ConvertFrom-Json

Write-Host "`nTop50 Results:"
Write-Host "  Duration: $($top50_kpi.actual_duration_minutes) min"
Write-Host "  Round Trips: $($top50_kpi.round_trips_completed)"
Write-Host "  Win Rate: $($top50_kpi.win_rate)%"
Write-Host "  PnL: $($top50_kpi.total_pnl)"
Write-Host "  CPU Avg: $($top50_kpi.cpu_usage_pct)%"
Write-Host "  Memory Avg: $($top50_kpi.memory_usage_mb) MB"
```

### 2. Acceptance Criteria 체크

**Top20 Checklist:**
- [ ] C1: 1h 연속 실행 (Crash = 0)
- [ ] C2: Round Trips ≥ 50
- [ ] C3: Memory 증가율 ≤ 10%/h
- [ ] C4: CPU ≤ 70% (평균)
- [ ] C5: Prometheus 스냅샷 저장 성공
- [ ] H1: Loop Latency p99 ≤ 80ms
- [ ] H2: Win Rate 30~80%
- [ ] H3: Rate Limit 429 자동 복구 100%

**Top50 Checklist:**
- [ ] C1: 1h 연속 실행 (Crash = 0)
- [ ] C2: Round Trips ≥ 50
- [ ] C3: Memory 증가율 ≤ 10%/h
- [ ] C4: CPU ≤ 70% (평균)
- [ ] C5: Prometheus 스냅샷 저장 성공
- [ ] H1: Loop Latency p99 ≤ 80ms
- [ ] H2: Win Rate 30~80%
- [ ] H3: Rate Limit 429 자동 복구 100%

### 3. 최종 판단

**판단 기준:**
- **GO**: Top20 + Top50 모두 Critical 5/5 충족
- **CONDITIONAL GO**: 둘 중 하나가 Critical 4/5
- **NO-GO**: 어느 Universe든 Critical < 4/5

---

## 📝 리포트 작성

### 1. D77_0_RM_EXT_REPORT.md 업데이트

**업데이트 항목:**
1. **Session Overview** (Top20/Top50 각각)
   - Session ID, Start/End Time, Duration, Exit Reason
2. **Trading KPI** (Top20/Top50 각각)
   - Round Trips, Win Rate, PnL, Drawdown
3. **Monitoring & Infrastructure**
   - Prometheus/Grafana 관찰, 429 핸들링, CPU/Memory
4. **Gap Analysis**
   - Top20 vs Top50 비교
5. **Conclusion**
   - GO / CONDITIONAL GO / NO-GO 판단

### 2. D_ROADMAP.md 업데이트

**업데이트 항목:**
- Status: ⚠️ PARTIAL → ✅ COMPLETE (조건 충족 시)
- Done Criteria: Top20 + Top50 실행 완료 명시
- 판단 결과: GO/CONDITIONAL GO/NO-GO
- Next: D78 또는 재검증

---

## ⚠️ 주의사항

1. **엔진 코드 변경 금지**: 모든 작업은 실행/문서 레벨만
2. **수동 중단 금지**: Ctrl+C 사용 금지 (자동 완료 대기)
3. **PnL 해석 주의**: Real Market PAPER는 엔진 검증용, 실거래 수익 보장 아님
4. **Rate Limit 예상**: Upbit 429는 정상 동작, 자동 복구 검증이 핵심
5. **Crash 시**: 즉시 실패 보고, "성공"으로 위장 금지

---

## 🔍 트러블슈팅

### Issue 1: Redis 연결 실패
```powershell
docker-compose restart redis
python scripts/prepare_d77_0_rm_ext_env.py --check-only
```

### Issue 2: Prometheus 메트릭 없음
```powershell
# Prometheus 재시작
docker-compose restart prometheus
# 엔드포인트 확인
curl http://localhost:9090/-/healthy
```

### Issue 3: Crash 발생
```powershell
# 로그 확인
Get-Content logs/d77-0-rm-ext/run_*/error.log
# 환경 재초기화
python scripts/prepare_d77_0_rm_ext_env.py --clean-all --kill-processes
```

---

**작성:** Windsurf AI  
**실행 담당:** 사용자 (수동 실행 및 모니터링 필수)  
**예상 소요 시간:** 약 2시간 15분 (Smoke 3분 + Top20 60분 + Top50 60분 + 정리 12분)
