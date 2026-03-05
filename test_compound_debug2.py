from playwright.sync_api import sync_playwright
import sys
import io

# 设置输出编码为UTF-8
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
    
    # 收集所有错误
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    
    # 收集网络错误
    network_errors = []
    def handle_response(response):
        if response.status >= 400:
            network_errors.append(f"{response.status} {response.url}")
    page.on("response", handle_response)
    
    print("Opening compound rules page...")
    try:
        page.goto('http://localhost:3000/alarm/compound', wait_until='networkidle', timeout=30000)
    except Exception as e:
        print(f"Page load timeout or failed: {e}")
    
    page.wait_for_timeout(2000)
    
    # Output all collected information
    print("\n=== Console Messages ===")
    if console_messages:
        for msg in console_messages:
            print(f"[{msg['type']}] {msg['text']}")
    else:
        print("No console messages")
    
    print("\n=== Page Errors ===")
    if page_errors:
        for err in page_errors:
            print(err)
    else:
        print("No page errors")
    
    print("\n=== Network Errors ===")
    if network_errors:
        for err in network_errors:
            print(err)
    else:
        print("No network errors")
    
    # Check page HTML
    html = page.content()
    if 'compound-rule-page' in html:
        print("\n[OK] HTML contains compound-rule-page class")
    else:
        print("\n[ERROR] HTML does not contain compound-rule-page class")
        # Output first 500 chars of body
        body = page.locator('body').inner_html()
        print(f"\nBody content (first 500 chars):\n{body[:500]}")
    
    # Check if Vue app mounted
    app_element = page.locator('#app').count()
    print(f"\n#app element count: {app_element}")
    
    if app_element > 0:
        app_html = page.locator('#app').inner_html()
        print(f"#app content (first 300 chars):\n{app_html[:300]}")
    
    print("\nPress Enter to close browser...")
    input()
    browser.close()
