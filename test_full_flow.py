from playwright.sync_api import sync_playwright
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 收集所有控制台消息
    all_console = []
    def handle_console(msg):
        all_console.append({
            'type': msg.type,
            'text': msg.text,
            'args': [str(arg) for arg in msg.args]
        })
    page.on("console", handle_console)
    
    # 收集页面错误
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    
    # 收集请求
    requests = []
    def handle_request(request):
        requests.append({
            'url': request.url,
            'method': request.method
        })
    page.on("request", handle_request)
    
    # 收集响应
    responses = []
    def handle_response(response):
        responses.append({
            'url': response.url,
            'status': response.status
        })
    page.on("response", handle_response)
    
    print("Opening login page...")
    page.goto('http://powerlab.cn:3000/login', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    print("Filling login form...")
    page.fill('input[placeholder="用户名"]', 'admin')
    page.fill('input[placeholder="密码"]', 'admin123')
    
    print("Clicking login button...")
    page.click('.login-btn')
    
    print("Waiting for navigation...")
    page.wait_for_timeout(5000)
    
    current_url = page.url
    print(f"\nAfter login URL: {current_url}")
    
    # 检查 token
    token = page.evaluate("() => localStorage.getItem('token')")
    if token:
        print(f"Token: {token[:50]}...")
    else:
        print("ERROR: No token found!")
    
    print("\nNavigating to compound rules page...")
    page.goto('http://powerlab.cn:3000/strategy/alarm-rules/compound', wait_until='networkidle')
    page.wait_for_timeout(5000)
    
    final_url = page.url
    print(f"\nFinal URL: {final_url}")
    
    # 检查页面元素
    print("\n=== Page Elements ===")
    print(f"Main container (.compound-rule-page): {page.locator('.compound-rule-page').count()}")
    print(f"Login container (.login-container): {page.locator('.login-container').count()}")
    print(f"Main layout (.main-layout): {page.locator('.main-layout').count()}")
    print(f"Any el-card: {page.locator('.el-card').count()}")
    print(f"Any el-table: {page.locator('.el-table').count()}")
    
    # 检查 #app 内容
    app_html = page.locator('#app').inner_html()
    print(f"\n#app HTML length: {len(app_html)}")
    print(f"#app content (first 500 chars):\n{app_html[:500]}")
    
    # 输出错误
    print("\n=== Console Errors ===")
    for msg in all_console:
        if msg['type'] == 'error':
            print(f"[ERROR] {msg['text']}")
    
    print("\n=== Page Errors ===")
    for err in page_errors:
        print(err)
    
    # 检查是否加载了 compound chunk
    print("\n=== Compound Chunk Requests ===")
    compound_requests = [r for r in requests if 'compound' in r['url'].lower()]
    for req in compound_requests:
        print(f"{req['method']} {req['url']}")
    
    compound_responses = [r for r in responses if 'compound' in r['url'].lower()]
    for resp in compound_responses:
        print(f"  -> {resp['status']}")
    
    print("\nPress Enter to close...")
    input()
    browser.close()
