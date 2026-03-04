"""
简化版测试：直接导航并测试抽屉框
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    console_logs = []
    
    def handle_console(msg):
        if msg.type in ["error", "warning"]:
            log_text = f"[{msg.type}] {msg.text}"
            console_logs.append(log_text)
            print(f"  {log_text}")
    
    page.on("console", handle_console)
    
    print("=" * 80)
    print("Drawer Test - Energy Config Page")
    print("=" * 80)
    
    try:
        # Login
        print("\n[1/4] Login...")
        page.goto('http://localhost:3000', wait_until='load')
        time.sleep(2)
        
        if "/login" in page.url.lower():
            page.fill('input[placeholder="用户名"]', 'admin')
            page.fill('input[placeholder="密码"]', 'admin123')
            page.click('button:has-text("登 录")')
            time.sleep(4)
        
        # Navigate to config page
        print("[2/4] Navigate to /energy/config...")
        page.goto('http://localhost:3000/#/energy/config', wait_until='load')
        time.sleep(3)
        
        # Click shift tab
        print("[3/4] Click shift config tab...")
        page.click('text=转移配置')
        time.sleep(3)
        
        # Screenshot
        page.screenshot(path='test_screenshots/shift_config_page.png', full_page=True)
        print("  Screenshot: shift_config_page.png")
        
        # Find device links
        print("[4/4] Click device link...")
        device_links = page.locator('.el-table .el-link').all()
        print(f"  Found {len(device_links)} device links")
        
        if len(device_links) > 0:
            device_name = device_links[0].inner_text()
            print(f"  Clicking: {device_name}")
            device_links[0].click()
            time.sleep(3)
            
            # Check drawer
            page.screenshot(path='test_screenshots/drawer_opened.png', full_page=True)
            print("  Screenshot: drawer_opened.png")
            
            drawer = page.locator('.el-drawer')
            if drawer.count() > 0:
                is_visible = drawer.is_visible()
                print(f"  Drawer visible: {is_visible}")
                
                if is_visible:
                    # Check chart
                    chart = drawer.locator('.power-chart')
                    print(f"  Chart element found: {chart.count() > 0}")
                    
                    # Check metric cards
                    cards = drawer.locator('.metric-card').all()
                    print(f"  Metric cards: {len(cards)}")
                    
                    # Save drawer HTML
                    with open('test_screenshots/drawer.html', 'w', encoding='utf-8') as f:
                        f.write(drawer.inner_html())
                    print("  Drawer HTML saved")
                    
                    print("\n  SUCCESS: Drawer opened and rendered")
                else:
                    print("\n  ERROR: Drawer exists but not visible")
            else:
                print("\n  ERROR: Drawer not found")
        else:
            print("\n  ERROR: No device links found")
        
        if console_logs:
            print("\nConsole Errors/Warnings:")
            for log in console_logs:
                print(log)
        
        print("\nPress Enter to close...")
        input()
        
    except Exception as e:
        print(f"\nError: {e}")
        page.screenshot(path='test_screenshots/error.png', full_page=True)
        import traceback
        traceback.print_exc()
    finally:
        browser.close()
