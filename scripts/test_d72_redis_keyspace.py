#!/usr/bin/env python3
"""
D72-2: Redis Keyspace Test

KeyBuilder, TTL 정책, StateStore 통합 테스트
"""

import sys
import os
import time
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from arbitrage.redis_keyspace import KeyBuilder, KeyDomain, TTLPolicy, KeyspaceValidator
from arbitrage.state_store import StateStore


class RedisKeyspaceTests:
    """Redis keyspace normalization tests"""
    
    def __init__(self, redis_client: redis.Redis, env: str = 'development'):
        self.redis = redis_client
        self.env = env
        self.test_session_id = f"test_session_{int(time.time())}"
        self.kb = KeyBuilder(env=env, session_id=self.test_session_id)
        
    def test_key_builder_basic(self) -> bool:
        """Test basic KeyBuilder functionality"""
        print("\n[TEST 1] KeyBuilder Basic")
        
        # Test key generation
        session_key = self.kb.build_session_key()
        position_key = self.kb.build_position_key('BTC')
        guard_key = self.kb.build_guard_key()
        portfolio_key = self.kb.build_portfolio_key()
        
        tests = [
            ('Session key', session_key),
            ('Position key (BTC)', position_key),
            ('Guard key', guard_key),
            ('Portfolio key', portfolio_key)
        ]
        
        all_valid = True
        for name, key in tests:
            valid = KeyBuilder.validate_key(key)
            print(f"  {name}: {key}")
            print(f"    Valid: {valid}")
            
            if not valid:
                all_valid = False
        
        if all_valid:
            print("  ✅ All keys valid")
        else:
            print("  ❌ Some keys invalid")
        
        return all_valid
    
    def test_key_parsing(self) -> bool:
        """Test key parsing"""
        print("\n[TEST 2] Key Parsing")
        
        test_key = self.kb.build_position_key('ETH')
        parsed = KeyBuilder.parse_key(test_key)
        
        print(f"  Key: {test_key}")
        print(f"  Parsed: {parsed}")
        
        expected = {
            'env': self.env,
            'session_id': self.test_session_id,
            'domain': 'state',
            'symbol': 'ETH',
            'field': 'position'
        }
        
        match = parsed == expected
        if match:
            print("  ✅ Parsing correct")
        else:
            print(f"  ❌ Parsing mismatch")
            print(f"    Expected: {expected}")
            print(f"    Got: {parsed}")
        
        return match
    
    def test_ttl_policy(self) -> bool:
        """Test TTL policy"""
        print("\n[TEST 3] TTL Policy")
        
        tests = [
            (KeyDomain.STATE, None, "STATE should have no TTL"),
            (KeyDomain.COOLDOWN, 600, "COOLDOWN should have 600s TTL"),
            (KeyDomain.WS, 30, "WS should have 30s TTL"),
            (KeyDomain.GUARD, None, "GUARD should have no TTL"),
        ]
        
        all_pass = True
        for domain, expected_ttl, desc in tests:
            actual_ttl = TTLPolicy.get_ttl(domain)
            match = actual_ttl == expected_ttl
            
            status = "✅" if match else "❌"
            print(f"  {status} {desc}")
            print(f"      Expected: {expected_ttl}, Got: {actual_ttl}")
            
            if not match:
                all_pass = False
        
        return all_pass
    
    def test_redis_operations(self) -> bool:
        """Test Redis set/get with KeyBuilder"""
        print("\n[TEST 4] Redis Operations")
        
        # Create test keys and values
        test_data = [
            (self.kb.build_session_key(), '{"session_id": "test"}'),
            (self.kb.build_position_key('BTC'), '{"symbol": "BTC", "size": 0.5}'),
            (self.kb.build_metrics_key('ETH', 'pnl'), '{"pnl": 123.45}'),
        ]
        
        # Set keys
        for key, value in test_data:
            self.redis.set(key, value)
            print(f"  Set: {key}")
        
        # Get and verify
        all_pass = True
        for key, expected_value in test_data:
            actual_value = self.redis.get(key)
            if actual_value:
                actual_value = actual_value.decode('utf-8')
            
            match = actual_value == expected_value
            if not match:
                print(f"  ❌ Mismatch for {key}")
                print(f"      Expected: {expected_value}")
                print(f"      Got: {actual_value}")
                all_pass = False
        
        if all_pass:
            print("  ✅ All Redis operations successful")
        
        # Cleanup
        for key, _ in test_data:
            self.redis.delete(key)
        
        return all_pass
    
    def test_statestore_integration(self) -> bool:
        """Test StateStore with KeyBuilder"""
        print("\n[TEST 5] StateStore Integration")
        
        # Create StateStore with PostgreSQL disabled
        store = StateStore(redis_client=self.redis, db_conn=None, env=self.env)
        
        # Create test state
        test_state = {
            'session': {
                'session_id': self.test_session_id,
                'start_time': time.time(),
                'mode': 'paper'
            },
            'positions': {
                'BTC': {'size': 0.5, 'entry_price': 50000}
            },
            'metrics': {
                'total_pnl': 123.45,
                'trades': 5
            },
            'risk_guard': {
                'daily_loss': 0.0,
                'max_loss': 1000.0
            }
        }
        
        # Save to Redis
        success = store.save_state_to_redis(self.test_session_id, test_state)
        
        if not success:
            print("  ❌ Failed to save state")
            return False
        
        print("  ✅ State saved to Redis")
        
        # Verify keys exist
        pattern = f"arbitrage:{self.env}:{self.test_session_id}:*"
        keys = list(self.redis.scan_iter(match=pattern))
        
        print(f"  Keys created: {len(keys)}")
        for key in keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            valid = KeyBuilder.validate_key(key_str)
            status = "✅" if valid else "❌"
            print(f"    {status} {key_str}")
            
            if not valid:
                return False
        
        # Load state
        loaded_state = store.load_state_from_redis(self.test_session_id)
        
        if not loaded_state:
            print("  ❌ Failed to load state")
            return False
        
        print("  ✅ State loaded from Redis")
        
        # Cleanup
        store.delete_state_from_redis(self.test_session_id)
        print("  ✅ State cleaned up")
        
        return True
    
    def test_keyspace_audit(self) -> bool:
        """Test keyspace compliance audit"""
        print("\n[TEST 6] Keyspace Audit")
        
        # Create some test keys
        test_keys = [
            self.kb.build_session_key(),
            self.kb.build_position_key('BTC'),
            self.kb.build_position_key('ETH'),
            self.kb.build_guard_key(),
            self.kb.build_portfolio_key(),
        ]
        
        for key in test_keys:
            self.redis.set(key, "test_value")
        
        # Run audit
        audit = KeyspaceValidator.audit_keys(self.redis)
        
        print(f"  Total keys: {audit['total_keys']}")
        print(f"  Valid keys: {audit['valid_keys']}")
        print(f"  Invalid keys: {audit['invalid_keys']}")
        print(f"  Compliance: {audit['compliance_rate']:.1f}%")
        
        print(f"\n  Domain breakdown:")
        for domain, count in audit['domain_breakdown'].items():
            print(f"    {domain}: {count}")
        
        # Cleanup
        for key in test_keys:
            self.redis.delete(key)
        
        if audit['compliance_rate'] == 100.0:
            print("  ✅ 100% compliance")
            return True
        else:
            print(f"  ❌ Compliance rate: {audit['compliance_rate']:.1f}%")
            return False
    
    def test_multisymbol_domain_separation(self) -> bool:
        """Test domain separation for multisymbol"""
        print("\n[TEST 7] Multisymbol Domain Separation")
        
        symbols = ['BTC', 'ETH', 'XRP']
        
        # Create keys for each symbol
        for symbol in symbols:
            pos_key = self.kb.build_position_key(symbol)
            metrics_key = self.kb.build_metrics_key(symbol, 'pnl')
            cooldown_key = self.kb.build_cooldown_key(symbol)
            
            self.redis.set(pos_key, f'{{"symbol": "{symbol}"}}')
            self.redis.set(metrics_key, f'{{"pnl": 100}}')
            self.redis.set(cooldown_key, "1")
        
        # Verify separation
        all_pass = True
        for symbol in symbols:
            pos_key = self.kb.build_position_key(symbol)
            value = self.redis.get(pos_key)
            
            if value:
                value = value.decode('utf-8')
                if symbol not in value:
                    print(f"  ❌ Symbol {symbol} data mismatch")
                    all_pass = False
            else:
                print(f"  ❌ Symbol {symbol} key not found")
                all_pass = False
        
        if all_pass:
            print(f"  ✅ All {len(symbols)} symbols properly separated")
        
        # Cleanup
        for symbol in symbols:
            self.redis.delete(self.kb.build_position_key(symbol))
            self.redis.delete(self.kb.build_metrics_key(symbol, 'pnl'))
            self.redis.delete(self.kb.build_cooldown_key(symbol))
        
        return all_pass


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("D72-2 REDIS KEYSPACE TESTS")
    print("=" * 70)
    
    # Connect to Redis
    redis_client = redis.Redis(host='localhost', port=6380, db=0, decode_responses=False)
    
    try:
        redis_client.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return 1
    
    # Create test suite
    tests = RedisKeyspaceTests(redis_client, env='development')
    
    # Run tests
    test_methods = [
        tests.test_key_builder_basic,
        tests.test_key_parsing,
        tests.test_ttl_policy,
        tests.test_redis_operations,
        tests.test_statestore_integration,
        tests.test_keyspace_audit,
        tests.test_multisymbol_domain_separation,
    ]
    
    results = []
    for test_method in test_methods:
        try:
            result = test_method()
            results.append((test_method.__name__, result))
        except Exception as e:
            print(f"\n❌ Exception in {test_method.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_method.__name__, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
