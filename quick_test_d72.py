import sys
sys.path.insert(0, '.')

from arbitrage.redis_keyspace import KeyBuilder, KeyDomain, KeyspaceValidator
import redis

print("=" * 70)
print("D72-2 QUICK TEST")
print("=" * 70)

# Connect to Redis
r = redis.Redis(host='localhost', port=6380, db=0)
r.ping()
print("\n✅ Redis connected")

# Test KeyBuilder
kb = KeyBuilder('development', 'test_session_123')

# Create test keys
session_key = kb.build_session_key()
pos_btc = kb.build_position_key('BTC')
pos_eth = kb.build_position_key('ETH')
guard_key = kb.build_guard_key()
portfolio_key = kb.build_portfolio_key()

keys = [session_key, pos_btc, pos_eth, guard_key, portfolio_key]

print("\n[TEST] Key Creation:")
for key in keys:
    valid = KeyBuilder.validate_key(key)
    print(f"  {'✅' if valid else '❌'} {key}")
    if not valid:
        sys.exit(1)

# Test Redis operations
print("\n[TEST] Redis Operations:")
for key in keys:
    r.set(key, f"test_value_{key}")
print(f"  ✅ Set {len(keys)} keys")

# Verify
for key in keys:
    value = r.get(key)
    if not value:
        print(f"  ❌ Key not found: {key}")
        sys.exit(1)
print(f"  ✅ Retrieved {len(keys)} keys")

# Audit
audit = KeyspaceValidator.audit_keys(r)
print(f"\n[AUDIT]")
print(f"  Total keys: {audit['total_keys']}")
print(f"  Valid: {audit['valid_keys']}")
print(f"  Invalid: {audit['invalid_keys']}")
print(f"  Compliance: {audit['compliance_rate']:.1f}%")

if audit['compliance_rate'] < 100.0:
    print(f"\n❌ Compliance test FAILED")
    sys.exit(1)

# Cleanup
for key in keys:
    r.delete(key)
print(f"\n✅ Cleaned up {len(keys)} keys")

# Test StateStore integration
from arbitrage.state_store import StateStore

store = StateStore(redis_client=r, db_conn=None, env='development')
test_session = 'integration_test_123'

state_data = {
    'session': {'id': test_session, 'mode': 'paper'},
    'positions': {'BTC': {'size': 0.5}},
    'metrics': {'pnl': 100.0},
    'risk_guard': {'daily_loss': 0.0}
}

print("\n[TEST] StateStore Integration:")
success = store.save_state_to_redis(test_session, state_data)
if not success:
    print("  ❌ Failed to save state")
    sys.exit(1)
print("  ✅ State saved")

# Verify keys
kb2 = KeyBuilder('development', test_session)
pattern = kb2.get_all_session_keys_pattern()
saved_keys = list(r.scan_iter(match=pattern))
print(f"  Keys created: {len(saved_keys)}")

all_valid = True
for key in saved_keys:
    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
    valid = KeyBuilder.validate_key(key_str)
    if not valid:
        print(f"  ❌ Invalid key: {key_str}")
        all_valid = False

if not all_valid:
    sys.exit(1)

print("  ✅ All StateStore keys valid")

# Cleanup
store.delete_state_from_redis(test_session)
print("  ✅ StateStore cleaned up")

print("\n" + "=" * 70)
print("🎉 D72-2 QUICK TEST: ALL PASS")
print("=" * 70)
