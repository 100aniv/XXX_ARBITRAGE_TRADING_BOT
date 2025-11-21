#!/bin/bash
# ============================================================================
# Arbitrage Engine - Wrapper Script
# Used by systemd service to start engine with proper environment
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[RUN_ENGINE]${NC} Starting Arbitrage Engine..."

# ============================================================================
# Configuration
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="${PROJECT_ROOT}/venv"
LOG_DIR="${PROJECT_ROOT}/logs"
MODE="${MODE:-paper}"

# ============================================================================
# Pre-flight checks
# ============================================================================
echo -e "${YELLOW}[RUN_ENGINE]${NC} Pre-flight checks..."

# Check virtual environment
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}[RUN_ENGINE]${NC} Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Activate virtual environment
source "${VENV_PATH}/bin/activate" 2>/dev/null || source "${VENV_PATH}/Scripts/activate"

# Check log directory
mkdir -p "$LOG_DIR"

# Check Redis connection
echo -e "${YELLOW}[RUN_ENGINE]${NC} Checking Redis connection..."
python -c "import redis; r=redis.Redis(host='${REDIS_HOST:-localhost}', port=${REDIS_PORT:-6379}); r.ping()" || {
    echo -e "${RED}[RUN_ENGINE]${NC} Redis connection failed"
    exit 1
}

# Check PostgreSQL connection
echo -e "${YELLOW}[RUN_ENGINE]${NC} Checking PostgreSQL connection..."
python -c "
import psycopg2
conn = psycopg2.connect(
    host='${POSTGRES_HOST:-localhost}',
    port=${POSTGRES_PORT:-5432},
    database='${POSTGRES_DB:-arbitrage}',
    user='${POSTGRES_USER:-arbitrage}',
    password='${POSTGRES_PASSWORD:-arbitrage}'
)
conn.close()
" || {
    echo -e "${RED}[RUN_ENGINE]${NC} PostgreSQL connection failed"
    exit 1
}

echo -e "${GREEN}[RUN_ENGINE]${NC} All pre-flight checks passed"

# ============================================================================
# Start engine
# ============================================================================
cd "$PROJECT_ROOT"

echo -e "${GREEN}[RUN_ENGINE]${NC} Starting engine in ${MODE} mode..."
echo -e "${YELLOW}[RUN_ENGINE]${NC} Log file: ${LOG_DIR}/arbitrage_${ENV:-production}.log"

# Execute engine
exec python -m arbitrage.live_runner --mode "$MODE"
