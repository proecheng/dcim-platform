"""
测试 Dashboard 页面，捕获控制台错误和网络请求失败
"""
from playwright.sync_api import sync_playwright
import json

def test_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 收集控制台消息
        console_messages = []
        def handle_console(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text,
                'location': msg.location
            })
        page.on('console', handle_console)

        # 收集网络请求失败
        failed_requests = []
        def handle_response(response):
            if response.status >= 400:
                failed_requests.append({
                    'url': response.url,
                    'status': response.status,
                    'method': response.request.method
                })
        page.on('response', handle_response)

        # 访问登录页面
        print("正在访问登录页面...")
        page.goto('http://localhost:3000')
        page.wait_for_load_state('networkidle')

        # 保存登录页面HTML用于调试
        with open('D:/mytest1/login_page.html', 'w', encoding='utf-8') as f:
            f.write(page.content())
        print("登录页面HTML已保存到: D:/mytest1/login_page.html")

        page.screenshot(path='D:/mytest1/screenshot_login.png')

        # 查找所有输入框和按钮
        inputs = page.locator('input').all()
        buttons = page.locator('button').all()
        print(f"找到 {len(inputs)} 个输入框, {len(buttons)} 个按钮")

        # 登录
        print("正在登录...")
        # 使用索引定位
        if len(inputs) >= 2:
            inputs[0].fill('admin')
            inputs[1].fill('admin123')
        if len(buttons) >= 1:
            buttons[0].click()

        # 等待一段时间观察登录结果
        page.wait_for_timeout(3000)

        # 检查当前URL
        current_url = page.url
        print(f"登录后URL: {current_url}")

        # 截图登录后状态
        page.screenshot(path='D:/mytest1/screenshot_after_login.png')

        # 如果还在登录页面，说明登录失败
        if '/login' in current_url or current_url == 'http://localhost:3000/':
            print("登录可能失败，检查页面上的错误提示...")
            # 查找错误提示
            error_elements = page.locator('.el-message, .el-notification, [class*="error"]').all()
            for elem in error_elements:
                if elem.is_visible():
                    print(f"错误提示: {elem.text_content()}")

        # 尝试导航到 dashboard（无论登录是否成功）
        if '/dashboard' not in current_url:
            print("手动导航到 dashboard...")
            page.goto('http://localhost:3000/dashboard')
            page.wait_for_load_state('networkidle')

        # 等待一段时间让所有请求完成
        page.wait_for_timeout(3000)

        # 截图
        page.screenshot(path='D:/mytest1/screenshot_dashboard.png', full_page=True)

        # 输出结果
        print("\n=== 控制台错误 ===")
        errors = [msg for msg in console_messages if msg['type'] == 'error']
        if errors:
            for err in errors:
                print(f"[ERROR] {err['text']}")
                if err['location']:
                    print(f"  位置: {err['location']}")
        else:
            print("无控制台错误")

        print("\n=== 失败的网络请求 ===")
        if failed_requests:
            for req in failed_requests:
                print(f"[{req['status']}] {req['method']} {req['url']}")
        else:
            print("无失败的网络请求")

        print("\n=== 所有控制台消息 ===")
        for msg in console_messages[-20:]:  # 最后20条
            print(f"[{msg['type']}] {msg['text']}")

        # 保存详细日志
        with open('D:/mytest1/test_results.json', 'w', encoding='utf-8') as f:
            json.dump({
                'console_messages': console_messages,
                'failed_requests': failed_requests
            }, f, ensure_ascii=False, indent=2)

        print("\n详细日志已保存到: D:/mytest1/test_results.json")
        print("截图已保存到: D:/mytest1/screenshot_login.png 和 screenshot_dashboard.png")

        browser.close()

if __name__ == '__main__':
    test_dashboard()
