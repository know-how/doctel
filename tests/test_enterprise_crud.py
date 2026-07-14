"""
Enterprise CRUD Integration Tests — Tests all 17 enterprise admin endpoints.

Run with server running:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Then:
    .venv\Scripts\python.exe -m pytest tests/test_enterprise_crud.py -v

Or standalone:
    .venv\Scripts\python.exe tests/test_enterprise_crud.py
"""

import json
import sys
import traceback
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "http://127.0.0.1:8001"
ADMIN_TOKEN = "local-admin"
HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json",
}


def _req(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method, headers=HEADERS)
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}


passed = 0
failed = 0


def check(name, status_ok, predicate=None):
    global passed, failed
    status, data = _req("GET", path) if "path" in dir() else (None, None)
    print(f"  [{name}] {status}")
    if status in (status_ok if isinstance(status_ok, (list, tuple)) else [status_ok]):
        if predicate is None or predicate(data):
            passed += 1
            print(f"    ✓ PASS")
        else:
            failed += 1
            print(f"    ✗ FAIL (predicate): {data}")
    else:
        failed += 1
        print(f"    ✗ FAIL (expected {status_ok}, got {status}): {data}")


def _delete_alert_by_scope(scope_type, scope_id, period="monthly"):
    """Delete any existing BudgetAlert matching the given unique key."""
    status, data = _req("GET", "/api/admin/enterprise/budget-alerts")
    if status != 200:
        return
    for item in data.get("items", []):
        if (item.get("scopeType") == scope_type
                and item.get("scopeId") == scope_id
                and item.get("period", "monthly") == period):
            _req("DELETE", f'/api/admin/enterprise/budget-alerts/{item["id"]}')


def _delete_restriction(department, restriction_type, restriction_id):
    """Delete any existing DepartmentRestriction matching the given unique key."""
    status, data = _req("GET", "/api/admin/enterprise/department-restrictions")
    if status != 200:
        return
    for item in data.get("items", []):
        if (item.get("department") == department
                and item.get("restrictionType") == restriction_type
                and item.get("restrictionId") == restriction_id):
            _req("DELETE", f'/api/admin/enterprise/department-restrictions/{item["id"]}')


