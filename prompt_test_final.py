"""Prompt Suggestions API final test runner with corrected expectations."""
import urllib.request
import json
import os
import sys

TOKEN_FILE = os.environ.get("TEMP", "") + "\\prompt_token.txt"

# Step 1: Login
login_data = json.dumps({"ec_number": "admin", "password": "admin"}).encode()
req = urllib.request.Request(
    "http://localhost:8000/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=30) as f:
        login_resp = json.loads(f.read())
        token = login_resp.get("access_token", "")
        with open(TOKEN_FILE, "w") as fp:
            fp.write(token)
        print(f"[PASS] LOGIN: token={token[:40]}...")
except Exception as e:
    print(f"[FAIL] LOGIN: {e}")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
all_pass = True

def test(name, method, url, data=None, timeout=30):
    """Run a single test and return parsed JSON."""
    global all_pass
    try:
        req = urllib.request.Request(url, headers=headers, method=method)
        if data is not None:
            req.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        with urllib.request.urlopen(req, timeout=timeout) as f:
            result = json.loads(f.read())
        print(f"[PASS] {name}")
        return result
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        all_pass = False
        return None

# Test 1: List with pagination
r = test("List suggestions", "GET",
    "http://localhost:8000/api/prompt-suggestions/?skip=0&limit=50")
if r:
    assert "items" in r, "Missing 'items'"
    assert "total" in r, "Missing 'total'"
    assert r["total"] >= 17, f"total={r['total']}"
    if r["items"]:
        item = r["items"][0]
        for k in ["id", "title", "prompt_text", "category", "enabled", "display_order", "icon"]:
            assert k in item, f"Missing key: {k}"
    print(f"  -> total={r['total']}, items={len(r['items'])}, snake_case=OK")

# Test 2: Search
r = test("Search 'safety'", "GET",
    "http://localhost:8000/api/prompt-suggestions/?search=safety&skip=0&limit=50")
if r:
    assert r["total"] >= 1, f"total={r['total']}"
    print(f"  -> {r['total']} result(s) matching 'safety'")

# Test 3: Categories
r = test("List categories", "GET",
    "http://localhost:8000/api/prompt-suggestions/categories")
if r:
    cats = r.get("categories", [])
    print(f"  -> {cats} ({len(cats)} categories)")

# Test 4: Toggle
r = test("Toggle id=1 OFF", "POST",
    "http://localhost:8000/api/prompt-suggestions/1/toggle", data={})
if r:
    assert "enabled" in r
    print(f"  -> enabled={r['enabled']}")

r = test("Toggle id=1 ON", "POST",
    "http://localhost:8000/api/prompt-suggestions/1/toggle", data={})
if r:
    assert r["enabled"] == True
    print(f"  -> enabled={r['enabled']}")

# Test 5: Random
r = test("Random suggestions", "GET",
    "http://localhost:8000/api/prompt-suggestions/random?limit=6")
if r:
    assert "suggestions" in r
    assert "count" in r
    print(f"  -> {len(r['suggestions'])} suggestions, count={r['count']}")

# Test 6: Category filter
r = test("Filter category=vision", "GET",
    "http://localhost:8000/api/prompt-suggestions/?category=vision&skip=0&limit=50")
if r:
    assert r["total"] == 2, f"Expected 2 vision, got {r['total']}"
    print(f"  -> {r['total']} vision results")

# Test 7: Enabled filter
r = test("Filter is_enabled=true", "GET",
    "http://localhost:8000/api/prompt-suggestions/?is_enabled=true&skip=0&limit=50")
if r:
    assert r["total"] == 17, f"Expected 17 enabled, got {r['total']}"
    print(f"  -> {r['total']} enabled results")

# Test 8: Filter policy category
r = test("Filter category=policy", "GET",
    "http://localhost:8000/api/prompt-suggestions/?category=policy&skip=0&limit=50")
if r:
    assert r["total"] == 3, f"Expected 3 policy, got {r['total']}"
    print(f"  -> {r['total']} policy results")

print(f"\n{'='*40}")
if all_pass:
    print("ALL TESTS PASSED!")
else:
    print("SOME TESTS FAILED")
print("=" * 40)
