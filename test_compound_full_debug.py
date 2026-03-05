from playwright.sync_api import sync_playwright
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 收集所有控制台消息（包括错误）
    console_messages = []
    def handle_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': str(msg.location) if msg.location else None
        })
    page.on("console", handle_console)
    
    # 收集页面错误
    page_errors = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    
    # 收集请求失败
    failed_requests = []
    def handle_response(response):
        if response.status >= 400:
            failed_requests.append({
                'url': response.url,
                'status': response.status,
                'statusText': response.status_text
            })
    page.on("response", handle_response)
    
    print("Opening compound rules page...")
    try:
        page.goto('http://powerlab.cn:3000/strategy/alarm-rules/compound', wait_until='networkidle', timeout=30000)
    except Exception as e:
        print(f"Navigation error: {e}")
    
    page.wait_for_timeout(3000)
    
    # 检查页面状态
    print("\n=== Page Status ===")
    title = page.title()
    print(f"Page title: {title}")
    
    url = page.url
    print(f"Current URL: {url}")
    
    # 检查主容器
    main_container = page.locator('.compound-rule-page').count()
    print(f"Main container count: {main_container}")
    
    # 检查 #app
    app_html = page.locator('#app').inner_html()
    print(f"\n#app content (first 500 chars):\n{app_html[:500]}")
    
    # 输出控制台消息
    print("\n=== Console Messages ===")
    if console_messages:
        for msg in console_messages:
            if msg['type'] in ['error', 'warning']:
                print(f"[{msg['type'].upper()}] {msg['text']}")
                if msg['location']:
                    print(f"  Location: {msg['location']}")
    else:
        print("No console messages")
    
    # 输出页面错误
    print("\n=== Page Errors ===")
    if page_errors:
        for err in page_errors:
            print(err)
    else:
        print("No page errors")
    
    # 输出失败的请求
    print("\n=== Failed Requests ===")
    if failed_requests:
        for req in failed_requests:
            print(f"{req['status']} {req['statusText']}: {req['url']}")
    else:
        print("No failed requests")
    
    print("\nPress Enter to close...")
    input()
    browser.close()
