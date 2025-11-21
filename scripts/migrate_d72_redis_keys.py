#!/usr/bin/env python3
"""
D72-2: Redis Key Migration Script

기존의 임의로 생성된 Redis key들을 표준화된 형식으로 마이그레이션.

Before: arbitrage:state:{env}:{session_id}:{category}
After:  arbitrage:{env}:{session_id}:{domain}:{symbol}:{field}
"""

import sys
import os
import re
from typing import Dict, List, Tuple, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from arbitrage.redis_keyspace import KeyBuilder, KeyDomain, KeyspaceValidator


class RedisKeyMigrator:
    """Migrate old Redis keys to new standardized format"""
    
    def __init__(self, redis_client: redis.Redis, env: str = 'development'):
        self.redis = redis_client
        self.env = env
        self.migration_log = []
        
    def _parse_old_key(self, key: str) -> Optional[Dict[str, str]]:
        """
        Parse old key format
        
        Old format: arbitrage:state:{env}:{session_id}:{category}
        """
        # Old pattern from D70
        old_pattern = r'^arbitrage:state:([^:]+):([^:]+):(.+)$'
        match = re.match(old_pattern, key)
        
        if match:
            return {
                'env': match.group(1),
                'session_id': match.group(2),
                'category': match.group(3)
            }
        
        return None
    
    def _map_old_to_new(self, old_key: str) -> Optional[str]:
        """
        Map old key format to new KeyBuilder format
        
        Args:
            old_key: Old format key
        
        Returns:
            New format key or None if can't migrate
        """
        parsed = self._parse_old_key(old_key)
        if not parsed:
            return None
        
        env = parsed['env']
        session_id = parsed['session_id']
        category = parsed['category']
        
        # Create KeyBuilder for this session
        try:
            kb = KeyBuilder(env=env, session_id=session_id)
        except ValueError:
            return None
        
        # Map category to new key
        if category == 'session':
            return kb.build_session_key()
        elif category in ['positions', 'position']:
            return kb.build(KeyDomain.STATE, field='positions')
        elif category == 'metrics':
            return kb.build(KeyDomain.METRICS, field='all')
        elif category == 'risk_guard':
            return kb.build_guard_key()
        elif category == 'orders':
            return kb.build(KeyDomain.STATE, field='orders')
        else:
            # Generic mapping
            return kb.build(KeyDomain.STATE, field=category)
    
    def scan_old_keys(self, pattern: str = "arbitrage:state:*") -> List[str]:
        """
        Scan for old format keys
        
        Args:
            pattern: Redis SCAN pattern
        
        Returns:
            List of old format keys
        """
        old_keys = []
        
        for key in self.redis.scan_iter(match=pattern):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            
            # Check if it's old format
            if not KeyBuilder.validate_key(key_str):
                old_keys.append(key_str)
        
        return old_keys
    
    def migrate_key(self, old_key: str, dry_run: bool = False) -> Tuple[bool, str]:
        """
        Migrate a single key
        
        Args:
            old_key: Old format key
            dry_run: If True, don't actually rename
        
        Returns:
            (success, message)
        """
        new_key = self._map_old_to_new(old_key)
        
        if not new_key:
            return False, f"Could not map key: {old_key}"
        
        if old_key == new_key:
            return True, f"Already migrated: {old_key}"
        
        if dry_run:
            return True, f"DRY RUN: {old_key} -> {new_key}"
        
        try:
            # Get value
            value = self.redis.get(old_key)
            
            if value is None:
                return False, f"Key not found: {old_key}"
            
            # Set new key
            self.redis.set(new_key, value)
            
            # Copy TTL if exists
            ttl = self.redis.ttl(old_key)
            if ttl > 0:
                self.redis.expire(new_key, ttl)
            
            # Delete old key
            self.redis.delete(old_key)
            
            self.migration_log.append({
                'old_key': old_key,
                'new_key': new_key,
                'status': 'success'
            })
            
            return True, f"Migrated: {old_key} -> {new_key}"
        
        except Exception as e:
            return False, f"Error migrating {old_key}: {e}"
    
    def migrate_all(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Migrate all old format keys
        
        Args:
            dry_run: If True, don't actually rename
        
        Returns:
            Migration report
        """
        print("\n" + "=" * 70)
        print("D72-2 REDIS KEY MIGRATION")
        print("=" * 70)
        
        # Scan old keys
        print("\n[STEP 1] Scanning for old format keys...")
        old_keys = self.scan_old_keys()
        print(f"Found {len(old_keys)} old format keys")
        
        if not old_keys:
            print("✅ No migration needed - all keys already use new format")
            return {
                'total': 0,
                'migrated': 0,
                'failed': 0,
                'skipped': 0
            }
        
        # Show samples
        print(f"\nFirst {min(10, len(old_keys))} old keys:")
        for key in old_keys[:10]:
            new_key = self._map_old_to_new(key)
            print(f"  {key}")
            print(f"    -> {new_key}")
        
        if dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be made")
        
        # Migrate
        print(f"\n[STEP 2] Migrating {len(old_keys)} keys...")
        
        success_count = 0
        failed_count = 0
        
        for i, old_key in enumerate(old_keys, 1):
            success, msg = self.migrate_key(old_key, dry_run=dry_run)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                print(f"  ❌ {msg}")
            
            # Progress
            if i % 10 == 0 or i == len(old_keys):
                print(f"  Progress: {i}/{len(old_keys)} ({success_count} ok, {failed_count} failed)")
        
        # Report
        print("\n" + "=" * 70)
        print("MIGRATION REPORT")
        print("=" * 70)
        print(f"Total keys:     {len(old_keys)}")
        print(f"Migrated:       {success_count}")
        print(f"Failed:         {failed_count}")
        print(f"Success rate:   {success_count / len(old_keys) * 100:.1f}%")
        
        return {
            'total': len(old_keys),
            'migrated': success_count,
            'failed': failed_count,
            'skipped': 0
        }
    
    def audit_post_migration(self) -> Dict[str, any]:
        """Run audit after migration"""
        print("\n" + "=" * 70)
        print("POST-MIGRATION AUDIT")
        print("=" * 70)
        
        audit = KeyspaceValidator.audit_keys(self.redis)
        
        print(f"\nTotal keys:        {audit['total_keys']}")
        print(f"Valid keys:        {audit['valid_keys']}")
        print(f"Invalid keys:      {audit['invalid_keys']}")
        print(f"Compliance rate:   {audit['compliance_rate']:.1f}%")
        
        if audit['invalid_keys'] > 0:
            print(f"\nInvalid keys (first 10):")
            for key in audit['invalid_key_list'][:10]:
                print(f"  - {key}")
        
        print(f"\nDomain breakdown:")
        for domain, count in audit['domain_breakdown'].items():
            print(f"  {domain:15s}: {count:5d}")
        
        print(f"\nEnvironment breakdown:")
        for env, count in audit['env_breakdown'].items():
            print(f"  {env:15s}: {count:5d}")
        
        return audit


def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate Redis keys to D72-2 standard format')
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6380, help='Redis port')
    parser.add_argument('--db', type=int, default=0, help='Redis database')
    parser.add_argument('--env', default='development', choices=['development', 'staging', 'production'], help='Environment')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no changes)')
    
    args = parser.parse_args()
    
    # Connect to Redis
    print(f"Connecting to Redis at {args.host}:{args.port} (db={args.db})")
    redis_client = redis.Redis(host=args.host, port=args.port, db=args.db, decode_responses=False)
    
    try:
        redis_client.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return 1
    
    # Create migrator
    migrator = RedisKeyMigrator(redis_client, env=args.env)
    
    # Run migration
    report = migrator.migrate_all(dry_run=args.dry_run)
    
    if not args.dry_run:
        # Run audit
        audit = migrator.audit_post_migration()
        
        # Final check
        if audit['compliance_rate'] < 100.0:
            print("\n⚠️  WARNING: Some keys still don't comply with new format")
            return 1
    
    print("\n✅ Migration completed successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
