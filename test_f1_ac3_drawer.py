"""
测试点击 F1 精密空调-3 设备
"""
from playwright.sync_api import sync_playwright
import time

def test_device_drawer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 监听控制台消息
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        
        # 监听页面错误
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        try:
            print("1. Login...")
            page.goto('http://localhost:3000/login', wait_until='networkidle')
            page.fill('input[type="text"]', 'admin')
            page.fill('input[type="password"]', 'admin123')
            page.click('.login-btn')
            page.wait_for_url('http://localhost:3000/', timeout=10000)
            page.wait_for_load_state('networkidle')
            print("   [OK] Logged in")
            
            print("\n2. Navigate to power config...")
            page.click('text=能源管理')
            time.sleep(1)
            page.click('text=配电配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            print("   [OK] On power config page")
            
            print("\n3. Switch to shift config tab...")
            page.click('text=转移配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path='screenshot_shift_tab.png', full_page=True)
            print("   [OK] On shift config tab")
            
            print("\n4. Search for F1 精密空调-3...")
            # 查找包含 "F1" 和 "空调" 的设备链接
            devices = page.locator('.el-table__row .el-link').all()
            print(f"   Found {len(devices)} device links")
            
            target_device = None
            for device in devices:
                text = device.inner_text()
                if 'F1' in text and '空调' in text and '3' in text:
                    target_device = device
                    print(f"   Found target device: {text}")
                    break
            
            if not target_device:
                print("   [WARNING] F1 精密空调-3 not found, trying first AC device...")
                for device in devices:
                    text = device.inner_text()
                    if '空调' in text:
                        target_device = device
                        print(f"   Using device: {text}")
                        break
            
            if not target_device:
                print("   [ERROR] No suitable device found")
                print("   Available devices:")
                for i, device in enumerate(devices[:10]):
                    print(f"     {i+1}. {device.inner_text()}")
                return
            
            print("\n5. Click device to open drawer...")
            target_device.click()
            time.sleep(3)
            
            print("\n6. Check drawer state...")
            drawer = page.locator('.device-shift-detail-drawer')
            if drawer.count() > 0 and drawer.is_visible():
                print("   [OK] Drawer is visible")
                page.screenshot(path='screenshot_drawer_f1_ac3.png', full_page=True)
                
                # 检查抽屉内容
                print("\n7. Check drawer content...")
                
                # 检查标题
                title = page.locator('.device-shift-detail-drawer .device-name').inner_text()
                print(f"   Device name: {title}")
                
                # 检查图表
                chart = page.locator('.device-shift-detail-drawer .power-chart')
                if chart.count() > 0:
                    print("   [OK] Chart element exists")
                else:
                    print("   [ERROR] Chart element not found")
                
                # 检查约束条件
                constraints = page.locator('.device-shift-detail-drawer .constraint-item').count()
                print(f"   Constraint items: {constraints}")
                
                # 检查是否有错误提示
                alerts = page.locator('.device-shift-detail-drawer .el-alert').all()
                if alerts:
                    print(f"   [WARNING] Found {len(alerts)} alert(s):")
                    for alert in alerts:
                        alert_text = alert.inner_text()
                        print(f"     - {alert_text[:100]}")
                
            else:
                print("   [ERROR] Drawer not visible")
            
            print("\n8. Check console messages...")
            if console_messages:
                print(f"   Console messages ({len(console_messages)}):")
                for msg in console_messages[-20:]:
                    print(f"     {msg}")
            else:
                print("   [OK] No console messages")
            
            print("\n9. Check page errors...")
            if page_errors:
                print(f"   [ERROR] Found {len(page_errors)} error(s):")
                for err in page_errors:
                    print(f"     {err}")
            else:
                print("   [OK] No page errors")
            
            print("\n[TEST] Keeping browser open for 15 seconds...")
            time.sleep(15)
            
        except Exception as e:
            print(f"\n[ERROR] Test failed: {e}")
            page.screenshot(path='screenshot_error.png', full_page=True)
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == '__main__':
    test_device_drawer()
