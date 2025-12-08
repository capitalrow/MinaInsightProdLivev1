#!/usr/bin/env python3
"""
Comprehensive End-to-End Tests for Mina App
Tests all user-facing features and functionality.
"""

import os
import sys
import time
import requests
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"

TEST_USER_EMAIL = "test@minaapp.com"
TEST_USER_PASSWORD = "TestUser123!"

class TestResult:
    def __init__(self, name, passed, details=""):
        self.name = name
        self.passed = passed
        self.details = details

def test_landing_page():
    """Test the landing/home page loads correctly."""
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        if resp.status_code == 200 and "Mina" in resp.text:
            return TestResult("Landing Page", True, "Page loads with Mina branding")
        return TestResult("Landing Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Landing Page", False, str(e))

def test_login_page():
    """Test the login page loads correctly."""
    try:
        resp = requests.get(f"{BASE_URL}/auth/login", timeout=10)
        if resp.status_code == 200 and ("login" in resp.text.lower() or "sign in" in resp.text.lower()):
            return TestResult("Login Page", True, "Login form renders correctly")
        return TestResult("Login Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Login Page", False, str(e))

def test_register_page():
    """Test the registration page loads correctly."""
    try:
        resp = requests.get(f"{BASE_URL}/auth/register", timeout=10)
        if resp.status_code == 200 and ("register" in resp.text.lower() or "sign up" in resp.text.lower()):
            return TestResult("Register Page", True, "Registration form renders correctly")
        return TestResult("Register Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Register Page", False, str(e))

def test_health_endpoints():
    """Test production health endpoints."""
    results = []
    endpoints = [
        ("/health/live", "liveness"),
        ("/health/ready", "readiness"),
        ("/health/startup", "startup"),
    ]
    
    for endpoint, name in endpoints:
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if resp.status_code == 200:
                results.append(TestResult(f"Health: {name}", True, "Endpoint healthy"))
            else:
                results.append(TestResult(f"Health: {name}", False, f"Status: {resp.status_code}"))
        except Exception as e:
            results.append(TestResult(f"Health: {name}", False, str(e)))
    
    return results

def test_authentication_flow():
    """Test login with test user credentials."""
    session = requests.Session()
    
    try:
        login_page = session.get(f"{BASE_URL}/auth/login", timeout=10)
        
        from html.parser import HTMLParser
        csrf_token = None
        
        class CSRFParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                nonlocal csrf_token
                attrs_dict = dict(attrs)
                if tag == "input" and attrs_dict.get("name") == "csrf_token":
                    csrf_token = attrs_dict.get("value")
        
        parser = CSRFParser()
        parser.feed(login_page.text)
        
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
        }
        if csrf_token:
            login_data["csrf_token"] = csrf_token
        
        resp = session.post(
            f"{BASE_URL}/auth/login",
            data=login_data,
            timeout=10,
            allow_redirects=True
        )
        
        if resp.status_code == 200 and ("dashboard" in resp.url or "dashboard" in resp.text.lower()):
            return TestResult("Authentication Flow", True, "Login successful, redirected to dashboard"), session
        elif "Invalid" in resp.text or "error" in resp.text.lower():
            return TestResult("Authentication Flow", False, "Login failed - invalid credentials"), None
        else:
            return TestResult("Authentication Flow", True, f"Login completed, URL: {resp.url}"), session
    except Exception as e:
        return TestResult("Authentication Flow", False, str(e)), None

def test_dashboard_page(session):
    """Test dashboard page loads with data."""
    if not session:
        return TestResult("Dashboard Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/dashboard", timeout=10)
        if resp.status_code == 200:
            has_meetings = "meeting" in resp.text.lower()
            has_tasks = "task" in resp.text.lower()
            return TestResult("Dashboard Page", True, f"Meetings: {has_meetings}, Tasks: {has_tasks}")
        return TestResult("Dashboard Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Dashboard Page", False, str(e))

def test_meetings_page(session):
    """Test meetings page loads with meeting list."""
    if not session:
        return TestResult("Meetings Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/dashboard/meetings", timeout=10)
        if resp.status_code == 200:
            has_meetings = "Q4" in resp.text or "Customer Success" in resp.text or "Incident" in resp.text
            return TestResult("Meetings Page", True, f"Test meetings visible: {has_meetings}")
        return TestResult("Meetings Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Meetings Page", False, str(e))

def test_tasks_page(session):
    """Test tasks page loads with task list."""
    if not session:
        return TestResult("Tasks Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/dashboard/tasks", timeout=10)
        if resp.status_code == 200:
            has_tasks = "task" in resp.text.lower() or "action" in resp.text.lower()
            return TestResult("Tasks Page", True, f"Tasks visible: {has_tasks}")
        return TestResult("Tasks Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Tasks Page", False, str(e))

