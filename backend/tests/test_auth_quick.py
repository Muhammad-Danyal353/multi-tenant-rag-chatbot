"""
Quick Authentication Test

A simple script to quickly test the main authentication flow:
1. Register a user
2. Login
3. Get current user
4. Test authentication
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1/auth"

def test():
    print("🚀 Quick Authentication Test\n")
    
    # Test data
    test_user = {
        "email": f"quicktest@example.com",
        "password": "TestPass123",
        "full_name": "Quick Test User",
        "organization_name": "Quick Test Org"
    }
    
    try:
        # 1. Register
        print("1️⃣  Registering user...")
        response = requests.post(
            f"{BASE_URL}/register",
            json=test_user
        )
        
        if response.status_code == 201:
            print(f"   ✅ User registered: {response.json()['email']}")
        elif response.status_code == 400 and "already" in response.json().get('detail', '').lower():
            print(f"   ℹ️  User already exists, continuing with login...")
        else:
            print(f"   ❌ Registration failed: {response.json()}")
            return
        
        # 2. Login
        print("\n2️⃣  Logging in...")
        response = requests.post(
            f"{BASE_URL}/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"]
            }
        )
        
        if response.status_code != 200:
            print(f"   ❌ Login failed: {response.json()}")
            return
        
        data = response.json()
        access_token = data["tokens"]["access_token"]
        print(f"   ✅ Logged in successfully")
        print(f"   📝 Access Token: {access_token[:30]}...")
        
        # 3. Get current user
        print("\n3️⃣  Getting current user info...")
        response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            print(f"   ❌ Failed to get user: {response.json()}")
            return
        
        user = response.json()
        print(f"   ✅ Current user retrieved:")
        print(f"      - ID: {user['id']}")
        print(f"      - Email: {user['email']}")
        print(f"      - Name: {user['full_name']}")
        print(f"      - Verified: {user['is_verified']}")
        
        # 4. Test unauthorized access
        print("\n4️⃣  Testing unauthorized access...")
        response = requests.get(f"{BASE_URL}/me")
        
        if response.status_code == 401:
            print(f"   ✅ Unauthorized access blocked correctly")
        else:
            print(f"   ❌ Security issue: Unauthorized access should be blocked")
        
        print("\n✅ All quick tests passed!\n")
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server!")
        print("   Make sure the server is running:")
        print("   uvicorn app.main:app --reload --port 8000")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

if __name__ == "__main__":
    test()

