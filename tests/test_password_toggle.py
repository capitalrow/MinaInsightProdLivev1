"""
Automated test for password visibility toggle on registration page.
Tests both click and touch interactions.
"""
import pytest
from playwright.sync_api import sync_playwright, expect
import time

BASE_URL = "http://localhost:5000"


def test_password_toggle_click():
    """Test that clicking the eye icon toggles password visibility."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(f"{BASE_URL}/auth/register")
        page.wait_for_load_state("domcontentloaded")
        
        password_input = page.locator("#password")
        toggle_button = page.locator(".password-toggle[data-target='password']")
        
        expect(password_input).to_have_attribute("type", "password")
        print("Initial state: password is hidden (type=password)")
        
        toggle_button.click()
        time.sleep(0.2)
        
        input_type_after_click = password_input.get_attribute("type")
        print(f"After click: input type = {input_type_after_click}")
        
        assert input_type_after_click == "text", f"Expected 'text' but got '{input_type_after_click}'"
        print("SUCCESS: Password is now visible (type=text)")
        
        toggle_button.click()
        time.sleep(0.2)
        
        input_type_after_second_click = password_input.get_attribute("type")
        print(f"After second click: input type = {input_type_after_second_click}")
        
        assert input_type_after_second_click == "password", f"Expected 'password' but got '{input_type_after_second_click}'"
        print("SUCCESS: Password is hidden again (type=password)")
        
        browser.close()
        print("\n✅ All password toggle tests passed!")


def test_confirm_password_toggle_click():
    """Test that clicking the eye icon toggles confirm password visibility."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(f"{BASE_URL}/auth/register")
        page.wait_for_load_state("domcontentloaded")
        
        confirm_input = page.locator("#confirm_password")
        toggle_button = page.locator(".password-toggle[data-target='confirm_password']")
        
        expect(confirm_input).to_have_attribute("type", "password")
        print("Initial state: confirm password is hidden (type=password)")
        
        toggle_button.click()
        time.sleep(0.2)
        
        input_type_after_click = confirm_input.get_attribute("type")
        print(f"After click: input type = {input_type_after_click}")
        
        assert input_type_after_click == "text", f"Expected 'text' but got '{input_type_after_click}'"
        print("SUCCESS: Confirm password is now visible (type=text)")
        
        browser.close()
        print("\n✅ Confirm password toggle test passed!")


def test_password_toggle_mobile_simulation():
    """Test password toggle with mobile device simulation (touch events)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (Linux; Android 16; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.7444.102 Mobile Safari/537.36"
        )
        page = context.new_page()
        
        page.goto(f"{BASE_URL}/auth/register")
        page.wait_for_load_state("domcontentloaded")
        
        password_input = page.locator("#password")
        toggle_button = page.locator(".password-toggle[data-target='password']")
        
        expect(password_input).to_have_attribute("type", "password")
        print("Mobile: Initial state: password is hidden")
        
        toggle_button.tap()
        time.sleep(0.3)
        
        input_type_after_tap = password_input.get_attribute("type")
        print(f"Mobile: After tap: input type = {input_type_after_tap}")
        
        assert input_type_after_tap == "text", f"Mobile tap failed! Expected 'text' but got '{input_type_after_tap}'"
        print("SUCCESS: Mobile tap toggled password visibility!")
        
        toggle_button.tap()
        time.sleep(0.3)
        
        input_type_after_second_tap = password_input.get_attribute("type")
        assert input_type_after_second_tap == "password", f"Expected 'password' but got '{input_type_after_second_tap}'"
        print("SUCCESS: Mobile second tap hid password again!")
        
        context.close()
        browser.close()
        print("\n✅ Mobile password toggle test passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Password Visibility Toggle")
    print("=" * 60)
    
    print("\n--- Test 1: Desktop Click ---")
    test_password_toggle_click()
    
    print("\n--- Test 2: Confirm Password Toggle ---")
    test_confirm_password_toggle_click()
    
    print("\n--- Test 3: Mobile Touch Simulation ---")
    test_password_toggle_mobile_simulation()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
