┌──────────────────────── arbitrage-lite Core ────────────────────────┐
│                                                                    │
│  [Market Data Layer]                                               │
│   ┌─────────────────────────────┐    ┌───────────────────────────┐  │
│   │ D83-1 L2 WebSocket Provider │    │ D80-x Multi-Currency Core│  │
│   └─────────────┬───────────────┘    └───────────────┬──────────┘  │
│                 │                                    │             │
│        L2 Orderbook + Trades                 Money/PNL/Risk Base   │
│                 │                                    │             │
│                 ▼                                    ▼             │
│        ┌────────────────────────────────────────────────────┐      │
│        │         D84-2 CalibratedFillModel Engine          │      │
│        │  - 실전 체결률/슬리피지 반영                     │      │
│        │  - Fill Events (jsonl) 기록                       │      │
│        └─────────────┬─────────────────────────────────────┘      │
│                      │ FillEvents                                │
│                      ▼                                            │
│        ┌────────────────────────────────────────────────────┐      │
│        │       Entry / Execution (D90 Zone Cluster)        │      │
│        │                                                    │      │
│        │  1) Config Layer                                   │      │
│        │     - config/arbitrage/zone_profiles.yaml          │      │
│        │       · strict_uniform                             │      │
│        │       · advisory_z2_focus                          │      │
│        │       · 기타 profile                              │      │
│        │                                                    │      │
│        │  2) Loader Layer                                   │      │
│        │     - arbitrage/config/zone_profiles_loader.py     │      │
│        │       · YAML 로딩 + 스키마 검증                   │      │
│        │       · dict-like 인터페이스 제공                 │      │
│        │       · backward compatibility 유지                │      │
│        │                                                    │      │
│        │  3) Domain Layer                                   │      │
│        │     - arbitrage/domain/entry_bps_profile.py        │      │
│        │       · class EntryBPSProfile                      │      │
│        │       · mode=zone_random                           │      │
│        │       · zone_profile="strict_uniform"/…            │      │
│        │       · 난수 시드 기반 Zone(Z1~Z4) 샘플링          │      │
│        │                                                    │      │
│        │  4) Runner Layer                                   │      │
│        │     - scripts/run_d84_2_calibrated_fill_paper.py   │      │
│        │       · --entry-bps-mode zone_random               │      │
│        │       · --entry-bps-zone-profile strict_uniform    │      │
│        │       · --entry-bps-seed 91                        │      │
│        └─────────────┬─────────────────────────────────────┘      │
│                      │                                            │
│             Trades + FillEvents                                   │
│                      │                                            │
│                      ▼                                            │
│        ┌────────────────────────────────────────────────────┐      │
│        │      Cross-Exchange Risk & Metrics Stack           │      │
│        │   - CrossExchangeRiskGuard (다중 티어 Risk)        │      │
│        │   - CrossExchangePnLTracker                         │      │
│        │   - CrossExchangeMetrics + Prometheus Exporter     │      │
│        └────────────────────────────────────────────────────┘      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

※ D90-4/5까지는 위 구조 중 “Config → Loader → Domain → Runner”  
  이 4단의 Zone Profile 파이프라인을 BTC 단일 심볼 기준으로 완전히 검증한 상태.
※ D91 이후엔 이 구조 위에 “Symbol/Market별 Profile 매핑” 레이어를 하나 더 얹는 방향.
