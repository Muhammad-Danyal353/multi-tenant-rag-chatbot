"""
Authentication Endpoints Test Script

This script tests all authentication endpoints to ensure they work correctly.
Run this after starting the server: uvicorn app.main:app --reload
"""

import requests
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000/api/v1/auth"
HEADERS = {"Content-Type": "application/json"}

# Store tokens and user data for testing
import time
timestamp = int(time.time())
test_data = {
    "email": f"testuser{timestamp}@example.com",
    "password": "TestPassword123",
    "full_name": "Test User",
    "organization_name": f"Test Organization {timestamp}"
}

tokens = {
    "access_token": None,
    "refresh_token": None
}

verification_token = None
reset_token = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name: str, response, expected_status: int = 200):
    """Print test result"""
    success = response.status_code == expected_status
    status_icon = "✅" if success else "❌"
    
    print(f"\n{status_icon} {test_name}")
    print(f"   Status Code: {response.status_code} (Expected: {expected_status})")
    
    try:
        response_data = response.json()
        print(f"   Response: {json.dumps(response_data, indent=2)}")
    except:
        print(f"   Response: {response.text}")
    
    return success


def make_request(
    method: str,
    endpoint: str,
    data: Optional[dict] = None,
    token: Optional[str] = None
):
    """Make HTTP request to API"""
    url = f"{BASE_URL}{endpoint}"
    headers = HEADERS.copy()
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, json=data, headers=headers)
    elif method == "PUT":
        response = requests.put(url, json=data, headers=headers)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    return response


# ============================================================================
# TEST 1: HEALTH CHECK
# ============================================================================

def test_health_check():
    """Test auth service health check"""
    print_section("TEST 1: Auth Service Health Check")
    
    response = make_request("GET", "/health")
    print_result("Health Check", response, 200)


# ============================================================================
# TEST 2: USER REGISTRATION
# ============================================================================

def test_user_registration():
    """Test user registration"""
    print_section("TEST 2: User Registration")
    
    # Test successful registration
    response = make_request("POST", "/register", {
        "email": test_data["email"],
        "password": test_data["password"],
        "full_name": test_data["full_name"],
        "organization_name": test_data["organization_name"]
    })
    
    success = print_result("Register New User", response, 201)
    
    if success:
        response_data = response.json()
        user_data = response_data.get("data", {}).get("user", {})
        print(f"\n   ✓ User ID: {user_data.get('id')}")
        print(f"   ✓ Email: {user_data.get('email')}")
        print(f"   ✓ Full Name: {user_data.get('full_name')}")
        print(f"   ✓ Is Verified: {user_data.get('is_verified')}")
    
    # Test duplicate email registration (should fail)
    print("\n--- Testing Duplicate Email Registration (Should Fail) ---")
    response = make_request("POST", "/register", {
        "email": test_data["email"],
        "password": test_data["password"],
        "full_name": "Another User",
        "organization_name": "Another Organization"
    })
    
    print_result("Register Duplicate Email", response, 400)


# ============================================================================
# TEST 3: USER LOGIN
# ============================================================================

def test_user_login():
    """Test user login"""
    print_section("TEST 3: User Login")
    
    # Test successful login
    response = make_request("POST", "/login", {
        "email": test_data["email"],
        "password": test_data["password"]
    })
    
    success = print_result("User Login", response, 200)
    
    if success:
        response_data = response.json()
        tokens_data = response_data.get("data", {}).get("tokens", {})
        tokens["access_token"] = tokens_data.get("access_token")
        tokens["refresh_token"] = tokens_data.get("refresh_token")
        
        if tokens["access_token"]:
            print(f"\n   ✓ Access Token: {tokens['access_token'][:50]}...")
            print(f"   ✓ Refresh Token: {tokens['refresh_token'][:50]}...")
            print(f"   ✓ Token Type: {tokens_data.get('token_type')}")
            print(f"   ✓ Expires In: {tokens_data.get('expires_in')} seconds")
        else:
            print("\n   ❌ Failed to extract tokens from response")
    
    # Test invalid credentials (should fail)
    print("\n--- Testing Invalid Credentials (Should Fail) ---")
    response = make_request("POST", "/login", {
        "email": test_data["email"],
        "password": "WrongPassword123"
    })
    
    print_result("Login with Wrong Password", response, 401)


