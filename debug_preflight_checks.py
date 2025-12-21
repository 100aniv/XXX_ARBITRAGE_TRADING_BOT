import sys
import os
from unittest.mock import MagicMock, patch

# Setup
os.environ.update({
    'ARBITRAGE_ENV': 'paper',
    'READ_ONLY_ENFORCED': 'true',
    'POSTGRES_DSN': 'postgresql://arbitrage:arbitrage@localhost:5432/arbitrage',
    'REDIS_URL': 'redis://localhost:6380/0',
    'UPBIT_ACCESS_KEY': 'test_key',
    'UPBIT_SECRET_KEY': 'test_secret',
    'BINANCE_API_KEY': 'test_key',
    'BINANCE_API_SECRET': 'test_secret',
    'TELEGRAM_BOT_TOKEN': 'test_token',
    'TELEGRAM_CHAT_ID': 'test_id',
})

with patch('scripts.d98_live_preflight.CrossExchangePositionManager') as mock_pos, \
     patch('redis.from_url') as mock_redis, \
     patch('psycopg2.connect') as mock_pg:
    
    # Mock Redis
    mock_redis_client = MagicMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.get.return_value = b'ok'
    mock_redis_client.set.return_value = True
    mock_redis_client.delete.return_value = 1
    mock_redis.return_value = mock_redis_client
    
    # Mock Postgres
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)
    mock_conn.cursor.return_value = mock_cursor
    mock_pg.return_value = mock_conn
    
    # Mock Position Manager
    mock_position_manager = MagicMock()
    mock_position_manager.list_open_positions.return_value = []
    mock_pos.return_value = mock_position_manager
    
    # Run
    from scripts.d98_live_preflight import LivePreflightChecker
    checker = LivePreflightChecker(dry_run=False, enable_metrics=False, enable_alerts=False)
    result = checker.run_all_checks()
    
    # Print results
    print("\n=== CHECK RESULTS ===")
    for c in result.checks:
        status_emoji = "✅" if c["status"] == "PASS" else "❌"
        print(f"{status_emoji} {c['name']}: {c['status']}")
        if c['status'] != 'PASS':
            print(f"   Message: {c['message']}")
            print(f"   Details: {c.get('details', {})}")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total: {len(result.checks)}")
    print(f"PASS: {result.passed}")
    print(f"FAIL: {result.failed}")
    print(f"Ready: {result.is_ready()}")
