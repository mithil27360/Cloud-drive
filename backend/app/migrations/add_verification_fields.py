"""
Database migration to add email verification and security fields.

Run this script directly:
python -m app.migrations.add_verification_fields
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    """Add email verification and security fields to users table."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("Adding email verification and security fields to users table...")
        
        # Add fields if they don't exist
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP",
        ]
        
        for migration_sql in migrations:
            try:
                conn.execute(text(migration_sql))
                conn.commit()
                print(f"✓ {migration_sql[:50]}...")
            except Exception as e:
                print(f"✗ Migration failed: {e}")
                conn.rollback()
        
        print("\nMigration complete!")
        print("Note: Existing users are marked as unverified by default.")
        print("You may want to manually verify existing users:")
        print("  UPDATE users SET is_verified = TRUE WHERE created_at < NOW();")

if __name__ == "__main__":
    migrate()
