import requests

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

# 2. Get status
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(f"{base_url}/collectors/status", headers=headers)

runs = resp.json()["runs"]
for r in runs:
    if r["source"] == "telegram":
        print("Telegram Run Status:", r["status"])
        print("Errors:", r["errors"])
        break
