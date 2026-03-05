from playwright.sync_api import sync_playwright
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    print("Step 1: Opening login page...")
    page.goto('http://localhost:3000/login', wait_until='networkidle')
    page.wait_for_timeout(2000)
    
    print("Step 2: Logging in...")
    page.fill('input[placeholder="用户名"]', 'admin')
    page.fill('input[placeholder="密码"]', 'admin123')
    page.click('.login-btn')
    
    print("Step 3: Waiting for redirect...")
    page.wait_for_timeout(5000)
    
    print("Step 4: Navigating to diagnosis rules page...")
    # 尝试通过菜单导航
    page.goto('http://localhost:3000/strategy/diagnosis/rules', wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    current_url = page.url
    print(f"\nCurrent URL: {current_url}")
    
    # 截图
    page.screenshot(path='diagnosis_rules_page.png', full_page=True)
    print("Screenshot saved to: diagnosis_rules_page.png")
    
    # 检查页面元素
    print("\n=== Page Elements ===")
    
    # 检查主要容器
    main_containers = [
        '.diagnosis-rules',
        '.diagnostic-rules', 
        '.diagnosis-page',
        '.el-table',
        '.el-card'
    ]
    
    for selector in main_containers:
        count = page.locator(selector).count()
        if count > 0:
            print(f"{selector}: {count}")
    
    # 获取页面标题
    title = page.title()
    print(f"\nPage title: {title}")
    
    # 检查是否有表格数据
    table_rows = page.locator('.el-table__row').count()
    print(f"Table rows: {table_rows}")
    
    # 检查是否有按钮
    buttons = page.locator('button').all()
    print(f"\nButtons found: {len(buttons)}")
    for i, btn in enumerate(buttons[:10]):  # 只显示前10个
        text = btn.inner_text()
        if text.strip():
            print(f"  - {text.strip()}")
    
    # 获取页面主要内容
    app_html = page.locator('#app').inner_html()
    print(f"\n#app HTML length: {len(app_html)}")
    
    # 检查是否有表单
    forms = page.locator('form, .el-form').count()
    print(f"Forms: {forms}")
    
    # 检查是否有对话框
    dialogs = page.locator('.el-dialog').count()
    print(f"Dialogs: {dialogs}")
    
    print("\nPress Enter to close...")
    input()
    browser.close()
