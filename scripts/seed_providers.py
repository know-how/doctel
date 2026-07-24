"""
Seed AI providers into the DocTel database via the admin API.
Uses urllib (which works from this environment) instead of httpx.

Run: python scripts/seed_providers.py <email> <otp_code>
"""

import sys, os, json, urllib.request, urllib.error

BASE = "http://192.168.8.100:8000"

PROVIDERS = [
    {"name": "Ollama", "vendor": "ollama", "base_url": "http://localhost:11434/v1",
     "description": "Locally hosted models via Ollama", "icon": "cpu",
     "provider_type": "openai", "models_endpoint": "http://localhost:11434/api/tags",
     "chat_endpoint": "", "health_endpoint": "http://localhost:11434/api/tags",
     "sort_order": 1},
    {"name": "DeepSeek", "vendor": "DeepSeek", "base_url": "https://api.deepseek.com/v1",
     "description": "DeepSeek cloud API", "icon": "deepseek",
     "provider_type": "openai", "sort_order": 2},
    {"name": "OpenCode Zen", "vendor": "opencode", "base_url": "https://opencode.ai/zen/v1",
     "description": "OpenCode Zen cloud API", "icon": "opencode",
     "provider_type": "openai", "sort_order": 3},
    {"name": "OpenCode Go", "vendor": "opencode", "base_url": "https://opencode.ai/zen/go/v1",
     "description": "OpenCode Go cloud API", "icon": "opencode",
     "provider_type": "openai", "sort_order": 4},
]


def req(method, url, data=None, token=None):
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else {"error": str(e)}


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "kkwaramba@zetdc.co.zw"
    otp = sys.argv[2] if len(sys.argv) > 2 else ""

    if not otp:
        # Read from file
        otp_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp_otp.txt")
        if os.path.exists(otp_file):
            with open(otp_file) as f:
                raw = f.read().strip()
            if ":" in raw:
                otp = raw.split(":")[-1].strip()
            else:
                otp = raw
        if not otp:
            print(f"Usage: python seed_providers.py {email} <otp_code>")
            return

    # Step 1: Login
    print(f"Logging in as {email}...")
    status, data = req("POST", f"{BASE}/auth/email/verify",
                       {"email": email, "code": otp.strip()})
    if status != 200:
        print(f"Login failed: {status} {data}")
        return

    token = data.get("access_token", "")
    if not token:
        print(f"No token: {data}")
        return
    print(f"Logged in OK")

    # Step 2: Check existing providers
    status, data = req("GET", f"{BASE}/api/models/v2/providers", token=token)
    if status != 200:
        print(f"Failed to list providers: {status} {data}")
        return
    existing = {p.get("id") for p in data.get("providers", [])}
    print(f"Existing providers: {len(existing)}")

    # Step 3: Add providers
    for prov in PROVIDERS:
        pid = prov["name"].lower().replace(" ", "-")
        if pid in existing:
            print(f"  SKIP {prov['name']} (exists)")
            continue

        status, data = req("POST", f"{BASE}/api/models/v2/providers", prov, token)
        if status == 200:
            print(f"  ADDED {prov['name']}")
            existing.add(pid)
        else:
            print(f"  FAILED {prov['name']}: {status} {data}")

    # Step 4: Fetch models for Ollama and others
    for prov in PROVIDERS:
        pid = prov["name"].lower().replace(" ", "-")
        print(f"Fetching models for {prov['name']}...")
        status, data = req("POST", f"{BASE}/api/models/v2/fetch-models",
                          {"providerId": pid}, token)
        if status == 200:
            result = data
            if result.get("success"):
                print(f"  OK: {result.get('count', 0)} models")
            else:
                print(f"  INFO: {result.get('message', '')[:100]}")
        else:
            print(f"  ERROR: {status}")

    # Step 5: Show final state
    print("\n=== Final Provider State ===")
    status, data = req("GET", f"{BASE}/api/models/v2/providers", token=token)
    total = 0
    for p in data.get("providers", []):
        cnt = len(p.get("models", []))
        total += cnt
        print(f"  {p['name']}: {cnt} models")
    print(f"\nTotal: {total} models across {len(data.get('providers',[]))} providers")


if __name__ == "__main__":
    main()
