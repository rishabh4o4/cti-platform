import requests
import json

base_url = "http://localhost:8000/api/v1"

# 1. Get token
resp = requests.post(f"{base_url}/auth/token", data={
    "username": "admin",
    "password": "G7y-bAfAQIwIXvqCpZBVThRNVUtUdaXanEYU_ZlX9Ug"
})

resp = requests.post(f"{base_url}/auth/token", json={
    "username": "admin",
    "password": "G7y-bAfAQIwIXvqCpZBVThRNVUtUdaXanEYU_ZlX9Ug"
})
token = resp.json()["access_token"]

# 2. Get system health
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(f"{base_url}/health/system", headers=headers)

if resp.ok:
    data = resp.json()
    for c in data["components"]:
        if c["name"] == "Telegram":
            print(json.dumps(c, indent=2))
else:
    print(resp.status_code, resp.text)