# ──────────────────────────────────────────
# Helper to run all tests
# ──────────────────────────────────────────
def test_all():
    global passed, failed, path
    print("=" * 60)
    print("Enterprise CRUD Integration Tests")
    print("=" * 60)

    # ── Pillar 3: DocAnalysisVersion ──
    print("\n--- PILLAR 3: DocAnalysisVersion ---")
    path = "/api/admin/enterprise/doc-analysis-versions"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # Test get-by-id (will be 404 since no data yet)
    status, data = _req("GET", "/api/admin/enterprise/doc-analysis-versions/1")
    print(f"  [get 404] {status}")
    if status == 404:
        passed += 1
        print("    ✓ PASS (expected 404)")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 4: QuotationSpan ──
    print("\n--- PILLAR 4: QuotationSpan ---")
    path = "/api/admin/enterprise/quotation-spans"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 6: Knowledge Graph ──
    print("\n--- PILLAR 6: Knowledge Graph ---")
    path = "/api/admin/enterprise/knowledge-nodes"
    status, data = _req("GET", path)
    print(f"  [list nodes] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    path = "/api/admin/enterprise/knowledge-edges"
    status, data = _req("GET", path)
    print(f"  [list edges] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 9: DocumentVersion ──
    print("\n--- PILLAR 9: DocumentVersion ---")
    path = "/api/admin/enterprise/document-versions"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 10: Agent CRUD ──
    print("\n--- PILLAR 10: Agent CRUD ---")
    # Create an agent
    status, data = _req("POST", "/api/admin/enterprise/agents", {
        "name": "TestAgent",
        "description": "Test agent for integration tests",
        "agent_type": "general",
        "config": {},
    })
    print(f"  [create] {status}")
    if status == 200:
        passed += 1
        agent_id = data.get("item", {}).get("id")
        print(f"    ✓ PASS (id={agent_id})")
    else:
        failed += 1
        agent_id = None
        print(f"    ✗ FAIL: {data}")

    # List agents
    path = "/api/admin/enterprise/agents"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200 and data.get("count", 0) >= 1:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # Get agent by id
    if agent_id:
        status, data = _req("GET", f"/api/admin/enterprise/agents/{agent_id}")
        print(f"  [get by id] {status}")
        if status == 200:
            passed += 1
            print(f"    ✓ PASS (name={data.get('item', {}).get('name', '?')})")
        else:
            failed += 1
            print(f"    ✗ FAIL: {data}")

        # Update agent
        status, data = _req("PUT", f"/api/admin/enterprise/agents/{agent_id}", {
            "name": "TestAgent-Updated",
            "description": "Updated description",
            "agent_type": "specialized",
            "config": {"key": "value"},
            "is_active": True,
        })
        print(f"  [update] {status}")
        if status == 200:
            passed += 1
            print(f"    ✓ PASS (name={data.get('item', {}).get('name', '?')})")
        else:
            failed += 1
            print(f"    ✗ FAIL: {data}")

    # ── Pillar 11: HumanReview ──
    print("\n--- PILLAR 11: HumanReview ---")
    path = "/api/admin/enterprise/human-reviews"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 12: PromptTemplate CRUD ──
    print("\n--- PILLAR 12: PromptTemplate CRUD ---")
    # Create template
    status, data = _req("POST", "/api/admin/enterprise/prompt-templates", {
        "name": "TestTemplate",
        "description": "Test template",
        "task_type": "chat",
        "owner": "tester",
        "department": "general",
    })
    print(f"  [create template] {status}")
    if status == 200:
        passed += 1
        tmpl_id = data.get("item", {}).get("id")
        print(f"    ✓ PASS (id={tmpl_id})")
    else:
        failed += 1
        tmpl_id = None

    # List templates
    path = "/api/admin/enterprise/prompt-templates"
    status, data = _req("GET", path)
    print(f"  [list templates] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # Create version (if template was created)
    if tmpl_id:
        status, data = _req("POST", f"/api/admin/enterprise/prompt-templates/{tmpl_id}/versions", {
            "content": "You are an expert. Question: {question}",
            "change_notes": "Initial version",
        })
        print(f"  [create version] {status}")
        if status == 200:
            passed += 1
            print(f"    ✓ PASS (version_id={data.get('item', {}).get('id', '?')})")
        else:
            failed += 1
            print(f"    ✗ FAIL: {data}")

    # ── Pillar 13: BenchmarkRun ──
    print("\n--- PILLAR 13: BenchmarkRun ---")
    path = "/api/admin/enterprise/benchmark-runs"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 14: CostRecord & BudgetAlert ──
    print("\n--- PILLAR 14: CostRecord ---")
    path = "/api/admin/enterprise/cost-records"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # Cost summary
    status, data = _req("GET", "/api/admin/enterprise/cost-records/summary?group_by=department")
    print(f"  [summary] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    print("\n--- PILLAR 14: BudgetAlert CRUD ---")
    # Clean up any existing BudgetAlert with the same unique key
    _delete_alert_by_scope("department", "radiology", "monthly")
    # Create a budget alert
    status, data = _req("POST", "/api/admin/enterprise/budget-alerts", {
        "scope_type": "department",
        "scope_id": "radiology",
        "budget_amount": 1000.0,
        "alert_threshold_pct": 80.0,
    })
    print(f"  [create] {status}")
    if status == 200:
        passed += 1
        alert_id = data.get("item", {}).get("id")
        print(f"    ✓ PASS (id={alert_id})")
    else:
        failed += 1
        alert_id = None

    # List budget alerts
    path = "/api/admin/enterprise/budget-alerts"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 15: ConfidenceScore ──
    print("\n--- PILLAR 15: ConfidenceScore ---")
    path = "/api/admin/enterprise/confidence-scores"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 17: DepartmentRestriction ──
    print("\n--- PILLAR 17: DepartmentRestriction CRUD ---")
    # Clean up any existing DepartmentRestriction with the same unique key
    _delete_restriction("radiology", "provider", "openai")
    # Create restriction
    status, data = _req("POST", "/api/admin/enterprise/department-restrictions", {
        "department": "radiology",
        "restriction_type": "provider",
        "restriction_id": "openai",
        "is_allowed": True,
    })
    print(f"  [create] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # List restrictions
    path = "/api/admin/enterprise/department-restrictions"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Pillar 20: InteractionAudit ──
    print("\n--- PILLAR 20: InteractionAudit ---")
    path = "/api/admin/enterprise/interaction-audits"
    status, data = _req("GET", path)
    print(f"  [list] {status}")
    if status == 200:
        passed += 1
        print(f"    ✓ PASS (count={data.get('count', '?')})")
    else:
        failed += 1
        print(f"    ✗ FAIL: {data}")

    # ── Cleanup: Delete created entities ──
    print("\n--- CLEANUP ---")
    if agent_id:
        status, data = _req("DELETE", f"/api/admin/enterprise/agents/{agent_id}")
        print(f"  [delete agent] {status}")
        if status == 200:
            passed += 1
            print("    ✓ PASS")
        else:
            failed += 1
            print(f"    ✗ FAIL: {data}")
    # Clean up BudgetAlert & DepartmentRestriction for idempotent re-runs
    _delete_alert_by_scope("department", "radiology", "monthly")
    _delete_restriction("radiology", "provider", "openai")

    # ── Summary ──
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
