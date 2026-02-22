"""深度诊断：为什么 alarm/gateway/logs/topology 页面在 headless 中不渲染"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # 收集所有控制台消息
    all_msgs = []
    page.on("console", lambda msg: all_msgs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: all_msgs.append(f"[PAGE_ERROR] {err}"))
    
    # 登录
    page.goto("http://localhost:3000", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    username_input = page.query_selector("input[type='text'], input[placeholder*='用户'], input[placeholder*='账号']")
    password_input = page.query_selector("input[type='password']")
    if username_input and password_input:
        username_input.fill("admin")
        password_input.fill("admin123")
        page.wait_for_timeout(500)
        login_btn = page.query_selector("button[type='submit'], button:has-text('登录'), .login-btn, .el-button--primary")
        if login_btn:
            login_btn.click()
            page.wait_for_timeout(4000)
    
    print(f"登录后: {page.url}")
    
    # 先验证 dashboard 能正常渲染
    page.goto("http://localhost:3000/dashboard", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    dash_text = page.inner_text("body")[:100] if page.query_selector("body") else "NO BODY"
    print(f"Dashboard body text: {len(dash_text)} chars: {dash_text[:80]}")
    
    # 现在测试 alarm
    all_msgs.clear()
    print("\n--- 测试 /alarm ---")
    page.goto("http://localhost:3000/alarm", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)
    
    # 检查 #app 内容
    app_el = page.query_selector("#app")
    app_html = app_el.inner_html()[:500] if app_el else "NO #app"
    app_text = app_el.inner_text()[:200] if app_el else ""
    print(f"#app HTML length: {len(app_html)}")
    print(f"#app HTML: {app_html[:300]}")
    print(f"#app text: '{app_text[:100]}'")
    
    # 检查 Vue 是否挂载
    vue_mounted = page.evaluate("() => { const app = document.querySelector('#app'); return app && app.__vue_app__ ? true : false }")
    print(f"Vue mounted: {vue_mounted}")
    
    # 检查路由
    try:
        route = page.evaluate("() => { const app = document.querySelector('#app'); if (app && app.__vue_app__) { const router = app.__vue_app__.config.globalProperties.$router; return router ? router.currentRoute.value.path : 'no router'; } return 'no vue'; }")
        print(f"Vue route: {route}")
    except Exception as e:
        print(f"Route check error: {e}")
    
    if all_msgs:
        print(f"\nConsole messages ({len(all_msgs)}):")
        for m in all_msgs[:15]:
            print(f"  {m[:150]}")
    
    page.screenshot(path="D:/mytest1/tmp/verify3_alarm.png")
    
    browser.close()
