"""
测试配电配置-转移配置页面的"请求失败"错误
复现步骤：采集配置 → 配电配置 → 转移配置 → 点击 F1 精密空调-2
"""
from playwright.sync_api import sync_playwright
import time
import json

def test_power_config_drawer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 使用有头模式便于观察
        context = browser.new_context()
        
        # 捕获所有网络请求
        failed_requests = []
        all_requests = []
        
        def handle_response(response):
            request_info = {
                'url': response.url,
                'status': response.status,
                'method': response.request.method,
                'timestamp': time.time()
            }
            all_requests.append(request_info)
            
            # 记录失败的请求
            if response.status >= 400:
                try:
                    body = response.text()
                except:
                    body = '<无法读取响应体>'
                
                failed_requests.append({
                    **request_info,
                    'response_body': body
                })
                print(f"❌ 请求失败: {response.request.method} {response.url} - Status: {response.status}")
                print(f"   响应: {body[:200]}")
        
        page = context.new_page()
        page.on('response', handle_response)
        
        # 捕获控制台日志
        console_logs = []
        def handle_console(msg):
            log_entry = f"[{msg.type}] {msg.text}"
            console_logs.append(log_entry)
            print(f"Console: {log_entry}")
        
        page.on('console', handle_console)
        
        try:
            print("1. 访问登录页面...")
            page.goto('http://localhost:3000', wait_until='networkidle')
            page.screenshot(path='screenshot_1_login.png')
            
            print("2. 登录...")
            page.fill('input[placeholder="请输入用户名"]', 'admin')
            page.fill('input[placeholder="请输入密码"]', 'admin123')
            page.click('button:has-text("登录")')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path='screenshot_2_after_login.png')
            
            print("3. 导航到采集配置...")
            # 点击采集配置菜单
            page.click('text=采集配置')
            time.sleep(1)
            page.screenshot(path='screenshot_3_collection_menu.png')
            
            print("4. 点击配电配置...")
            page.click('text=配电配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path='screenshot_4_power_config.png')
            
            print("5. 切换到转移配置标签...")
            # 查找并点击"转移配置"标签
            page.click('text=转移配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path='screenshot_5_shift_config.png')
            
            print("6. 点击 F1 精密空调-2...")
            # 清空之前的失败请求记录
            failed_requests.clear()
            
            # 点击设备名称
            page.click('text=F1 精密空调-2')
            
            # 等待抽屉框出现
            time.sleep(3)
            page.screenshot(path='screenshot_6_drawer_opened.png')
            
            # 检查是否有错误提示
            error_messages = page.locator('.el-message--error').all()
            if error_messages:
                print(f"\n⚠️ 发现 {len(error_messages)} 个错误提示")
                for i, msg in enumerate(error_messages):
                    print(f"   错误 {i+1}: {msg.text_content()}")
            
            # 等待一段时间观察
            time.sleep(5)
            page.screenshot(path='screenshot_7_final.png')
            
            print("\n" + "="*80)
            print("失败的请求汇总:")
            print("="*80)
            for req in failed_requests:
                print(f"\n{req['method']} {req['url']}")
                print(f"Status: {req['status']}")
                print(f"响应: {req['response_body'][:500]}")
            
            print("\n" + "="*80)
            print(f"总请求数: {len(all_requests)}")
            print(f"失败请求数: {len(failed_requests)}")
            print("="*80)
            
            # 保存详细日志
            with open('network_log.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'all_requests': all_requests,
                    'failed_requests': failed_requests,
                    'console_logs': console_logs
                }, f, indent=2, ensure_ascii=False)
            
            print("\n详细日志已保存到 network_log.json")
            
        except Exception as e:
            print(f"\n❌ 测试过程中出错: {e}")
            page.screenshot(path='screenshot_error.png')
            raise
        finally:
            input("\n按 Enter 键关闭浏览器...")
            browser.close()

if __name__ == '__main__':
    test_power_config_drawer()
