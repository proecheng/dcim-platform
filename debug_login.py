"""
Debug script to inspect login page
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("Navigating to http://localhost:3000...")
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    
    print(f"Current URL: {page.url}")
    print(f"Page title: {page.title()}")
    
    # Take screenshot
    page.screenshot(path='test_screenshots/debug_login.png', full_page=True)
    print("Screenshot saved to test_screenshots/debug_login.png")
    
    # Find all input fields
    inputs = page.locator('input').all()
    print(f"\nFound {len(inputs)} input fields:")
    for i, inp in enumerate(inputs):
        try:
            placeholder = inp.get_attribute('placeholder')
            input_type = inp.get_attribute('type')
            print(f"  Input {i+1}: type={input_type}, placeholder={placeholder}")
        except:
            pass
    
    # Find all buttons
    buttons = page.locator('button').all()
    print(f"\nFound {len(buttons)} buttons:")
    for i, btn in enumerate(buttons):
        try:
            text = btn.inner_text()
            print(f"  Button {i+1}: text='{text}'")
        except:
            pass
    
    print("\nPress Enter to close browser...")
    input()
    browser.close()
