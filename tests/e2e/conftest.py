"""
E2E test configuration and fixtures for Playwright browser tests.
Handles authentication and page setup for AI Proposals and Tasks testing.
"""
import pytest
import os
import sys
from pathlib import Path
from playwright.sync_api import Page, Browser, BrowserContext

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:5000')
TEST_USER_EMAIL = 'analytics_test@example.com'
TEST_USER_PASSWORD = 'testpass123'


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context with viewport and permissions."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def authenticated_page(page: Page) -> Page:
    """Fixture that provides an authenticated page session."""
    page.goto(f"{BASE_URL}/auth/login")
    page.wait_for_load_state('networkidle')
    
    page.fill('input[name="email"], input[type="email"], #email', TEST_USER_EMAIL)
    page.fill('input[name="password"], input[type="password"], #password', TEST_USER_PASSWORD)
    
    page.click('button[type="submit"], input[type="submit"]')
    
    try:
        page.wait_for_url(f"{BASE_URL}/dashboard**", timeout=10000)
    except:
        page.wait_for_selector('.dashboard, .tasks-container, .meetings-list', timeout=10000)
    
    page.wait_for_load_state('networkidle')
    
    return page


@pytest.fixture(scope="function")
def tasks_page(authenticated_page: Page) -> Page:
    """Fixture that provides a page navigated to the tasks dashboard."""
    authenticated_page.goto(f"{BASE_URL}/dashboard/tasks")
    
    authenticated_page.wait_for_load_state('networkidle')
    
    try:
        authenticated_page.wait_for_selector('.tasks-container, .task-list, #tasks-page', timeout=15000)
    except:
        authenticated_page.wait_for_timeout(3000)
    
    return authenticated_page
