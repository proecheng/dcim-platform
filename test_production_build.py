"""Verify production build loads correctly via proxy server (port 3000)."""
from playwright.sync_api import sync_playwright
import sys

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Capture console errors
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    print("Navigating to http://localhost:3000 ...")
    page.goto("http://localhost:3000", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=30000)
    
    # Check if Vue app mounted (should have #app with content)
    app_el = page.locator("#app")
    inner_html = app_el.inner_html(timeout=10000)
    has_content = len(inner_html.strip()) > 100
    
    # Check for the login page or dashboard (either means app loaded)
    has_login = page.locator("input[type='text'], input[type='password'], .el-input").count() > 0
    has_dashboard = page.locator(".el-menu, .el-aside, .dashboard").count() > 0
    
    page.screenshot(path="test_production_build.png", full_page=True)
    
    print(f"App has content: {has_content}")
    print(f"Has login form: {has_login}")
    print(f"Has dashboard: {has_dashboard}")
    print(f"Console errors: {len(errors)}")
    for e in errors:
        print(f"  ERROR: {e}")
    
    # Check for the specific circular dependency error
    circular_errors = [e for e in errors if "$l" in e or "before initialization" in e]
    
    browser.close()

if circular_errors:
    print("\nFAILED: Circular dependency error still present!")
    sys.exit(1)
elif not has_content:
    print("\nFAILED: Vue app did not mount (empty #app)")
    sys.exit(1)
elif not (has_login or has_dashboard):
    print("\nFAILED: No login form or dashboard found")
    sys.exit(1)
else:
    print("\nPASSED: Production build loads correctly!")
    sys.exit(0)