# ============================================================================
# TEST 4: GET CURRENT USER
# ============================================================================

def test_get_current_user():
    """Test getting current user profile"""
    print_section("TEST 4: Get Current User")
    
    if not tokens["access_token"]:
        print("❌ No access token available. Please run login test first.")
        return
    
    response = make_request("GET", "/me", token=tokens["access_token"])
    
    success = print_result("Get Current User", response, 200)
    
    if success:
        response_data = response.json()
        user_data = response_data.get("data", {}).get("user", {})
        print(f"\n   ✓ User ID: {user_data.get('id')}")
        print(f"   ✓ Email: {user_data.get('email')}")
        print(f"   ✓ Full Name: {user_data.get('full_name')}")
        print(f"   ✓ Is Active: {user_data.get('is_active')}")
        print(f"   ✓ Is Verified: {user_data.get('is_verified')}")


# ============================================================================
# TEST 5: TOKEN REFRESH
# ============================================================================

def test_token_refresh():
    """Test token refresh"""
    print_section("TEST 5: Token Refresh")
    
    if not tokens["refresh_token"]:
        print("❌ No refresh token available. Please run login test first.")
        return
    
    response = make_request("POST", "/refresh", {
        "refresh_token": tokens["refresh_token"]
    })
    
    success = print_result("Refresh Token", response, 200)
    
    if success:
        response_data = response.json()
        tokens_data = response_data.get("data", {}).get("tokens", {})
        # Update tokens
        tokens["access_token"] = tokens_data.get("access_token")
        tokens["refresh_token"] = tokens_data.get("refresh_token")
        
        if tokens["access_token"]:
            print(f"\n   ✓ New Access Token: {tokens['access_token'][:50]}...")
            print(f"   ✓ New Refresh Token: {tokens['refresh_token'][:50]}...")
        else:
            print("\n   ❌ Failed to extract new tokens from response")


# ============================================================================
# TEST 6: CHANGE PASSWORD
# ============================================================================

def test_change_password():
    """Test changing password"""
    print_section("TEST 6: Change Password")
    
    if not tokens["access_token"]:
        print("❌ No access token available. Please run login test first.")
        return
    
    new_password = "NewTestPassword456"
    
    # Change password
    response = make_request("POST", "/change-password", {
        "current_password": test_data["password"],
        "new_password": new_password
    }, token=tokens["access_token"])
    
    success = print_result("Change Password", response, 200)
    
    if success:
        print("\n   ✓ Password changed successfully")
        
        # Try logging in with old password (should fail)
        print("\n--- Testing Login with Old Password (Should Fail) ---")
        response = make_request("POST", "/login", {
            "email": test_data["email"],
            "password": test_data["password"]
        })
        print_result("Login with Old Password", response, 401)
        
        # Login with new password
        print("\n--- Testing Login with New Password (Should Succeed) ---")
        response = make_request("POST", "/login", {
            "email": test_data["email"],
            "password": new_password
        })
        
        success = print_result("Login with New Password", response, 200)
        
        if success:
            # Update tokens
            response_data = response.json()
            tokens_data = response_data.get("data", {}).get("tokens", {})
            tokens["access_token"] = tokens_data.get("access_token")
            tokens["refresh_token"] = tokens_data.get("refresh_token")
            
            # Change password back to original
            print("\n--- Changing Password Back to Original ---")
            response = make_request("POST", "/change-password", {
                "current_password": new_password,
                "new_password": test_data["password"]
            }, token=tokens["access_token"])
            
            print_result("Restore Original Password", response, 200)


# ============================================================================
# TEST 7: PASSWORD RESET FLOW
# ============================================================================

