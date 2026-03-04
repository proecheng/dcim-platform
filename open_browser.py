"""
打开浏览器查看系统状态
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    print("正在打开系统...")
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    
    print(f"当前 URL: {page.url}")
    
    # 如果在登录页面，进行登录
    if "/login" in page.url or "login" in page.url.lower():
        print("检测到登录页面，正在登录...")
        
        # 填写登录表单
        page.fill('input[placeholder="用户名"]', 'admin')
        page.fill('input[placeholder="密码"]', 'admin123')
        
        # 点击登录按钮
        page.click('button:has-text("登 录")')
        
        # 等待登录完成
        page.wait_for_load_state('networkidle')
        time.sleep(3)
        
        print(f"登录后 URL: {page.url}")
    
    # 截图主页
    page.screenshot(path='test_screenshots/homepage.png', full_page=True)
    print("主页截图已保存: test_screenshots/homepage.png")
    
    # 导航到负荷转移页面
    print("\n正在导航到负荷转移页面...")
    page.goto('http://localhost:3000/#/energy/shift/execution/list')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    
    # 截图执行列表页面
    page.screenshot(path='test_screenshots/shift_execution_list.png', full_page=True)
    print("执行列表页面截图已保存: test_screenshots/shift_execution_list.png")
    
    # 检查页面内容
    content = page.content()
    if "今日执行次数" in content:
        print("✅ 执行列表页面渲染正常")
    else:
        print("⚠️ 执行列表页面可能缺少数据")
    
    # 导航到制冷联动配置页面
    print("\n正在导航到制冷联动配置页面...")
    page.goto('http://localhost:3000/#/energy/shift/cooling/config')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    
    # 截图制冷联动配置页面
    page.screenshot(path='test_screenshots/cooling_config.png', full_page=True)
    print("制冷联动配置页面截图已保存: test_screenshots/cooling_config.png")
    
    # 导航到约束管理页面
    print("\n正在导航到约束管理页面...")
    page.goto('http://localhost:3000/#/energy/shift/constraint/config')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    
    # 截图约束管理页面
    page.screenshot(path='test_screenshots/constraint_config.png', full_page=True)
    print("约束管理页面截图已保存: test_screenshots/constraint_config.png")
    
    # 导航到收益报表页面
    print("\n正在导航到收益报表页面...")
    page.goto('http://localhost:3000/#/energy/shift/reports')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    
    # 截图收益报表页面
    page.screenshot(path='test_screenshots/reports.png', full_page=True)
    print("收益报表页面截图已保存: test_screenshots/reports.png")
    
    print("\n所有截图已保存到 test_screenshots/ 目录")
    print("浏览器将保持打开状态，按 Enter 键关闭...")
    input()
    
    browser.close()