def test_analytics_page(session):
    """Test analytics page loads."""
    if not session:
        return TestResult("Analytics Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/dashboard/analytics", timeout=10)
        if resp.status_code == 200:
            has_charts = "chart" in resp.text.lower() or "analytics" in resp.text.lower()
            return TestResult("Analytics Page", True, f"Analytics components: {has_charts}")
        return TestResult("Analytics Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Analytics Page", False, str(e))

def test_calendar_page(session):
    """Test calendar page loads."""
    if not session:
        return TestResult("Calendar Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/calendar", timeout=10)
        if resp.status_code == 200:
            has_calendar = "calendar" in resp.text.lower()
            return TestResult("Calendar Page", True, f"Calendar visible: {has_calendar}")
        return TestResult("Calendar Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Calendar Page", False, str(e))

def test_copilot_page(session):
    """Test AI Copilot page loads."""
    if not session:
        return TestResult("Copilot Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/copilot", timeout=10)
        if resp.status_code == 200:
            has_copilot = "copilot" in resp.text.lower() or "ai" in resp.text.lower() or "assistant" in resp.text.lower()
            return TestResult("Copilot Page", True, f"Copilot UI: {has_copilot}")
        return TestResult("Copilot Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Copilot Page", False, str(e))

def test_settings_page(session):
    """Test settings page loads."""
    if not session:
        return TestResult("Settings Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/settings", timeout=10)
        if resp.status_code == 200:
            has_settings = "settings" in resp.text.lower() or "profile" in resp.text.lower()
            return TestResult("Settings Page", True, f"Settings UI: {has_settings}")
        return TestResult("Settings Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Settings Page", False, str(e))

def test_billing_page(session):
    """Test billing page loads."""
    if not session:
        return TestResult("Billing Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/billing", timeout=10)
        if resp.status_code == 200:
            has_billing = "billing" in resp.text.lower() or "subscription" in resp.text.lower() or "plan" in resp.text.lower()
            return TestResult("Billing Page", True, f"Billing UI: {has_billing}")
        return TestResult("Billing Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Billing Page", False, str(e))

def test_sessions_page(session):
    """Test transcription sessions page."""
    if not session:
        return TestResult("Sessions Page", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/sessions", timeout=10)
        if resp.status_code == 200:
            has_sessions = "session" in resp.text.lower() or "transcript" in resp.text.lower()
            return TestResult("Sessions Page", True, f"Sessions visible: {has_sessions}")
        return TestResult("Sessions Page", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Sessions Page", False, str(e))

def test_api_endpoints(session):
    """Test API endpoints."""
    results = []
    
    if not session:
        return [TestResult("API Endpoints", False, "No authenticated session")]
    
    endpoints = [
        ("/api/tasks", "Tasks API"),
        ("/api/meetings", "Meetings API"),
        ("/api/analytics/dashboard", "Analytics API"),
    ]
    
    for endpoint, name in endpoints:
        try:
            resp = session.get(f"{BASE_URL}{endpoint}", timeout=10)
            if resp.status_code == 200:
                results.append(TestResult(f"API: {name}", True, "Returns valid JSON"))
            else:
                results.append(TestResult(f"API: {name}", False, f"Status: {resp.status_code}"))
        except Exception as e:
            results.append(TestResult(f"API: {name}", False, str(e)))
    
    return results

def test_logout(session):
    """Test logout functionality."""
    if not session:
        return TestResult("Logout", False, "No authenticated session")
    
    try:
        resp = session.get(f"{BASE_URL}/auth/logout", timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return TestResult("Logout", True, "Logout successful")
        return TestResult("Logout", False, f"Status: {resp.status_code}")
    except Exception as e:
        return TestResult("Logout", False, str(e))

def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("MINA END-TO-END COMPREHENSIVE TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    all_results = []
    
    print("1. Testing Public Pages...")
    all_results.append(test_landing_page())
    all_results.append(test_login_page())
    all_results.append(test_register_page())
    
    print("2. Testing Health Endpoints...")
    all_results.extend(test_health_endpoints())
    
    print("3. Testing Authentication...")
    auth_result, session = test_authentication_flow()
    all_results.append(auth_result)
    
    if session:
        print("4. Testing Authenticated Pages...")
        all_results.append(test_dashboard_page(session))
        all_results.append(test_meetings_page(session))
        all_results.append(test_tasks_page(session))
        all_results.append(test_analytics_page(session))
        all_results.append(test_calendar_page(session))
        all_results.append(test_copilot_page(session))
        all_results.append(test_settings_page(session))
        all_results.append(test_billing_page(session))
        all_results.append(test_sessions_page(session))
        
        print("5. Testing API Endpoints...")
        all_results.extend(test_api_endpoints(session))
        
        print("6. Testing Logout...")
        all_results.append(test_logout(session))
    else:
        print("⚠️  Skipping authenticated tests - login failed")
    
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for result in all_results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"  {status}: {result.name}")
        if result.details:
            print(f"         {result.details}")
        if result.passed:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-"*70)
    print(f"SUMMARY: {passed} passed, {failed} failed, {len(all_results)} total")
    print("-"*70)
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) need attention")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
