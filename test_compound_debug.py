from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 收集所有控制台消息
    console_messages = []
    def handle_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location
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
    
    print("正在打开复合规则页面...")
    try:
        page.goto('http://localhost:3000/alarm/compound', wait_until='networkidle', timeout=30000)
    except Exception as e:
        print(f"页面加载超时或失败: {e}")
    
    page.wait_for_timeout(2000)
    
    # 输出所有收集到的信息
    print("\n=== 控制台消息 ===")
    for msg in console_messages:
        print(f"[{msg['type']}] {msg['text']}")
        if msg['location']:
            print(f"  位置: {msg['location']}")
    
    print("\n=== 页面错误 ===")
    for err in page_errors:
        print(err)
    
    print("\n=== 网络错误 ===")
    for err in network_errors:
        print(err)
    
    # 检查页面HTML
    html = page.content()
    if 'compound-rule-page' in html:
        print("\n✓ HTML中包含 compound-rule-page 类")
    else:
        print("\n✗ HTML中不包含 compound-rule-page 类")
        # 输出body内容的前500字符
        body = page.locator('body').inner_html()
        print(f"\nBody内容（前500字符）:\n{body[:500]}")
    
    print("\n按Enter关闭浏览器...")
    input()
    browser.close()
