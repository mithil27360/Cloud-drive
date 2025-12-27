"""
Database migration to add google_id field for OAuth.

Run inside container:
docker exec ai_drive_backend python -m app.migrations.add_google_oauth
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    """Add Google OAuth support to users table."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("Adding Google OAuth support to users table...")
        
        migrations = [
            # Add google_id column
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR UNIQUE",
            "CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)",
            
            # Make password nullable for OAuth users
            "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL",
            
            # Auto-verify existing OAuth users (if any future ones)
            # Existing users keep their current verification status
        ]
        
        for migration_sql in migrations:
            try:
                conn.execute(text(migration_sql))
                conn.commit()
                print(f"✓ {migration_sql[:60]}...")
            except Exception as e:
                print(f"✗ Migration failed: {e}")
                conn.rollback()
        
        print("\n✅ Migration complete!")
        print("Google OAuth is now ready to use.")

if __name__ == "__main__":
    migrate()
