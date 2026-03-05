from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # 收集控制台日志
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
    
    # 收集错误
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    print("正在打开复合规则页面...")
    page.goto('http://localhost:3000/alarm/compound')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)  # 额外等待2秒
    
    # 截图
    page.screenshot(path='compound_page.png', full_page=True)
    print("截图已保存到 compound_page.png")
    
    # 检查页面内容
    html = page.content()
    
    # 检查是否有错误提示
    error_elements = page.locator('.el-message--error').all()
    if error_elements:
        print(f"\n发现 {len(error_elements)} 个错误提示")
    
    # 检查主要容器
    main_container = page.locator('.alarm-compound-rules').count()
    print(f"\n主容器 .alarm-compound-rules 数量: {main_container}")
    
    # 检查表格
    table = page.locator('.el-table').count()
    print(f"表格 .el-table 数量: {table}")
    
    # 输出控制台日志
    if console_logs:
        print("\n=== 控制台日志 ===")
        for log in console_logs[-20:]:  # 只显示最后20条
            print(log)
    
    # 输出错误
    if errors:
        print("\n=== JavaScript 错误 ===")
        for err in errors:
            print(err)
    
    print("\n按任意键关闭浏览器...")
    input()
    browser.close()
