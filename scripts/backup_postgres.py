#!/usr/bin/env python3
"""
D72-3: PostgreSQL Backup Script

pg_dump 기반 백업 + 압축 + 로테이션
"""

import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path


class PostgresBackup:
    """PostgreSQL backup manager"""
    
    def __init__(
        self,
        backup_dir: str = 'backups/postgres',
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'arbitrage',
        user: str = 'arbitrage',
        password: str = 'arbitrage',
        retention_days: int = 30
    ):
        self.backup_dir = Path(backup_dir)
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.retention_days = retention_days
        
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self) -> str:
        """
        Create PostgreSQL backup using pg_dump
        
        Returns:
            Path to compressed backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'arbitrage_backup_{timestamp}.sql'
        backup_path = self.backup_dir / backup_filename
        compressed_path = self.backup_dir / f'{backup_filename}.gz'
        
        print(f"\n[BACKUP] Creating backup: {backup_filename}")
        
        # pg_dump command
        cmd = [
            'docker', 'exec', 'arbitrage-postgres',
            'pg_dump',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-d', self.database,
            '--no-password',  # Use PGPASSWORD env var
            '-F', 'p',  # Plain text format
            '--verbose'
        ]
        
        # Set password environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = self.password
        
        try:
            # Run pg_dump
            print(f"  Running pg_dump...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"  ❌ pg_dump failed:")
                print(f"    {result.stderr}")
                return None
            
            # Write to file
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            
            backup_size = backup_path.stat().st_size
            print(f"  ✅ Backup created: {backup_size / 1024 / 1024:.2f} MB")
            
            # Compress
            print(f"  Compressing...")
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed file
            backup_path.unlink()
            
            compressed_size = compressed_path.stat().st_size
            ratio = (1 - compressed_size / backup_size) * 100
            print(f"  ✅ Compressed: {compressed_size / 1024 / 1024:.2f} MB ({ratio:.1f}% reduction)")
            
            return str(compressed_path)
        
        except Exception as e:
            print(f"  ❌ Backup failed: {e}")
            if backup_path.exists():
                backup_path.unlink()
            if compressed_path.exists():
                compressed_path.unlink()
            return None
    
    def rotate_backups(self):
        """
        Delete backups older than retention_days
        """
        print(f"\n[ROTATION] Cleaning up backups older than {self.retention_days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        total_size_freed = 0
        
        for backup_file in self.backup_dir.glob('arbitrage_backup_*.sql.gz'):
            # Parse timestamp from filename
            try:
                # Format: arbitrage_backup_YYYYMMDD_HHMMSS.sql.gz
                timestamp_str = backup_file.stem.split('_')[2] + '_' + backup_file.stem.split('_')[3]
                file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                
                if file_date < cutoff_date:
                    size = backup_file.stat().st_size
                    backup_file.unlink()
                    deleted_count += 1
                    total_size_freed += size
                    print(f"  🗑️  Deleted: {backup_file.name}")
            
            except Exception as e:
                print(f"  ⚠️  Could not process {backup_file.name}: {e}")
        
        if deleted_count > 0:
            print(f"  ✅ Deleted {deleted_count} old backups ({total_size_freed / 1024 / 1024:.2f} MB freed)")
        else:
            print(f"  ℹ️  No old backups to delete")
    
    def list_backups(self):
        """
        List all available backups
        """
        print(f"\n[BACKUPS] Available backups:")
        
        backups = sorted(self.backup_dir.glob('arbitrage_backup_*.sql.gz'), reverse=True)
        
        if not backups:
            print("  ℹ️  No backups found")
            return
        
        for backup_file in backups:
            size = backup_file.stat().st_size
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            age = datetime.now() - mtime
            
            print(f"  📦 {backup_file.name}")
            print(f"      Size: {size / 1024 / 1024:.2f} MB")
            print(f"      Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"      Age: {age.days} days")
    
    def restore_backup(self, backup_path: str):
        """
        Restore from backup
        
        Args:
            backup_path: Path to compressed backup file
        """
        print(f"\n[RESTORE] Restoring from backup: {backup_path}")
        
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            print(f"  ❌ Backup file not found: {backup_path}")
            return False
        
        # Decompress
        temp_sql_path = backup_file.with_suffix('')
        
        print(f"  Decompressing...")
        with gzip.open(backup_file, 'rb') as f_in:
            with open(temp_sql_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"  ✅ Decompressed")
        
        # Restore using psql
        print(f"  Restoring to database...")
        
        # WARNING: This will drop and recreate tables
        print(f"  ⚠️  WARNING: This will overwrite existing data!")
        
        # Copy file into container
        copy_cmd = [
            'docker', 'cp',
            str(temp_sql_path),
            f'arbitrage-postgres:/tmp/restore.sql'
        ]
        
        subprocess.run(copy_cmd, check=True)
        
        # Execute restore
        restore_cmd = [
            'docker', 'exec', 'arbitrage-postgres',
            'psql',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-d', self.database,
            '-f', '/tmp/restore.sql'
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.password
        
        result = subprocess.run(
            restore_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Remove temp file
        temp_sql_path.unlink()
        
        if result.returncode != 0:
            print(f"  ❌ Restore failed:")
            print(f"    {result.stderr}")
            return False
        
        print(f"  ✅ Restore completed")
        return True


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PostgreSQL backup management')
    parser.add_argument('action', choices=['backup', 'list', 'rotate', 'restore'], help='Action to perform')
    parser.add_argument('--restore-file', help='Backup file to restore from')
    parser.add_argument('--retention-days', type=int, default=30, help='Backup retention days')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("D72-3 POSTGRESQL BACKUP")
    print("=" * 70)
    
    backup_manager = PostgresBackup(retention_days=args.retention_days)
    
    if args.action == 'backup':
        backup_path = backup_manager.create_backup()
        if backup_path:
            print(f"\n✅ Backup completed: {backup_path}")
            # Auto-rotate after backup
            backup_manager.rotate_backups()
            return 0
        else:
            print(f"\n❌ Backup failed")
            return 1
    
    elif args.action == 'list':
        backup_manager.list_backups()
        return 0
    
    elif args.action == 'rotate':
        backup_manager.rotate_backups()
        return 0
    
    elif args.action == 'restore':
        if not args.restore_file:
            print("❌ --restore-file required for restore action")
            return 1
        
        success = backup_manager.restore_backup(args.restore_file)
        return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