def test_password_reset_flow():
    """Test forgot password and reset flow"""
    print_section("TEST 7: Password Reset Flow")
    
    # Request password reset
    response = make_request("POST", "/forgot-password", {
        "email": test_data["email"]
    })
    
    success = print_result("Request Password Reset", response, 200)
    
    if success:
        print("\n   ✓ Password reset email sent (check logs for token)")
        print("   ℹ️  In production, the token would be sent via email")
        print("   ℹ️  For testing, you need to extract the token from the database or logs")
        print("\n   Note: To complete this test, you would need to:")
        print("   1. Get the reset token from the email/database")
        print("   2. Call POST /reset-password with the token and new password")
    
    # Test with non-existent email (should still return success for security)
    print("\n--- Testing Reset with Non-existent Email (Should Still Succeed) ---")
    response = make_request("POST", "/forgot-password", {
        "email": "nonexistent@example.com"
    })
    
    print_result("Reset Non-existent Email", response, 200)


# ============================================================================
# TEST 8: EMAIL VERIFICATION FLOW
# ============================================================================

def test_email_verification_flow():
    """Test email verification flow"""
    print_section("TEST 8: Email Verification Flow")
    
    # Request resend verification
    response = make_request("POST", "/resend-verification", {
        "email": test_data["email"]
    })
    
    # Accept both 200 (success) and 422 (already verified) as valid responses
    success = response.status_code in [200, 422]
    expected_status = 200 if response.status_code == 200 else 422
    
    print_result("Resend Verification Email", response, expected_status)
    
    if response.status_code == 200:
        print("\n   ✓ Verification email sent (check logs for token)")
        print("   ℹ️  In production, the token would be sent via email")
        print("   ℹ️  For testing, you need to extract the token from the database or logs")
        print("\n   Note: To complete this test, you would need to:")
        print("   1. Get the verification token from the email/database")
        print("   2. Call POST /verify-email with the token")
    elif response.status_code == 422:
        print("\n   ✓ User is already verified (expected behavior)")
        print("   ℹ️  This is normal for users who are already verified")


# ============================================================================
# TEST 9: LOGOUT
# ============================================================================

def test_logout():
    """Test logout"""
    print_section("TEST 9: Logout")
    
    if not tokens["access_token"]:
        print("❌ No access token available. Please run login test first.")
        return
    
    response = make_request("POST", "/logout", token=tokens["access_token"])
    
    print_result("Logout", response, 200)


# ============================================================================
# TEST 10: UNAUTHORIZED ACCESS
# ============================================================================

def test_unauthorized_access():
    """Test accessing protected endpoints without token"""
    print_section("TEST 10: Unauthorized Access")
    
    # Try to access /me without token
    response = make_request("GET", "/me")
    
    print_result("Access /me Without Token", response, 401)
    
    # Try with invalid token
    print("\n--- Testing with Invalid Token ---")
    response = make_request("GET", "/me", token="invalid_token_12345")
    
    print_result("Access /me With Invalid Token", response, 401)


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all authentication tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "AUTHENTICATION ENDPOINTS TEST SUITE" + " " * 23 + "║")
    print("╚" + "=" * 78 + "╝")
    print(f"\nBase URL: {BASE_URL}")
    print(f"Test User Email: {test_data['email']}")
    print("\nℹ️  Make sure the server is running: uvicorn app.main:app --reload")
    print("ℹ️  Make sure the database is set up and migrations are run")
    
    try:
        # Run tests in sequence
        test_health_check()
        test_user_registration()
        test_user_login()
        test_get_current_user()
        test_token_refresh()
        test_change_password()
        test_password_reset_flow()
        test_email_verification_flow()
        test_logout()
        test_unauthorized_access()
        
        # Summary
        print_section("TEST SUMMARY")
        print("\n✅ All basic authentication tests completed!")
        print("\nℹ️  Notes:")
        print("   - Email verification and password reset require email service configuration")
        print("   - For full testing, configure SMTP settings in .env file")
        print("   - Check the database to see created user and organization")
        print("   - Tokens are stored in the 'tokens' variable for further testing")
        
        print("\n📊 Token Information:")
        print(f"   Access Token: {tokens['access_token'][:50] if tokens['access_token'] else 'Not available'}...")
        print(f"   Refresh Token: {tokens['refresh_token'][:50] if tokens['refresh_token'] else 'Not available'}...")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server!")
        print("   Make sure the server is running: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()

