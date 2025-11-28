"""
Test proper API authentication with CSRF handling.
"""
import requests
import re

BASE_URL = "http://localhost:5000"

def test_api_authentication():
    """Test authentication flow with proper CSRF handling."""
    session = requests.Session()
    
    # Step 1: Get login page and extract CSRF token
    print("Step 1: Getting login page...")
    resp = session.get(f"{BASE_URL}/auth/login", timeout=10)
    print(f"  Status: {resp.status_code}")
    
    # Extract CSRF token from hidden input
    match = re.search(r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', resp.text)
    if not match:
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    
    if match:
        csrf_token = match.group(1)
        print(f"  CSRF Token: {csrf_token[:20]}...")
    else:
        print("  ERROR: No CSRF token found in login page")
        # Try to find any csrf_token mention
        matches = re.findall(r'csrf_token[^>]*>', resp.text)
        print(f"  Found csrf mentions: {matches[:3]}")
        return False
    
    # Step 2: Login with credentials
    print("\nStep 2: Logging in...")
    login_data = {
        "email": "agent_tester@mina.ai",
        "password": "test123",
        "csrf_token": csrf_token
    }
    
    resp = session.post(
        f"{BASE_URL}/auth/login",
        data=login_data,
        allow_redirects=False,
        timeout=10
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Location: {resp.headers.get('Location', 'N/A')}")
    
    # Step 3: Follow redirect to verify session
    if resp.status_code in [302, 303]:
        print("\nStep 3: Following redirect...")
        resp = session.get(resp.headers['Location'], allow_redirects=True, timeout=10)
        print(f"  Status: {resp.status_code}")
    
    # Step 4: Test API access
    print("\nStep 4: Testing API access...")
    api_resp = session.get(f"{BASE_URL}/api/tasks/", timeout=10)
    print(f"  Status: {api_resp.status_code}")
    
    if api_resp.status_code == 200:
        data = api_resp.json()
        tasks = data.get('tasks', [])
        print(f"  Tasks found: {len(tasks)}")
        
        if tasks:
            for i, task in enumerate(tasks[:3]):
                print(f"    [{i+1}] {task.get('title', 'N/A')[:50]}")
            return True
        else:
            print("  WARNING: No tasks in response")
            return True
    elif api_resp.status_code == 401:
        print("  ERROR: Not authenticated")
        data = api_resp.json()
        print(f"  Message: {data.get('error', 'N/A')}")
        return False
    else:
        print(f"  Unexpected status: {api_resp.status_code}")
        return False

if __name__ == "__main__":
    success = test_api_authentication()
    print("\n" + "=" * 50)
    if success:
        print("✅ Authentication test PASSED")
    else:
        print("❌ Authentication test FAILED")
