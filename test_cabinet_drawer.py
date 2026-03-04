# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright, TimeoutError as PTimeout
import time

print("=== DCIM Cabinet Drawer Reproduction ===\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.set_default_timeout(6000)
    
    try:
        # Login
        print("[1/4] Login...")
        page.goto('http://localhost:3000')
        time.sleep(1)
        page.fill('input[type="text"]', 'admin')
        page.fill('input[type="password"]', 'admin123')
        page.click('.login-btn')
        time.sleep(3)
        print("  OK")
        
        # Navigate
        print("[2/4] Navigate...")
        page.goto('http://localhost:3000/#/power/cabinet')
        time.sleep(5)  # Long wait for data
        print(f"  URL: {page.url}")
        
        # Find rows
        print("[3/4] Find rows...")
        try:
            page.wait_for_selector('.el-table__body tr', timeout=10000)
        except PTimeout:
            print("  [FAIL] No table rows found")
            print("  This indicates:")
            print("    - Data not loaded")
            print("    - API call failed")
            print("    - Empty dataset")
            browser.close()
            sys.exit(1)
        
        rows = page.locator('.el-table__body tr').all()
        print(f"  Found {len(rows)} rows")
        
        if len(rows) == 0:
            print("  [FAIL] Zero rows")
            browser.close()
            sys.exit(1)
        
        # Click last
        print("[4/4] Click last row...")
        last = rows[-1]
        txt = last.inner_text().replace('\n', ' ')[:60]
        print(f"  Row: {txt}")
        
        last.scroll_into_view_if_needed()
        time.sleep(0.2)
        last.click()
        time.sleep(1.5)
        
        # Check drawer
        print("\n=== Drawer Check ===")
        try:
            page.wait_for_selector('.el-drawer', timeout=5000)
        except PTimeout:
            print("[FAIL] Drawer not visible")
            browser.close()
            sys.exit(1)
        
        title = page.locator('.el-drawer__title').inner_text()
        body = page.locator('.el-drawer__body').first.inner_text()
        
        print(f"Title: '{title}'")
        print(f"Body: {len(body)} chars")
        
        # Get row ID
        cell = last.locator('td').first.inner_text()
        print(f"Row ID: '{cell}'")
        print(f"ID in drawer: {cell in body if cell else False}")
        
        # Issues
        print("\n=== Issues ===")
        issues = []
        if not title.strip():
            issues.append("Empty title")
        if len(body) < 10:
            issues.append("Body too short")
        if cell and cell not in body:
            issues.append(f"Row ID '{cell}' missing in drawer")
        
        if issues:
            for i in issues:
                print(f"  - {i}")
            print(f"\nDrawer body:\n{body[:300]}")
        else:
            print("  No issues")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        browser.close()
        print("\n=== Done ===")
