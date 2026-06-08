"""
Test the Settings module (Stage 4.5)
"""
import requests
import json

BASE_URL = "https://pharmasud-api.onrender.com"

# Login
print("1. Logging in...")
r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "D. Abeer", "password": "abeer2026"}, timeout=15)
TOKEN = r.json()["token"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
print("   ✅ Logged in")

# Employees
print("\n2. Employee list...")
r = requests.get(f"{BASE_URL}/api/settings/employees", headers=H, timeout=15)
data = r.json()
print(f"   Count: {data['total']}")
for e in data["employees"]:
    print(f"   - {e['full_name']} ({e['username']}) [{e['role']}] active={e['is_active']}")

print("\n3. Add employee...")
r = requests.post(f"{BASE_URL}/api/settings/employees", headers=H,
    json={"full_name": "موظف تجربة", "username": "employee1", "password": "123456", "role": "employee"}, timeout=15)
print(f"   {r.json()}")

print("\n4. Add employee (duplicate)...")
r = requests.post(f"{BASE_URL}/api/settings/employees", headers=H,
    json={"full_name": "موظف 2", "username": "employee1", "password": "123456", "role": "employee"}, timeout=15)
print(f"   {r.json()}")

print("\n5. Pharmacy settings...")
r = requests.get(f"{BASE_URL}/api/settings/pharmacy", headers=H, timeout=15)
print(f"   {r.json()}")

print("\n6. Update pharmacy name...")
r = requests.put(f"{BASE_URL}/api/settings/pharmacy", headers=H,
    json={"name": "صيدلية الزاريات - فرع جديد", "phone": "+249912345678"}, timeout=15)
print(f"   {r.json()}")

print("\n7. Wrong password test...")
r = requests.post(f"{BASE_URL}/api/settings/change-password", headers=H,
    json={"current_password": "wrongpass", "new_password": "newpass123"}, timeout=15)
print(f"   {r.json()}")

print("\n8. Correct password test...")
r = requests.post(f"{BASE_URL}/api/settings/change-password", headers=H,
    json={"current_password": "abeer2026", "new_password": "abeer2026"}, timeout=15)
print(f"   {r.json()}")

print("\n✅ Settings test complete!")