"""
Run migration 010_add_vision_2_0_enterprise_tables.sql against MySQL.
Follows the same pattern as fix_database_schema.py (sync pymysql engine).
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.config import settings

db_url = settings.db_url
print(f'Connecting to: {db_url}')

# Use sync pymysql engine for DDL operations
db_url = db_url.replace('+aiomysql', '+pymysql')
if 'pymysql' not in db_url:
    db_url = db_url.replace('mysql://', 'mysql+pymysql://')
engine = create_engine(db_url, pool_pre_ping=True)

# Read migration SQL file
sql_file = 'migrations/010_add_vision_2_0_enterprise_tables.sql'
with open(sql_file, 'r', encoding='utf-8') as f:
    sql_content = f.read()

# Split into individual statements
statements = []
current = []
for line in sql_content.split('\n'):
    stripped = line.strip()
    # Skip comments and empty lines
    if stripped.startswith('--') or stripped.startswith('#') or not stripped:
        continue
    current.append(line)
    if stripped.endswith(';'):
        statements.append('\n'.join(current))
        current = []

success_count = 0
error_count = 0

with engine.connect() as conn:
    for i, stmt in enumerate(statements):
        stmt_clean = stmt.strip()
        if not stmt_clean:
            continue
        try:
            conn.execute(text(stmt_clean))
            conn.commit()
            # Print first 80 chars of the statement
            preview = stmt_clean[:80].replace('\n', ' ')
            print(f'  ✓  [{i+1:02d}] {preview}...')
            success_count += 1
        except Exception as e:
            error_msg = str(e)
            # Only report as error if it's not "already exists"
            if "already exists" in error_msg or "Duplicate" in error_msg:
                preview = stmt_clean[:80].replace('\n', ' ')
                print(f'  ~  [{i+1:02d}] Already exists: {preview}...')
                success_count += 1
            else:
                preview = stmt_clean[:80].replace('\n', ' ')
                print(f'  ✗  [{i+1:02d}] ERROR: {preview}...')
                print(f'      {error_msg}')
                error_count += 1

print(f'\n{"="*60}')
print(f'Migration complete!')
print(f'  Statements executed: {success_count}')
print(f'  Errors: {error_count}')
print(f'{"="*60}')
