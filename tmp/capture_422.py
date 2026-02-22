"""捕获所有 422 错误的具体 URL 和请求参数"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

errors_422 = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # 拦截所有响应
    def on_response(response):
        if response.status == 422:
            req = response.request
            post_data = req.post_data or ""
            errors_422.append({
                "url": req.url,
                "method": req.method,
                "post_data": post_data[:500],
                "response": ""
            })
            try:
                body = response.text()
                errors_422[-1]["response"] = body[:500]
            except:
                pass
    
    page.on("response", on_response)
    
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
    
    # 遍历所有页面
    pages = [
        "/dashboard", "/alarm",
        "/energy/monitor", "/energy/topology", "/energy/statistics",
        "/environment/overview", "/environment/temperature", "/environment/water-leak", "/environment/smoke-infrared",
        "/power/overview", "/cooling/overview", "/cooling/cold-aisle",
        "/security/overview", "/security/access-control", "/security/fire-linkage",
        "/asset", "/capacity",
        "/gateway", "/device-manage", "/device-status",
        "/operation/workorder", "/operation/inspection", "/operation/knowledge",
        "/system/users", "/system/logs", "/system/sites",
        "/reports", "/topology/site-selection",
        "/bigscreen",
    ]
    
    for path in pages:
        url = f"http://localhost:3000{path}"
        before = len(errors_422)
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)
        after = len(errors_422)
        if after > before:
            print(f"  {path}: {after - before} x 422")
    
    browser.close()

print(f"\n{'='*60}")
print(f"共捕获 {len(errors_422)} 个 422 错误")
print(f"{'='*60}")
for i, e in enumerate(errors_422):
    print(f"\n[{i+1}] {e['method']} {e['url']}")
    if e['post_data']:
        print(f"    请求: {e['post_data'][:200]}")
    print(f"    响应: {e['response'][:300]}")
