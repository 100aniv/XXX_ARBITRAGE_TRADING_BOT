#!/bin/bash
# ============================================================================
# Arbitrage Engine - Container Entrypoint
# Handles readiness checks, graceful startup, and shutdown
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}[ENTRYPOINT]${NC} Starting Arbitrage Engine..."

# ============================================================================
# Environment Variables (with defaults)
# ============================================================================
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-arbitrage}"
POSTGRES_USER="${POSTGRES_USER:-arbitrage}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-arbitrage}"
MODE="${MODE:-paper}"
MAX_RETRIES=30
RETRY_INTERVAL=2

# ============================================================================
# Function: Wait for Redis
# ============================================================================
wait_for_redis() {
    echo -e "${YELLOW}[ENTRYPOINT]${NC} Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if python -c "import redis; r=redis.Redis(host='${REDIS_HOST}', port=${REDIS_PORT}, db=0); r.ping()" 2>/dev/null; then
            echo -e "${GREEN}[ENTRYPOINT]${NC} Redis is ready!"
            return 0
        fi
        echo -e "${YELLOW}[ENTRYPOINT]${NC} Redis not ready yet (attempt $i/$MAX_RETRIES)..."
        sleep $RETRY_INTERVAL
    done
    
    echo -e "${RED}[ENTRYPOINT]${NC} Redis readiness check failed after $MAX_RETRIES attempts"
    return 1
}

# ============================================================================
# Function: Wait for PostgreSQL
# ============================================================================
wait_for_postgres() {
    echo -e "${YELLOW}[ENTRYPOINT]${NC} Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT 1" >/dev/null 2>&1; then
            echo -e "${GREEN}[ENTRYPOINT]${NC} PostgreSQL is ready!"
            return 0
        fi
        echo -e "${YELLOW}[ENTRYPOINT]${NC} PostgreSQL not ready yet (attempt $i/$MAX_RETRIES)..."
        sleep $RETRY_INTERVAL
    done
    
    echo -e "${RED}[ENTRYPOINT]${NC} PostgreSQL readiness check failed after $MAX_RETRIES attempts"
    return 1
}

# ============================================================================
# Function: Check migrations
# ============================================================================
check_migrations() {
    echo -e "${YELLOW}[ENTRYPOINT]${NC} Checking database migrations..."
    
    # Check if system_logs table exists (D72-4)
    if PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'system_logs');" | grep -q "t"; then
        echo -e "${GREEN}[ENTRYPOINT]${NC} Database migrations are up to date"
        return 0
    else
        echo -e "${YELLOW}[ENTRYPOINT]${NC} Database migrations needed. Running migrations..."
        # Apply migrations if script exists
        if [ -f "/app/scripts/apply_all_migrations.py" ]; then
            python /app/scripts/apply_all_migrations.py
        else
            echo -e "${YELLOW}[ENTRYPOINT]${NC} No migration script found, skipping..."
        fi
        return 0
    fi
}

# ============================================================================
# Function: Graceful shutdown handler
# ============================================================================
shutdown_handler() {
    echo -e "${YELLOW}[ENTRYPOINT]${NC} Received shutdown signal..."
    echo -e "${YELLOW}[ENTRYPOINT]${NC} Stopping engine gracefully..."
    
    # Send SIGTERM to child process
    if [ ! -z "$ENGINE_PID" ]; then
        kill -TERM "$ENGINE_PID" 2>/dev/null || true
        wait "$ENGINE_PID" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}[ENTRYPOINT]${NC} Engine stopped gracefully"
    exit 0
}

# ============================================================================
# Setup signal handlers
# ============================================================================
trap shutdown_handler SIGTERM SIGINT

# ============================================================================
# Main execution
# ============================================================================

# Wait for dependencies
wait_for_redis || exit 1
wait_for_postgres || exit 1

# Check migrations
check_migrations

# Display configuration
echo -e "${GREEN}[ENTRYPOINT]${NC} Configuration:"
echo -e "  ENV: ${ENV}"
echo -e "  MODE: ${MODE}"
echo -e "  REDIS: ${REDIS_HOST}:${REDIS_PORT}"
echo -e "  POSTGRES: ${POSTGRES_HOST}:${POSTGRES_PORT}"

# Start engine
echo -e "${GREEN}[ENTRYPOINT]${NC} Starting engine in ${MODE} mode..."

# Execute command passed to entrypoint
exec "$@" &
ENGINE_PID=$!

# Wait for engine process
wait "$ENGINE_PID"
