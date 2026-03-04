"""
测试制冷总览页面
"""
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # 收集控制台日志和错误
    console_logs = []
    errors = []
    
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: errors.append(str(err)))
    
    # 监听网络请求
    failed_requests = []
    def handle_response(response):
        if response.status >= 400:
            failed_requests.append({
                "url": response.url,
                "status": response.status,
                "method": response.request.method
            })
    
    page.on("response", handle_response)
    
    try:
        # 访问登录页
        print("正在访问登录页...")
        page.goto('http://localhost:3000', wait_until='networkidle')
        page.wait_for_timeout(1000)
        
        # 登录
        print("正在登录...")
        page.fill('input[placeholder="请输入用户名"]', 'admin')
        page.fill('input[placeholder="请输入密码"]', 'admin123')
        page.click('button:has-text("登录")')
        page.wait_for_timeout(2000)
        
        # 导航到制冷总览
        print("正在导航到制冷总览...")
        page.goto('http://localhost:3000/cooling/overview', wait_until='networkidle')
        page.wait_for_timeout(3000)
        
        # 截图
        page.screenshot(path='D:\\mytest1\\cooling_overview.png', full_page=True)
        print("截图已保存: cooling_overview.png")
        
        # 检查页面内容
        title = page.title()
        print(f"\n页面标题: {title}")
        
        # 检查统计卡片
        stat_cards = page.locator('.stat-card').all()
        print(f"\n统计卡片数量: {len(stat_cards)}")
        
        # 检查是否有错误提示
        error_messages = page.locator('.el-message--error').all()
        if error_messages:
            print(f"\n发现错误提示: {len(error_messages)} 个")
            for msg in error_messages:
                print(f"  - {msg.text_content()}")
        
        # 输出失败的请求
        if failed_requests:
            print(f"\n失败的请求 ({len(failed_requests)} 个):")
            for req in failed_requests:
                print(f"  - {req['method']} {req['url']} -> {req['status']}")
        
        # 输出控制台错误
        console_errors = [log for log in console_logs if 'error' in log.lower()]
        if console_errors:
            print(f"\n控制台错误 ({len(console_errors)} 个):")
            for err in console_errors[:10]:  # 只显示前10个
                print(f"  - {err}")
        
        # 输出页面错误
        if errors:
            print(f"\n页面错误 ({len(errors)} 个):")
            for err in errors[:5]:
                print(f"  - {err}")
        
        print("\n测试完成！")
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        page.screenshot(path='D:\\mytest1\\cooling_overview_error.png', full_page=True)
    finally:
        browser.close()
