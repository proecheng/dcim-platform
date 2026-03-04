"""
测试转移配置抽屉对话框
"""
from playwright.sync_api import sync_playwright
import time

def test_shift_drawer():
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
            print("1. 登录系统...")
            page.goto('http://localhost:3000/login', wait_until='networkidle')
            page.fill('input[type="text"]', 'admin')
            page.fill('input[type="password"]', 'admin123')
            page.click('.login-btn')
            page.wait_for_url('http://localhost:3000/', timeout=10000)
            page.wait_for_load_state('networkidle')
            print("   [OK] 登录成功")
            
            print("\n2. 导航到配电配置页面...")
            page.click('text=能源管理')
            time.sleep(1)
            page.click('text=配电配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            print("   [OK] 已进入配电配置页面")
            
            print("\n3. 切换到转移配置标签页...")
            page.click('text=转移配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path='screenshot_shift_tab.png', full_page=True)
            print("   [OK] 已切换到转移配置")
            
            print("\n4. 检查表格数据...")
            rows = page.locator('.el-table__row').count()
            print(f"   表格行数: {rows}")
            
            if rows > 0:
                print("\n5. 点击第一行的设备名称链接...")
                # 等待表格加载完成
                page.wait_for_selector('.el-table__row', timeout=5000)
                
                # 点击第一行的设备名称链接
                first_link = page.locator('.el-table__row').first.locator('.el-link')
                device_name = first_link.inner_text()
                print(f"   点击设备: {device_name}")
                
                first_link.click()
                
                # 等待抽屉出现
                time.sleep(2)
                
                print("\n6. 检查抽屉是否出现...")
                drawer = page.locator('.device-shift-detail-drawer')
                drawer_count = drawer.count()
                print(f"   抽屉元素数量: {drawer_count}")
                
                if drawer_count > 0:
                    is_visible = drawer.is_visible()
                    print(f"   抽屉是否可见: {is_visible}")
                    
                    if is_visible:
                        print("   [OK] 抽屉已显示")
                        page.screenshot(path='screenshot_drawer_open.png', full_page=True)
                    else:
                        print("   [ERROR] 抽屉元素存在但不可见")
                        # 检查 display 和 visibility 样式
                        display = drawer.evaluate('el => window.getComputedStyle(el).display')
                        visibility = drawer.evaluate('el => window.getComputedStyle(el).visibility')
                        print(f"   display: {display}, visibility: {visibility}")
                else:
                    print("   [ERROR] 抽屉元素不存在")
                
                page.screenshot(path='screenshot_after_click.png', full_page=True)
            else:
                print("   [WARNING] 表格无数据")
            
            print("\n7. 检查控制台消息...")
            if console_messages:
                print(f"   控制台消息 ({len(console_messages)} 条):")
                for msg in console_messages[-10:]:  # 只显示最后10条
                    print(f"     {msg}")
            else:
                print("   [OK] 无控制台消息")
            
            print("\n8. 检查页面错误...")
            if page_errors:
                print(f"   [ERROR] 发现 {len(page_errors)} 个页面错误:")
                for err in page_errors:
                    print(f"     {err}")
            else:
                print("   [OK] 无页面错误")
            
            print("\n测试完成！保持浏览器打开 10 秒...")
            time.sleep(10)
            
        except Exception as e:
            print(f"\n[ERROR] 测试失败: {e}")
            page.screenshot(path='screenshot_error.png', full_page=True)
            raise
        finally:
            browser.close()

if __name__ == '__main__':
    test_shift_drawer()
