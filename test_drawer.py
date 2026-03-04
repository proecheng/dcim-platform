"""
自动化测试：导航到配电配置-转移配置页面，点击 F1 精密空调-2，检查抽屉框
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # 启用控制台日志捕获
    console_logs = []
    errors = []
    
    def handle_console(msg):
        console_logs.append(f"[{msg.type}] {msg.text}")
        if msg.type == "error":
            errors.append(msg.text)
    
    page.on("console", handle_console)
    
    print("=" * 80)
    print("导航到配电配置-转移配置页面并测试抽屉框")
    print("=" * 80)
    
    try:
        # 1. 打开系统
        print("\n[1/5] 打开系统...")
        page.goto('http://localhost:3000')
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        # 2. 登录
        print("[2/5] 登录...")
        if "/login" in page.url.lower():
            page.fill('input[placeholder="用户名"]', 'admin')
            page.fill('input[placeholder="密码"]', 'admin123')
            page.click('button:has-text("登 录")')
            page.wait_for_load_state('networkidle')
            time.sleep(3)
        
        # 3. 导航到配电配置-转移配置页面
        print("[3/5] 导航到配电配置-转移配置页面...")
        # 尝试多种可能的路由
        routes_to_try = [
            '/#/energy/shift/config',
            '/#/energy/shift/device-config',
            '/#/energy/shift/transfer-config',
            '/#/energy/shift/power-config'
        ]
        
        for route in routes_to_try:
            print(f"   尝试路由: {route}")
            page.goto(f'http://localhost:3000{route}')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            # 检查页面内容
            content = page.content()
            if "F1 精密空调" in content or "转移配置" in content or "配电配置" in content:
                print(f"   ✅ 找到页面: {route}")
                break
        else:
            print("   ⚠️ 未找到配电配置-转移配置页面，尝试通过菜单导航...")
            # 通过菜单导航
            page.goto('http://localhost:3000')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
        
        # 截图当前页面
        page.screenshot(path='test_screenshots/before_click.png', full_page=True)
        print("   截图已保存: test_screenshots/before_click.png")
        
        # 4. 查找并点击 "F1 精密空调-2"
        print("[4/5] 查找并点击 'F1 精密空调-2'...")
        
        # 尝试多种选择器
        selectors = [
            'text=F1 精密空调-2',
            ':text("F1 精密空调-2")',
            'button:has-text("F1 精密空调-2")',
            'div:has-text("F1 精密空调-2")',
            '[class*="device"]:has-text("F1 精密空调-2")',
        ]
        
        clicked = False
        for selector in selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"   找到元素: {selector}")
                    page.locator(selector).first.click()
                    clicked = True
                    print("   ✅ 点击成功")
                    break
            except Exception as e:
                print(f"   尝试 {selector} 失败: {e}")
        
        if not clicked:
            print("   ⚠️ 未找到 'F1 精密空调-2' 元素")
            print("   页面内容预览:")
            # 获取所有可点击元素
            clickable = page.locator('button, [role="button"], .el-button').all()
            for i, elem in enumerate(clickable[:10]):
                try:
                    text = elem.inner_text()
                    if text:
                        print(f"      - {text[:50]}")
                except:
                    pass
        
        # 等待抽屉框出现
        time.sleep(2)
        
        # 5. 检查抽屉框
        print("[5/5] 检查抽屉框...")
        
        # 截图抽屉框
        page.screenshot(path='test_screenshots/drawer_opened.png', full_page=True)
        print("   截图已保存: test_screenshots/drawer_opened.png")
        
        # 检查抽屉框内容
        drawer_selectors = [
            '.el-drawer',
            '[class*="drawer"]',
            '[role="dialog"]',
            '.el-dialog'
        ]
        
        drawer_found = False
        for selector in drawer_selectors:
            if page.locator(selector).count() > 0:
                print(f"   ✅ 找到抽屉框: {selector}")
                drawer_found = True
                
                # 获取抽屉框内容
                drawer = page.locator(selector).first
                drawer_html = drawer.inner_html()
                
                # 保存抽屉框 HTML
                with open('test_screenshots/drawer_content.html', 'w', encoding='utf-8') as f:
                    f.write(drawer_html)
                print("   抽屉框 HTML 已保存: test_screenshots/drawer_content.html")
                
                # 检查抽屉框中的表单元素
                inputs = drawer.locator('input').all()
                print(f"   抽屉框中的输入框数量: {len(inputs)}")
                
                selects = drawer.locator('select, .el-select').all()
                print(f"   抽屉框中的下拉框数量: {len(selects)}")
                
                buttons = drawer.locator('button').all()
                print(f"   抽屉框中的按钮数量: {len(buttons)}")
                
                break
        
        if not drawer_found:
            print("   ⚠️ 未找到抽屉框")
        
        # 输出控制台日志
        print("\n" + "=" * 80)
        print("控制台日志:")
        print("=" * 80)
        for log in console_logs[-20:]:  # 只显示最后 20 条
            print(log)
        
        # 输出错误
        if errors:
            print("\n" + "=" * 80)
            print("发现的错误:")
            print("=" * 80)
            for error in errors:
                print(f"❌ {error}")
        
        print("\n浏览器将保持打开状态，按 Enter 键关闭...")
        input()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        page.screenshot(path='test_screenshots/error.png', full_page=True)
        print("错误截图已保存: test_screenshots/error.png")
        raise
    finally:
        browser.close()
