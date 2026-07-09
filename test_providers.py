import requests

# Test with local-dev token bypass
r = requests.get(
    'http://127.0.0.1:8000/api/models/v2/providers',
    headers={'Authorization': 'Bearer local-admin'}
)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    providers = data.get('providers', [])
    print(f'Found {len(providers)} providers')
    for p in providers:
        print(f"  - {p['id']}: {p['name']} ({len(p.get('models', []))} models)")
else:
    print(r.text[:2000])
