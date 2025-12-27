"""
Migration to add Magic Link authentication fields.

Run: docker exec ai_drive_backend python -m app.migrations.add_magic_links
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    """Add Magic Link fields to users table."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("Adding Magic Link authentication fields...")
        
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS magic_link_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS magic_link_expires TIMESTAMP",
            "CREATE INDEX IF NOT EXISTS idx_users_magic_link_token ON users(magic_link_token)",
        ]
        
        for migration_sql in migrations:
            try:
                conn.execute(text(migration_sql))
                conn.commit()
                print(f"✓ {migration_sql[:60]}...")
            except Exception as e:
                print(f"✗ Migration failed: {e}")
                conn.rollback()
        
        print("\n✅ Magic Link migration complete!")
        print("Users can now sign in without passwords using email magic links.")

if __name__ == "__main__":
    migrate()
