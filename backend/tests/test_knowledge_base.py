"""
Knowledge Base Test Script

Tests for Phase 4: Knowledge Base Management
- Document upload and processing
- Web scraping
- Text content management
- Source management
"""

import requests
import json
import os
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"Content-Type": "application/json"}

# Test data
test_data = {
    "email": f"kbtest{int(__import__('time').time())}@example.com",
    "password": "TestPassword123",
    "full_name": "KB Test User",
    "organization_name": "KB Test Org"
}

tokens = {
    "access_token": None,
    "refresh_token": None
}

test_context = {
    "organization_id": None,
    "bot_id": None,
    "source_ids": [],
    "text_content_id": None
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_section(title: str):
    """Print section header"""
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
    token: Optional[str] = None,
    files: Optional[dict] = None,
    org_id: Optional[str] = None
):
    """Make HTTP request"""
    url = f"{BASE_URL}{endpoint}"
    headers = HEADERS.copy()
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if org_id:
        headers["X-Organization-ID"] = org_id
    
    # Remove Content-Type for file uploads
    if files:
        headers.pop("Content-Type", None)
    
    if method == "GET":
        response = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        if files:
            response = requests.post(url, headers=headers, files=files, data=data)
        else:
            response = requests.post(url, json=data, headers=headers)
    elif method == "PUT":
        response = requests.put(url, json=data, headers=headers)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    return response


# ============================================================================
# SETUP: AUTHENTICATION & BOT CREATION
# ============================================================================

def setup_auth():
    """Register and login"""
    print_section("SETUP: Authentication")
    
    # Register
    response = make_request("POST", "/auth/register", {
        "email": test_data["email"],
        "password": test_data["password"],
        "full_name": test_data["full_name"],
        "organization_name": test_data["organization_name"]
    })
    
    print_result("Register User", response, 201)
    
    if response.status_code == 201:
        data = response.json()
        test_context["organization_id"] = data.get("data", {}).get("organization", {}).get("id")
    
    # Login
    response = make_request("POST", "/auth/login", {
        "email": test_data["email"],
        "password": test_data["password"]
    })
    
    print_result("Login", response, 200)
    
    if response.status_code == 200:
        data = response.json()
        tokens["access_token"] = data.get("data", {}).get("tokens", {}).get("access_token")
        tokens["refresh_token"] = data.get("data", {}).get("tokens", {}).get("refresh_token")


def setup_bot():
    """Create a test bot"""
    print_section("SETUP: Create Bot")
    
    # Note: Bot creation endpoint not implemented yet
    # For now, we'll need to manually create a bot or skip bot-specific tests
    print("⚠️  Note: Bot creation endpoint not yet implemented")
    print("   Please create a bot manually and update test_context['bot_id']")
    
    # Placeholder - you would normally call POST /api/v1/bots here
    test_context["bot_id"] = "test-bot-id"


# ============================================================================
# TEST 1: TEXT CONTENT MANAGEMENT
# ============================================================================

