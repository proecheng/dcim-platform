from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 设置控制台日志监听
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
    
    # 设置页面错误监听
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    
    try:
        # 打开登录页面
        page.goto('http://localhost:3000')
        page.wait_for_load_state('networkidle')
        
        # 登录
        page.fill('input[type="text"]', 'admin')
        page.fill('input[type="password"]', 'admin123')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        
        # 查找并点击电池组菜单
        # 先尝试展开能源管理菜单
        try:
            energy_menu = page.locator('text=能源管理').first
            if energy_menu.is_visible():
                energy_menu.click()
                time.sleep(1)
        except:
            pass
        
        # 点击电池组菜单
        battery_link = page.locator('text=电池组').first
        battery_link.click()
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        
        # 截图
        page.screenshot(path='D:\\mytest1\\battery_page.png', full_page=True)
        
        # 输出错误信息
        print("=== Console Logs ===")
        for log in console_logs:
            print(log)
        
        print("\n=== Page Errors ===")
        for error in page_errors:
            print(error)
        
        # 等待一段时间以便观察
        
    finally:
        browser.close()
