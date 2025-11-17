# Arbitrage-Lite Core Service Dockerfile (D15 고성능 버전)
# =========================================================
# 용도:
# - arbitrage-core 컨테이너 (메인 봇)
# - D15 고성능 모듈 포함:
#   - ml/volatility_model.py (PyTorch LSTM, GPU 지원)
#   - arbitrage/portfolio_optimizer.py (NumPy 벡터화)
#   - arbitrage/risk_quant.py (NumPy 벡터화)
# - 실거래 API 지원 (LIVE_MODE 환경변수로 제어)
# - LiveGuard + Safety 모듈 활성화

FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
# - gcc: 컴파일 필요 패키지 (numpy, torch 등)
# - postgresql-client: DB 연결 테스트
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 관리자 업그레이드
RUN pip install --no-cache-dir pip setuptools wheel

# requirements.txt 복사 및 설치
# ⚠️ 중요: requirements.txt에 numpy, pandas, torch 명시되어 있어야 함
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 환경 변수
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=docker

# 헬스 체크 (Python 기본 실행 확인)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 진입점: live_loop 실행
# 환경변수로 제어:
# - LIVE_MODE=false (기본): paper/simulation mode
# - LIVE_MODE=true: 실거래 모드 (LiveGuard, Safety 활성화)
CMD ["python", "-m", "arbitrage.live_loop"]
