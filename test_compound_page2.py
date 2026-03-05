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
    page.wait_for_timeout(3000)  # 额外等待3秒
    
    # 截图
    page.screenshot(path='compound_page2.png', full_page=True)
    print("截图已保存到 compound_page2.png")
    
    # 检查主要容器
    main_container = page.locator('.compound-rule-page').count()
    print(f"\n主容器 .compound-rule-page 数量: {main_container}")
    
    # 检查统计卡片
    stat_cards = page.locator('.stat-card').count()
    print(f"统计卡片 .stat-card 数量: {stat_cards}")
    
    # 检查表格
    table = page.locator('.el-table').count()
    print(f"表格 .el-table 数量: {table}")
    
    # 检查是否有内容
    if main_container > 0:
        text_content = page.locator('.compound-rule-page').text_content()
        print(f"\n页面文本内容（前200字符）: {text_content[:200] if text_content else '无内容'}")
    
    # 输出控制台日志
    if console_logs:
        print("\n=== 控制台日志（最后30条）===")
        for log in console_logs[-30:]:
            print(log)
    
    # 输出错误
    if errors:
        print("\n=== JavaScript 错误 ===")
        for err in errors:
            print(err)
    
    # 检查网络请求
    print("\n等待查看页面状态...")
    page.wait_for_timeout(5000)
    
    browser.close()
