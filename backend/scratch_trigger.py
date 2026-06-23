import requests
import json

base_url = "http://localhost:8000/api/v1"

# 1. Get token
resp = requests.post(f"{base_url}/auth/token", json={
    "username": "admin",
    "password": "G7y-bAfAQIwIXvqCpZBVThRNVUtUdaXanEYU_ZlX9Ug"
})

if not resp.ok:
    print("Auth failed:", resp.text)
    exit(1)

token = resp.json()["access_token"]
print("Token acquired.")

# 2. Trigger Telegram collection
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
resp = requests.post(f"{base_url}/collectors/run", headers=headers, json={
    "source": "telegram"
})

print("Status Code:", resp.status_code)
print("Response:", resp.text)
