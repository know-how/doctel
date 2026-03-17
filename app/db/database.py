from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_async_engine(settings.db_url, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def init_db():
    from .models import User
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite(conn)
    
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(username="admin", ec_number="admin", email="", display_name="Admin", role="admin")
            session.add(admin)
            await session.commit()


async def _ensure_sessions_updated_at(conn) -> None:
    res = await conn.exec_driver_sql("PRAGMA table_info(sessions)")
    cols = [dict(r) for r in res.mappings().all()]
    has = any((c.get("name") == "updated_at") for c in cols)
    if not has:
        await conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN updated_at DATETIME")
    try:
        await conn.exec_driver_sql("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS sessions_updated_at_insert
            AFTER INSERT ON sessions
            WHEN NEW.updated_at IS NULL
            BEGIN
                UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE rowid = NEW.rowid;
            END;
            """
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS sessions_updated_at_update
            AFTER UPDATE ON sessions
            BEGIN
                UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE rowid = NEW.rowid;
            END;
            """
        )
    except Exception:
        pass

async def _migrate_sqlite(conn):
    def _col_exists(cols, name: str) -> bool:
        return any((c.get("name") == name) for c in cols)

    res = await conn.exec_driver_sql("PRAGMA table_info(documents)")
    cols = [dict(r) for r in res.mappings().all()]
    statements = []
    if not _col_exists(cols, "status"):
        statements.append("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'uploaded'")
    if not _col_exists(cols, "ingest_step"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_step TEXT DEFAULT 'uploaded'")
    if not _col_exists(cols, "ingest_percent"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_percent INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingest_message"):
        statements.append("ALTER TABLE documents ADD COLUMN ingest_message TEXT DEFAULT ''")
    if not _col_exists(cols, "error_message"):
        statements.append("ALTER TABLE documents ADD COLUMN error_message TEXT DEFAULT ''")
    if not _col_exists(cols, "detected_type"):
        statements.append("ALTER TABLE documents ADD COLUMN detected_type TEXT DEFAULT ''")
    if not _col_exists(cols, "updated_at"):
        statements.append("ALTER TABLE documents ADD COLUMN updated_at TEXT")
    if not _col_exists(cols, "uploaded_by_user_id"):
        statements.append("ALTER TABLE documents ADD COLUMN uploaded_by_user_id INTEGER")
    if not _col_exists(cols, "auto_project_confidence"):
        statements.append("ALTER TABLE documents ADD COLUMN auto_project_confidence REAL DEFAULT 0")
    if not _col_exists(cols, "needs_project_review"):
        statements.append("ALTER TABLE documents ADD COLUMN needs_project_review INTEGER DEFAULT 0")
    if not _col_exists(cols, "tags_json"):
        statements.append("ALTER TABLE documents ADD COLUMN tags_json TEXT DEFAULT '[]'")
    if not _col_exists(cols, "analysis_ready"):
        statements.append("ALTER TABLE documents ADD COLUMN analysis_ready INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_started"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_started INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_completed"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_completed INTEGER DEFAULT 0")
    if not _col_exists(cols, "ingestion_failed"):
        statements.append("ALTER TABLE documents ADD COLUMN ingestion_failed INTEGER DEFAULT 0")

    for stmt in statements:
        await conn.exec_driver_sql(stmt)

    res2 = await conn.exec_driver_sql("PRAGMA table_info(doc_analysis)")
    cols2 = [dict(r) for r in res2.mappings().all()]
    statements2 = []
    if not _col_exists(cols2, "action_items_json"):
        statements2.append("ALTER TABLE doc_analysis ADD COLUMN action_items_json TEXT")
    if not _col_exists(cols2, "decisions_json"):
        statements2.append("ALTER TABLE doc_analysis ADD COLUMN decisions_json TEXT")
    for stmt in statements2:
        await conn.exec_driver_sql(stmt)

    res3 = await conn.exec_driver_sql("PRAGMA table_info(sessions)")
    cols3 = [dict(r) for r in res3.mappings().all()]
    statements3 = []
    if not _col_exists(cols3, "session_uuid"):
        statements3.append("ALTER TABLE sessions ADD COLUMN session_uuid TEXT")
    if not _col_exists(cols3, "model_name"):
        statements3.append("ALTER TABLE sessions ADD COLUMN model_name TEXT")
    if not _col_exists(cols3, "document_id"):
        statements3.append("ALTER TABLE sessions ADD COLUMN document_id INTEGER")
    if not _col_exists(cols3, "title"):
        statements3.append("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
    if not _col_exists(cols3, "scope"):
        statements3.append("ALTER TABLE sessions ADD COLUMN scope TEXT DEFAULT 'document'")
    if not _col_exists(cols3, "archived"):
        statements3.append("ALTER TABLE sessions ADD COLUMN archived INTEGER DEFAULT 0")
    for stmt in statements3:
        await conn.exec_driver_sql(stmt)
    await _ensure_sessions_updated_at(conn)

    res_users = await conn.exec_driver_sql("PRAGMA table_info(users)")
    user_cols = [dict(r) for r in res_users.mappings().all()]
    user_statements = []
    if not _col_exists(user_cols, "ec_number"):
        user_statements.append("ALTER TABLE users ADD COLUMN ec_number TEXT")
    if not _col_exists(user_cols, "email"):
        user_statements.append("ALTER TABLE users ADD COLUMN email TEXT")
    if not _col_exists(user_cols, "display_name"):
        user_statements.append("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    for stmt in user_statements:
        await conn.exec_driver_sql(stmt)

    res4 = await conn.exec_driver_sql("PRAGMA table_info(messages)")
    cols4 = [dict(r) for r in res4.mappings().all()]
    statements4 = []
    if not _col_exists(cols4, "status"):
        statements4.append("ALTER TABLE messages ADD COLUMN status TEXT DEFAULT 'done'")
    for stmt in statements4:
        await conn.exec_driver_sql(stmt)

    try:
        await conn.exec_driver_sql(
            "DELETE FROM project_members WHERE id NOT IN (SELECT MIN(id) FROM project_members GROUP BY project_id, user_id)"
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_members_project_user ON project_members(project_id, user_id)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS document_links (id INTEGER PRIMARY KEY, from_document_id INTEGER, to_document_id INTEGER, relation TEXT, confidence REAL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS diagrams (id INTEGER PRIMARY KEY, project_id INTEGER, session_id INTEGER, title TEXT, mermaid TEXT, drawing_prompt TEXT, version INTEGER DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value_json TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_by_user_id INTEGER)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS settings_audit (id INTEGER PRIMARY KEY, key TEXT, old_value_json TEXT, new_value_json TEXT, changed_by_user_id INTEGER, changed_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass

    try:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS user_identity_providers (id INTEGER PRIMARY KEY, user_id INTEGER, provider TEXT, identity TEXT, verified INTEGER DEFAULT 0, last_login_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    except Exception:
        pass
    try:
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_provider_identity ON user_identity_providers(provider, identity)"
        )
    except Exception:
        pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
