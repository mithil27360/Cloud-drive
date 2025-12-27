
from sqlalchemy import create_engine, text
from app.config import settings

def run_migration():
    print("Running migration...")
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # Add can_upload to users
        try:
            print("Adding can_upload column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_upload BOOLEAN DEFAULT TRUE;"))
            print("Column added.")
        except Exception as e:
            print(f"Error adding column (might exist): {e}")

        # Create audit_logs table
        try:
            print("Creating audit_logs table...")
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
                actor_id INTEGER,
                action VARCHAR,
                target_id INTEGER,
                target_type VARCHAR,
                metadata_json VARCHAR,
                FOREIGN KEY (actor_id) REFERENCES users(id)
            );
            """))
            print("Table created.")
        except Exception as e:
            print(f"Error creating table: {e}")

if __name__ == "__main__":
    run_migration()
