# V1 Legacy Documentation

**Status:** READ-ONLY  
**Version:** 1.0 (D15 ~ D106)  
**Archived Date:** 2025-12-29

---

## 📖 Overview

이 폴더는 **V1 아키텍처 문서의 존재를 마킹**하기 위한 것입니다.

실제 V1 문서는 `docs/` 디렉토리 아래에 위치하며, **현재 위치에서 이동하지 않습니다.**

---

## 📁 V1 Document Location

V1 문서는 아래 경로에 있습니다:

```
docs/
  ├── D15_*.md         # Phase 1: Docker + Paper Mode
  ├── D16_*.md         # Phase 1: Live Architecture
  ├── D17~D36/         # Phase 2: K8s Orchestration
  ├── D37~D48/         # Phase 3: Arbitrage MVP
  ├── D49~D64/         # Phase 4: WebSocket + Multi-symbol
  ├── D65~D76/         # Phase 5: Alerting + Monitoring
  ├── D77~D82/         # Phase 6: Real Market Validation
  ├── D83~D85/         # Phase 7: L2 Orderbook + Fill Model
  ├── D86~D91/         # Phase 8: Performance Optimization
  ├── D92~D95/         # Phase 9: Integration + Hardening
  ├── D96~D99/         # Phase 10: Regression Testing
  ├── D106/            # Phase 11: LIVE Preflight + Hotfix
  └── ...
```

---

## 🚫 V1 Document Policy

### READ-ONLY (원칙)
- ✅ **허용:** V1 문서 읽기, 참조, 학습
- ❌ **금지:** V1 문서 수정 (새 기능 추가, 리팩토링)
- ⚠️ **예외:** 버그 픽스, 오타 수정 (최소한으로)

### V1 코드 레퍼런스
V1 코드베이스는 아래 위치:
```
arbitrage/
  ├── exchanges/          # V1 거래소 어댑터 (upbit_spot.py 등)
  ├── cross_exchange/     # V1 크로스 거래소 로직
  ├── live_runner.py      # V1 메인 런너
  └── ...
```

---

## 🆕 V2 Architecture

V2는 **Engine-Centric 아키텍처**로 재설계되었습니다.

**V2 문서는 여기:**
```
docs/v2/
  ├── SSOT_RULES.md         # V2 개발 규칙
  ├── V2_ARCHITECTURE.md    # V2 아키텍처
  └── ...
```

**V2 코드는 여기:**
```
arbitrage/v2/
  ├── core/
  │   ├── order_intent.py   # Semantic layer
  │   ├── adapter.py        # Exchange adapter interface
  │   └── engine.py         # Arbitrage engine
  └── adapters/
      ├── upbit_adapter.py
      └── binance_adapter.py
```

---

## 🔄 Migration Timeline

### Phase 0: V1 + V2 공존 (현재)
- V1 코드 유지 (production 안정성)
- V2 코드 신규 작성 (v2 네임스페이스)

### Phase 1: V2 Validation
- PAPER 모드로 V2 검증
- V1과 동일한 결과 확인

### Phase 2: V2 Production
- V2 안정화 후 production 전환
- V1 코드 deprecated 마킹

### Phase 3: V1 Removal
- 3개월 유예 후 V1 코드 제거
- V1 문서는 아카이브 유지

---

## 📚 Key V1 Documents (Reference)

### Architecture
- `docs/D16_LIVE_ARCHITECTURE.md` - V1 LIVE 아키텍처
- `docs/D37_ARBITRAGE_MVP.md` - 차익거래 MVP 설계
- `docs/D79_CROSS_EXCHANGE_DESIGN.md` - 크로스 거래소 설계

### Testing & Validation
- `docs/D48_LONGRUN_TEST_PLAN.md` - Long-run 테스트 계획
- `docs/D77_0_RM_EXT_REPORT.md` - Real market validation
- `docs/D82/D82-11_SMOKE_TEST_PLAN.md` - Smoke 테스트 가이드

### Operations
- `docs/DEPLOYMENT_GUIDE.md` - 배포 가이드
- `docs/RUNBOOK.md` - 운영 런북
- `docs/TROUBLESHOOTING.md` - 트러블슈팅

### Final Reports
- `docs/D106/D106_4_1_FINAL_REPORT.md` - V1 마지막 핫픽스
- `docs/D99/D99_REPORT.md` - Regression 최종 리포트

---

## 🎓 Learning from V1

V2 개발 시 V1에서 배운 교훈:

### ✅ Keep
- WebSocket 기반 L2 orderbook
- 4-tier RiskGuard 구조
- Prometheus + Grafana 모니터링
- PAPER 모드 우선 검증

### ❌ Avoid
- 스크립트 중심 실험 (run_*.py 난립)
- 거래소 로직과 Runner 혼재
- SSOT 분산 (여러 ROADMAP 파일)

### 🔄 Improve
- Engine-Centric 아키텍처
- Semantic Layer (OrderIntent)
- Mock-First Testing
- 증거 기반 개발

---

**V1은 소중한 자산입니다. V2는 V1의 어깨 위에서 시작합니다.** 🚀
