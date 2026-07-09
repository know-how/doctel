"""
Fix database schema - Add missing columns to ai_providers table
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.config import settings

db_url = settings.db_url
print(f'Connecting to: {db_url}')

# Create sync engine for DDL (use pymysql)
db_url = db_url.replace('+aiomysql', '+pymysql')
if 'pymysql' not in db_url:
    db_url = db_url.replace('mysql://', 'mysql+pymysql://')
engine = create_engine(db_url, pool_pre_ping=True)

# Columns to add (name, type, default)
columns = [
    ('provider_type', 'VARCHAR(64)', 'openai'),
    ('models_endpoint', 'VARCHAR(512)', ''),
    ('chat_endpoint', 'VARCHAR(512)', ''),
    ('messages_endpoint', 'VARCHAR(512)', ''),
    ('embeddings_endpoint', 'VARCHAR(512)', ''),
    ('health_endpoint', 'VARCHAR(512)', ''),
]

with engine.connect() as conn:
    # Check if table exists
    result = conn.execute(text("SHOW TABLES LIKE 'ai_providers'"))
    tables = [row[0] for row in result]
    print(f'Provider tables found: {tables}')
    
    if not tables:
        print("ERROR: ai_providers table not found!")
        sys.exit(1)
    
    # Check existing columns
    result = conn.execute(text('DESCRIBE ai_providers'))
    existing_cols = [row[0] for row in result]
    print(f'Existing columns: {existing_cols}')
    
    for col_name, col_type, default in columns:
        if col_name not in existing_cols:
            print(f'Adding column: {col_name}')
            sql = f"ALTER TABLE ai_providers ADD COLUMN {col_name} {col_type} DEFAULT '{default}'"
            conn.execute(text(sql))
            print(f'  -> Added successfully')
        else:
            print(f'Column {col_name} already exists')
    
    # Also add endpoint_type to ai_models if not exists
    result = conn.execute(text("SHOW TABLES LIKE 'ai_models'"))
    if [row[0] for row in result]:
        result = conn.execute(text('DESCRIBE ai_models'))
        model_cols = [row[0] for row in result]
        if 'endpoint_type' not in model_cols:
            print(f'Adding column: endpoint_type to ai_models')
            conn.execute(text("ALTER TABLE ai_models ADD COLUMN endpoint_type VARCHAR(32) DEFAULT 'chat'"))
            print(f'  -> Added successfully')
        else:
            print(f'Column endpoint_type already exists in ai_models')
    
    # Create sync_logs table if not exists
    result = conn.execute(text("SHOW TABLES LIKE 'sync_logs'"))
    if not [row[0] for row in result]:
        print('Creating table: sync_logs')
        conn.execute(text('''
            CREATE TABLE sync_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                provider_id VARCHAR(128) NOT NULL,
                sync_type VARCHAR(32) DEFAULT 'fetch',
                models_retrieved INT DEFAULT 0,
                models_added INT DEFAULT 0,
                models_removed INT DEFAULT 0,
                models_updated INT DEFAULT 0,
                models_unchanged INT DEFAULT 0,
                status VARCHAR(32) DEFAULT 'success',
                error_message TEXT DEFAULT '',
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sync_provider_time (provider_id, synced_at)
            )
        '''))
        print('  -> Created successfully')
    else:
        print('Table sync_logs already exists')
    
    conn.commit()
    print('\nMigration complete!')
    
    # Verify
    result = conn.execute(text('DESCRIBE ai_providers'))
    all_cols = [row[0] for row in result]
    print(f'\nFinal ai_providers columns: {all_cols}')
