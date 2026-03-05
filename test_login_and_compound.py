from playwright.sync_api import sync_playwright
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 收集所有控制台消息
    console_messages = []
    def handle_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text
        })
    page.on("console", handle_console)
    
    # 收集页面错误
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    
    print("Step 1: Opening login page...")
    page.goto('http://powerlab.cn:3000/login', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    print("Step 2: Logging in...")
    # 填写登录表单
    page.fill('input[placeholder*="用户名"], input[type="text"]', 'admin')
    page.fill('input[placeholder*="密码"], input[type="password"]', 'admin123')
    
    # 点击登录按钮
    page.click('button[type="submit"], button:has-text("登录")')
    
    print("Step 3: Waiting for redirect...")
    page.wait_for_timeout(3000)
    
    # 检查登录后的状态
    current_url = page.url
    print(f"\nCurrent URL after login: {current_url}")
    
    print("\nStep 4: Navigating to compound rules page...")
    page.goto('http://powerlab.cn:3000/strategy/alarm-rules/compound', wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    # 检查最终状态
    final_url = page.url
    print(f"\nFinal URL: {final_url}")
    
    title = page.title()
    print(f"Page title: {title}")
    
    # 检查主容器
    main_container = page.locator('.compound-rule-page').count()
    print(f"Main container (.compound-rule-page): {main_container}")
    
    # 检查是否还在登录页
    login_container = page.locator('.login-container').count()
    print(f"Login container (.login-container): {login_container}")
    
    # 检查 #app 内容
    app_html = page.locator('#app').inner_html()
    print(f"\n#app content (first 800 chars):\n{app_html[:800]}")
    
    # 输出所有错误和警告
    print("\n=== Console Messages (errors/warnings) ===")
    for msg in console_messages:
        if msg['type'] in ['error', 'warning']:
            print(f"[{msg['type'].upper()}] {msg['text']}")
    
    print("\n=== Page Errors ===")
    for err in page_errors:
        print(err)
    
    # 检查 localStorage 中的 token
    token = page.evaluate("() => localStorage.getItem('token')")
    print(f"\n=== Token Status ===")
    if token:
        print(f"Token exists: {token[:50]}...")
    else:
        print("No token found in localStorage")
    
    # 截图
    page.screenshot(path='compound_after_login.png', full_page=True)
    print("\nScreenshot saved to: compound_after_login.png")
    
    print("\nPress Enter to close...")
    input()
    browser.close()
