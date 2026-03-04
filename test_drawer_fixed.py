"""
自动化测试：导航到能源配置-转移配置页面，点击设备，检查抽屉框
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # 启用控制台日志捕获
    console_logs = []
    errors = []
    
    def handle_console(msg):
        log_text = f"[{msg.type}] {msg.text}"
        console_logs.append(log_text)
        print(f"  Console: {log_text}")
        if msg.type == "error":
            errors.append(msg.text)
    
    page.on("console", handle_console)
    
    print("=" * 80)
    print("Test: Navigate to Energy Config - Shift Config and test drawer")
    print("=" * 80)
    
    try:
        # 1. Open system
        print("\n[1/6] Opening system...")
        page.goto('http://localhost:3000')
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(2)
        
        # 2. Login
        print("[2/6] Logging in...")
        if "/login" in page.url.lower():
            page.fill('input[placeholder="用户名"]', 'admin')
            page.fill('input[placeholder="密码"]', 'admin123')
            page.click('button:has-text("登 录")')
            page.wait_for_load_state('networkidle', timeout=10000)
            time.sleep(3)
        
        # 3. Navigate to energy config page
        print("[3/6] Navigating to energy config page...")
        page.goto('http://localhost:3000/#/energy/config')
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(2)
        
        # 4. Click shift config tab
        print("[4/6] Clicking shift config tab...")
        shift_tab = page.locator('text=转移配置')
        if shift_tab.count() > 0:
            shift_tab.click()
            time.sleep(2)
            print("  Shift config tab clicked")
        else:
            print("  WARNING: Shift config tab not found")
        
        # Screenshot before click
        page.screenshot(path='test_screenshots/before_device_click.png', full_page=True)
        print("  Screenshot saved: before_device_click.png")
        
        # 5. Find and click device link
        print("[5/6] Finding and clicking device link...")
        
        # Try to find any device link in the table
        device_links = page.locator('.el-table .el-link').all()
        print(f"  Found {len(device_links)} device links")
        
        if len(device_links) > 0:
            # Click the first device link
            first_device = device_links[0]
            device_name = first_device.inner_text()
            print(f"  Clicking device: {device_name}")
            first_device.click()
            time.sleep(3)
            
            # 6. Check drawer
            print("[6/6] Checking drawer...")
            
            # Screenshot after click
            page.screenshot(path='test_screenshots/after_device_click.png', full_page=True)
            print("  Screenshot saved: after_device_click.png")
            
            # Check if drawer is visible
            drawer = page.locator('.el-drawer')
            if drawer.count() > 0:
                print("  FOUND: Drawer element exists")
                
                # Check drawer visibility
                is_visible = drawer.is_visible()
                print(f"  Drawer visible: {is_visible}")
                
                if is_visible:
                    # Get drawer content
                    drawer_html = drawer.inner_html()
                    with open('test_screenshots/drawer_content.html', 'w', encoding='utf-8') as f:
                        f.write(drawer_html)
                    print("  Drawer HTML saved: drawer_content.html")
                    
                    # Check for chart element
                    chart_ref = drawer.locator('.power-chart')
                    if chart_ref.count() > 0:
                        print("  FOUND: Chart element (.power-chart)")
                    else:
                        print("  NOT FOUND: Chart element (.power-chart)")
                    
                    # Check for metric cards
                    metric_cards = drawer.locator('.metric-card').all()
                    print(f"  Found {len(metric_cards)} metric cards")
                    
                else:
                    print("  ERROR: Drawer exists but not visible")
            else:
                print("  ERROR: Drawer element not found")
        else:
            print("  ERROR: No device links found in table")
            # Show table content
            table_html = page.locator('.el-table').inner_html()
            with open('test_screenshots/table_content.html', 'w', encoding='utf-8') as f:
                f.write(table_html)
            print("  Table HTML saved for inspection")
        
        # Output console logs
        print("\n" + "=" * 80)
        print("Console Logs (last 30):")
        print("=" * 80)
        for log in console_logs[-30:]:
            print(log)
        
        # Output errors
        if errors:
            print("\n" + "=" * 80)
            print("Errors Found:")
            print("=" * 80)
            for error in errors:
                print(f"ERROR: {error}")
        
        print("\nBrowser will stay open. Press Enter to close...")
        input()
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        page.screenshot(path='test_screenshots/error.png', full_page=True)
        print("Error screenshot saved: error.png")
        import traceback
        traceback.print_exc()
    finally:
        browser.close()