def test_text_content():
    """Test text content creation and management"""
    print_section("TEST 1: Text Content Management")
    
    if not test_context.get("bot_id"):
        print("⚠️  Skipping: No bot_id available")
        return
    
    # Create text content
    response = make_request(
        "POST",
        "/knowledge/text",
        {
            "bot_id": test_context["bot_id"],
            "title": "Test FAQ",
            "content": "This is test content for the knowledge base. It contains important information that should be indexed and searchable.",
            "category": "FAQ",
            "tags": ["test", "faq", "important"]
        },
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    success = print_result("Create Text Content", response, 201)
    
    if success:
        data = response.json()
        test_context["text_content_id"] = data.get("data", {}).get("text_content_id")
        source_id = data.get("data", {}).get("source_id")
        if source_id:
            test_context["source_ids"].append(source_id)
    
    # List text content
    response = make_request(
        "GET",
        "/knowledge/text",
        {"bot_id": test_context["bot_id"]},
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    print_result("List Text Content", response, 200)


# ============================================================================
# TEST 2: DOCUMENT UPLOAD
# ============================================================================

def test_document_upload():
    """Test document upload"""
    print_section("TEST 2: Document Upload")
    
    if not test_context.get("bot_id"):
        print("⚠️  Skipping: No bot_id available")
        return
    
    # Create a test text file
    test_file_path = "test_document.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test document.\n")
        f.write("It contains multiple lines of text.\n")
        f.write("This should be chunked and indexed properly.\n" * 10)
    
    try:
        # Upload document
        with open(test_file_path, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            data = {"bot_id": test_context["bot_id"]}
            
            response = make_request(
                "POST",
                "/knowledge/documents/upload",
                data=data,
                token=tokens["access_token"],
                org_id=test_context["organization_id"],
                files=files
            )
        
        success = print_result("Upload Document", response, 201)
        
        if success:
            data = response.json()
            source_id = data.get("data", {}).get("source_id")
            if source_id:
                test_context["source_ids"].append(source_id)
    
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


# ============================================================================
# TEST 3: WEB SCRAPING
# ============================================================================

def test_web_scraping():
    """Test website scraping"""
    print_section("TEST 3: Web Scraping")
    
    if not test_context.get("bot_id"):
        print("⚠️  Skipping: No bot_id available")
        return
    
    # Scrape website (using a safe test URL)
    response = make_request(
        "POST",
        "/knowledge/website/scrape",
        {
            "url": "https://example.com",
            "bot_id": test_context["bot_id"],
            "max_pages": 1,
            "follow_links": False,
            "include_sitemap": False
        },
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    success = print_result("Scrape Website", response, 201)
    
    if success:
        data = response.json()
        source_id = data.get("data", {}).get("source_id")
        if source_id:
            test_context["source_ids"].append(source_id)


# ============================================================================
# TEST 4: SOURCE MANAGEMENT
# ============================================================================

def test_source_management():
    """Test source listing and management"""
    print_section("TEST 4: Source Management")
    
    if not tokens["access_token"]:
        print("⚠️  Skipping: Not authenticated")
        return
    
    # List all sources
    response = make_request(
        "GET",
        "/knowledge/sources",
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    print_result("List All Sources", response, 200)
    
    # List sources by bot
    if test_context.get("bot_id"):
        response = make_request(
            "GET",
            "/knowledge/sources",
            {"bot_id": test_context["bot_id"]},
            token=tokens["access_token"],
            org_id=test_context["organization_id"]
        )
        
        print_result("List Bot Sources", response, 200)
    
    # Get source details
    if test_context["source_ids"]:
        source_id = test_context["source_ids"][0]
        response = make_request(
            "GET",
            f"/knowledge/sources/{source_id}",
            token=tokens["access_token"],
            org_id=test_context["organization_id"]
        )
        
        print_result("Get Source Details", response, 200)


# ============================================================================
# TEST 5: STATISTICS
# ============================================================================

def test_statistics():
    """Test knowledge base statistics"""
    print_section("TEST 5: Statistics")
    
    if not tokens["access_token"]:
        print("⚠️  Skipping: Not authenticated")
        return
    
    # Get KB stats
    response = make_request(
        "GET",
        "/knowledge/stats",
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    print_result("Get KB Statistics", response, 200)


# ============================================================================
# TEST 6: REINDEXING
# ============================================================================

def test_reindexing():
    """Test source reindexing"""
    print_section("TEST 6: Reindexing")
    
    if not test_context["source_ids"]:
        print("⚠️  Skipping: No sources to reindex")
        return
    
    source_id = test_context["source_ids"][0]
    
    # Reindex source
    response = make_request(
        "POST",
        f"/knowledge/sources/{source_id}/reindex",
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    print_result("Reindex Source", response, 200)


# ============================================================================
# TEST 7: DELETION
# ============================================================================

def test_deletion():
    """Test source deletion"""
    print_section("TEST 7: Deletion")
    
    if not test_context["source_ids"]:
        print("⚠️  Skipping: No sources to delete")
        return
    
    # Delete first source
    source_id = test_context["source_ids"][0]
    
    response = make_request(
        "DELETE",
        f"/knowledge/sources/{source_id}",
        token=tokens["access_token"],
        org_id=test_context["organization_id"]
    )
    
    print_result("Delete Source", response, 200)
    
    # Bulk delete remaining sources
    if len(test_context["source_ids"]) > 1:
        response = make_request(
            "POST",
            "/knowledge/sources/bulk-delete",
            {"source_ids": test_context["source_ids"][1:]},
            token=tokens["access_token"],
            org_id=test_context["organization_id"]
        )
        
        print_result("Bulk Delete Sources", response, 200)


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all knowledge base tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 18 + "KNOWLEDGE BASE TEST SUITE (PHASE 4)" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")
    print(f"\nBase URL: {BASE_URL}")
    print(f"Test User Email: {test_data['email']}")
    print("\nℹ️  Make sure the server is running: uvicorn app.main:app --reload")
    print("ℹ️  Make sure database and Qdrant are running")
    print("ℹ️  Make sure you have created a bot and updated test_context['bot_id']")
    
    try:
        # Setup
        setup_auth()
        setup_bot()
        
        # Run tests
        test_text_content()
        test_document_upload()
        test_web_scraping()
        test_source_management()
        test_statistics()
        test_reindexing()
        test_deletion()
        
        # Summary
        print_section("TEST SUMMARY")
        print("\n✅ All knowledge base tests completed!")
        print("\nℹ️  Notes:")
        print("   - Some tests may be skipped if bot creation is not implemented")
        print("   - Web scraping requires internet connection")
        print("   - Document upload creates chunks and embeddings")
        print("   - All operations require proper RBAC permissions")
        
        print("\n📊 Test Context:")
        print(f"   Organization ID: {test_context.get('organization_id', 'N/A')}")
        print(f"   Bot ID: {test_context.get('bot_id', 'N/A')}")
        print(f"   Sources Created: {len(test_context.get('source_ids', []))}")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to the server!")
        print("   Make sure the server is running: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()

