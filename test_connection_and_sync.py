"""
Test Test Connection and Fetch Models functionality
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {"Authorization": "Bearer local-admin"}

def test_test_connection():
    """Test the Test Connection endpoint"""
    print("\n=== Testing Test Connection ===")
    
    # Test existing provider
    payload = {
        "providerId": "opencodezen"
    }
    
    r = requests.post(
        f"{BASE_URL}/api/models/v2/test-connection",
        headers=HEADERS,
        json=payload
    )
    
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Success: {data.get('success')}")
        print(f"Message: {data.get('message')}")
        print(f"Latency: {data.get('latencyMs')}ms")
        print(f"Status: {data.get('status')}")
        print(f"Provider ID: {data.get('providerId')}")
        print(f"Checked At: {data.get('checkedAt')}")
        return True
    else:
        print(f"Error: {r.text}")
        return False

def test_fetch_models():
    """Test the Fetch Models endpoint"""
    print("\n=== Testing Fetch Models ===")
    
    # Test with existing provider
    payload = {
        "providerId": "opencodezen"
    }
    
    r = requests.post(
        f"{BASE_URL}/api/models/v2/fetch-models",
        headers=HEADERS,
        json=payload
    )
    
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Success: {data.get('success')}")
        print(f"Count: {data.get('count')}")
        print(f"Added: {data.get('added')}")
        print(f"Updated: {data.get('updated')}")
        print(f"Removed: {data.get('removed')}")
        print(f"Unchanged: {data.get('unchanged')}")
        print(f"Changes Detected: {data.get('changesDetected')}")
        print(f"Message: {data.get('message')}")
        print(f"Provider ID: {data.get('providerId')}")
        print(f"Synced At: {data.get('syncedAt')}")
        return True
    else:
        print(f"Error: {r.text}")
        return False

def test_sync_history():
    """Test the Sync History endpoint"""
    print("\n=== Testing Sync History ===")
    
    r = requests.get(
        f"{BASE_URL}/api/models/v2/sync-history",
        headers=HEADERS,
        params={"limit": 10}
    )
    
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        entries = data.get("syncHistory", [])
        print(f"Total entries: {data.get('total')}")
        for entry in entries[:3]:  # Show first 3
            print(f"  - {entry['providerId']}: {entry['modelsRetrieved']} models, status={entry['status']}")
        return True
    else:
        print(f"Error: {r.text}")
        return False

def test_providers_status():
    """Test that providers show connection status"""
    print("\n=== Testing Providers Status ===")
    
    r = requests.get(
        f"{BASE_URL}/api/models/v2/providers",
        headers=HEADERS
    )
    
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        providers = data.get("providers", [])
        print(f"Found {len(providers)} providers:")
        for p in providers[:5]:
            print(f"  - {p['id']}: status={p.get('status')}, isConnected={p.get('isConnected')}")
        return True
    else:
        print(f"Error: {r.text}")
        return False

if __name__ == "__main__":
    print("Testing Provider Connection and Sync Functionality")
    print("=" * 60)
    
    results = []
    results.append(("Test Connection", test_test_connection()))
    results.append(("Fetch Models", test_fetch_models()))
    results.append(("Sync History", test_sync_history()))
    results.append(("Providers Status", test_providers_status()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
