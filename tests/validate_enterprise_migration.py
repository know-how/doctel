"""
Enterprise Post-Migration Validation Script

Tests every component of the Enterprise Architecture stack
after the agent_memory schema migration.

Usage:
    cd doctel && .venv\Scripts\python tests/validate_enterprise_migration.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Bootstrap all SQLAlchemy models first so relationship() string refs resolve
from app.db import models as _m  # noqa: F401, E402
from app.db import job_models as _jm  # noqa: F401, E402
from app.db import enterprise_models as _em  # noqa: F401, E402

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

DB_HOST = 'localhost'
DB_PORT = 5432
DB_USER = 'doctel_app'
DB_PASS = 'DocTelTest2026'
DB_NAME = 'doctel'

db_url = settings.database_url or settings.db_url
engine = create_async_engine(db_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Test Framework ────────────────────────────────────────────────────────────

class TestSuite:
    def __init__(self):
        self.results = []

    def add(self, name, category, passed, elapsed_ms, error=None):
        self.results.append({
            "name": name, "category": category,
            "status": "PASS" if passed else "FAIL",
            "elapsed_ms": round(elapsed_ms, 1), "error": error,
        })

    def report(self):
        elapsed = time.time() - self.start
        passed = [r for r in self.results if r["status"] == "PASS"]
        failed = [r for r in self.results if r["status"] == "FAIL"]
        by_cat = {}
        for r in self.results:
            c = r["category"]
            by_cat.setdefault(c, {"total": 0, "passed": 0, "failed": 0})
            by_cat[c]["total"] += 1
            by_cat[c]["passed"] += r["status"] == "PASS"
            by_cat[c]["failed"] += r["status"] == "FAIL"
        return {
            "total_tests": len(self.results), "passed": len(passed),
            "failed": len(failed), "elapsed_sec": round(elapsed, 2),
            "by_category": by_cat, "results": self.results,
            "passed_tests": [r["name"] for r in passed],
            "failed_tests": [r["name"] for r in failed],
        }

    async def run(self, name, category, fn, *args, **kwargs):
        t0 = time.time()
        try:
            await fn(*args, **kwargs)
            elapsed = (time.time() - t0) * 1000
            self.add(name, category, True, elapsed)
            print(f"  [PASS] {name} ({elapsed:.0f}ms)")
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            self.add(name, category, False, elapsed, str(e))
            print(f"  [FAIL] {name}: {e}")


async def main():
    suite = TestSuite()
    suite.start = time.time()

    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASS, database=DB_NAME,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: DATABASE SCHEMA VALIDATION
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 1. DATABASE SCHEMA VALIDATION ===")

    async def _agent_memory_exists():
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='agent_memory'"
        )
        assert len(rows) == 1, "agent_memory table not found"

    async def _pk_is_integer():
        rows = await conn.fetch(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name='id'"
        )
        assert rows[0]['data_type'] == 'integer', f"PK type is {rows[0]['data_type']}"

    async def _has_agent_execution_id():
        rows = await conn.fetch(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name='agent_execution_id'"
        )
        assert rows[0]['is_nullable'] == 'NO'

    async def _has_key_column():
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name='key'"
        )
        assert len(rows) == 1, "column 'key' not found (was 'memory_key')"

    async def _has_value_json():
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name='value_json'"
        )
        assert len(rows) == 1

    async def _has_embedding():
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name='embedding'"
        )
        assert len(rows) == 1

    async def _fk_agent_executions():
        rows = await conn.fetch(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid='agent_memory'::regclass AND contype='f' "
            "AND conname LIKE '%agent_execution%'"
        )
        assert len(rows) >= 1

    async def _fk_sessions():
        rows = await conn.fetch(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid='agent_memory'::regclass AND contype='f' "
            "AND conname LIKE '%session%'"
        )
        assert len(rows) >= 1

    async def _all_5_indexes():
        rows = await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE tablename='agent_memory'"
        )
        expected = {'agent_memory_pkey', 'idx_agent_memory_lookup',
                     'idx_agent_memory_expiry', 'idx_agent_memory_session',
                     'idx_agent_memory_access'}
        missing = expected - {r['indexname'] for r in rows}
        assert not missing, f"Missing indexes: {missing}"

    async def _old_columns_dropped():
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='agent_memory' "
            "AND column_name IN ('memory_key','memory_value','scope_type','scope_id')"
        )
        assert len(rows) == 0, f"Old columns still exist: {[r['column_name'] for r in rows]}"

    async def _alembic_version():
        row = await conn.fetch("SELECT version_num FROM alembic_version")
        assert row[0]['version_num'] in ('d5e6f7a8b9c0', 'e6f7a8b9c0d1'), \
            f"Expected d5e6f7a8b9c0 or e6f7a8b9c0d1, got {row[0]['version_num']}"

    for fn in [_agent_memory_exists, _pk_is_integer, _has_agent_execution_id,
               _has_key_column, _has_value_json, _has_embedding,
               _fk_agent_executions, _fk_sessions, _all_5_indexes,
               _old_columns_dropped, _alembic_version]:
        await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "schema", fn)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: AGENT MEMORY CRUD
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 2. AGENT MEMORY CRUD ===")

    db = async_session()
    try:
        from app.services.agent_memory_service import AgentMemoryService, MemoryType
        from app.db.enterprise_models import Agent, AgentExecution
        from sqlalchemy import select

        agent = (await db.execute(select(Agent).limit(1))).scalar_one_or_none()
        if not agent:
            # Create a test agent for FK validation
            from app.db.enterprise_models import Agent as AgentModel
            agent = AgentModel(
                agent_id="test-val-agent",
                name="Validation Test Agent",
                agent_type="validation",
                is_active=True,
            )
            db.add(agent)
            await db.commit()
            await db.refresh(agent)

        exec_entry = AgentExecution(
            agent_id=agent.id, status="completed", duration_ms=0,
        )
        db.add(exec_entry)
        await db.commit()
        await db.refresh(exec_entry)
        exec_id = exec_entry.id

        mem_svc = AgentMemoryService(db)

        async def _store_memory():
            mem_id = await mem_svc.store_memory(
                agent_execution_id=exec_id, key="test_key",
                value={"test": "data", "query": "validation"},
                memory_type=MemoryType.EPISODIC.value,
                session_id=None,
            )
            assert mem_id is not None, "store_memory returned None"
            assert isinstance(mem_id, int)

        async def _search_memory():
            results = await mem_svc.search_memory(
                key="test_key", memory_type=MemoryType.EPISODIC.value, limit=10,
            )
            assert len(results) >= 1
            assert any(r.get("key") == "test_key" for r in results)

        async def _build_memory_context():
            ctx = await mem_svc.build_memory_context(session_id=-1, max_tokens=500)
            assert isinstance(ctx, str)

        async def _get_session_memories():
            results = await mem_svc.get_session_memories(session_id=-1, limit=5)
            assert isinstance(results, list)

        async def _promote_session_memories():
            count = await mem_svc.promote_session_memories(
                session_id=-1, target_type=MemoryType.EPISODIC.value,
            )
            assert isinstance(count, int)

        for fn in [_store_memory, _search_memory, _build_memory_context,
                   _get_session_memories, _promote_session_memories]:
            await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "agent_memory", fn)
    finally:
        await db.close()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 3: AGENT RUNTIME
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 3. AGENT RUNTIME ===")

    db2 = async_session()
    try:
        from app.services.agent_runtime_service import (
            AgentCoordinator, AgentRegistry, AgentType, select_agents_for_intent,
            AgentResult,
        )
        from sqlalchemy import select as sa_select
        from app.db.enterprise_models import AgentExecution

        async def _registry_load():
            reg = AgentRegistry(db2)
            await reg.load_from_db()
            agents = reg.get_all_agents()
            assert len(agents) >= 10

        async def _registry_get_agent():
            reg = AgentRegistry(db2)
            await reg.load_from_db()
            for at in [AgentType.RETRIEVAL_AGENT, AgentType.GRAPH_AGENT,
                       AgentType.ASSET_AGENT, AgentType.MEETING_AGENT,
                       AgentType.RISK_AGENT, AgentType.POLICY_AGENT]:
                a = reg.get_agent(at)
                assert a is not None, f"Agent {at.value} not found"
                assert a.get("agent_id") == at.value

        async def _coordinator_initialize():
            coord = AgentCoordinator(db2)
            await coord.initialize()
            assert len(coord.registry.get_all_agents()) >= 10

        async def _execute_chat_plan():
            coord = AgentCoordinator(db2)
            await coord.initialize()
            bundle = await coord.execute_agent_plan(
                intent="chat", user_query="What is DocTel?", session_id=None,
            )
            assert len(bundle.agent_results) > 0

        async def _execute_meeting_plan():
            coord = AgentCoordinator(db2)
            await coord.initialize()
            bundle = await coord.execute_agent_plan(
                intent="meeting_analysis",
                user_query="Summarize this meeting about CRM",
                session_id=None,
                audio_transcript="Team discussed CRM. John will update API by Friday.",
            )
            assert bundle.to_dict().get("agents_executed", 0) > 0

        async def _select_agents():
            agents = select_agents_for_intent("policy_review")
            assert AgentType.POLICY_AGENT in agents
            assert AgentType.RISK_AGENT in agents

        async def _store_agent_findings():
            coord = AgentCoordinator(db2)
            await coord.initialize()
            result = AgentResult(
                agent_type=AgentType.SUMMARY_AGENT, status="completed",
                duration_ms=100, summary="Test summary",
                entities=["ZETDC", "CRM"],
                key_findings=["Finding 1", "Finding 2"],
            )
            await coord._store_agent_findings(result, session_id=-1, execution_id=1)
            # Should not throw

        for fn in [_registry_load, _registry_get_agent, _coordinator_initialize,
                   _execute_chat_plan, _execute_meeting_plan, _select_agents,
                   _store_agent_findings]:
            await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "agent_runtime", fn)
    finally:
        await db2.close()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 4: KNOWLEDGE GRAPH
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 4. KNOWLEDGE GRAPH ===")

    db3 = async_session()
    try:
        from app.services.knowledge_graph_service import KnowledgeGraphService

        kg = KnowledgeGraphService(db3)

        async def _explore_graph():
            result = await kg.explore_graph(limit=5)
            assert isinstance(result, dict)
            assert "nodes" in result
            assert "edges" in result or "total_edges_shown" in result

        async def _find_related_assets():
            related = await kg.find_related_assets(node_id="test", limit=5)
            assert isinstance(related, list)

        async def _find_assets_by_entity():
            assets = await kg.find_assets_by_entity(entity_name="DocTel", limit=5)
            assert isinstance(assets, list)

        for fn in [_explore_graph, _find_related_assets, _find_assets_by_entity]:
            await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "knowledge_graph", fn)
    finally:
        await db3.close()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 5: WORKFLOW ENGINE
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 5. WORKFLOW ENGINE ===")

    db4 = async_session()
    try:
        from app.db.enterprise_models import WorkflowExecutionRecord
        from sqlalchemy import select
        import uuid

        async def _insert_workflow():
            wf = WorkflowExecutionRecord(
                execution_id=f"test-val-{uuid.uuid4().hex[:8]}",
                workflow_type="policy_review",
                objective="Test validation workflow",
                status="completed",
            )
            db4.add(wf)
            await db4.commit()
            assert wf.id is not None

        async def _select_workflows():
            result = await db4.execute(select(WorkflowExecutionRecord).limit(5))
            records = result.scalars().all()
            assert isinstance(records, list)

        for fn in [_insert_workflow, _select_workflows]:
            await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "workflow_engine", fn)
    finally:
        await db4.close()

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 6: DATABASE CONNECTION INTEGRITY
    # ═══════════════════════════════════════════════════════════════════════
    print("\n=== 6. DATABASE CONNECTION INTEGRITY ===")

    async def _enterprise_tables():
        tables = [
            'agents', 'agent_executions', 'agent_memory', 'agent_execution_plans',
            'knowledge_nodes', 'knowledge_edges', 'knowledge_assets',
            'workflow_execution_records', 'interaction_audits',
        ]
        for table in tables:
            row = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=$1", table
            )
            assert row >= 1, f"Table '{table}' not found"
        print(f"  [PASS] All {len(tables)} enterprise tables accessible")

    async def _transaction_integrity():
        # Run a query to confirm the connection is clean
        val = await conn.fetchval("SELECT 1")
        assert val == 1

    for fn in [_enterprise_tables, _transaction_integrity]:
        await suite.run(fn.__name__.lstrip('_').replace('_', ' '), "integrity", fn)

    # ── Cleanup ─────────────────────────────────────────────────────────────
    await conn.close()

    # ═════════════════════════════════════════════════════════════════════════
    # REPORT
    # ═════════════════════════════════════════════════════════════════════════
    report = suite.report()

    print(f"\n{'='*60}")
    print(f"  ENTERPRISE POST-MIGRATION VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"  Total tests:  {report['total_tests']}")
    print(f"  Passed:       {report['passed']}")
    print(f"  Failed:       {report['failed']}")
    print(f"  Elapsed:      {report['elapsed_sec']}s")
    print(f"\n  By category:")
    for cat, stats in sorted(report['by_category'].items()):
        status = "[OK]" if stats['failed'] == 0 else "[FAIL]"
        print(f"    {status} {cat:20s}: {stats['passed']}/{stats['total']} passed")

    if report['failed_tests']:
        print(f"\n  FAILED TESTS:")
        for name in report['failed_tests']:
            err = next((r['error'] for r in report['results'] if r['name'] == name), '')
            print(f"    - {name}: {err}")

    print(f"\n{'='*60}")
    readiness = "READY" if report['failed'] == 0 else "DEGRADED"
    score = 100 if report['failed'] == 0 else \
        round((report['passed'] / report['total_tests']) * 100, 1)
    print(f"  READINESS: {readiness} (score: {score}%)")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    sys.exit(0 if report['failed'] == 0 else 1)
