# -*- coding: utf-8 -*-
"""
详细检查报表分析页面的网络请求和控制台日志
"""
from playwright.sync_api import sync_playwright
import time
import json

def test_report_page_detailed():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 收集所有日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "location": f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}"
        }))
        
        # 收集网络请求
        api_requests = []
        page.on("response", lambda response: api_requests.append({
            "url": response.url,
            "status": response.status,
            "method": response.request.method,
            "content_type": response.headers.get("content-type", "")
        }) if "/api/" in response.url else None)
        
        try:
            print("=" * 80)
            print("步骤 1: 登录系统")
            print("=" * 80)
            page.goto('http://localhost:3000', timeout=30000)
            page.wait_for_load_state('networkidle')
            
            username_input = page.locator('input[type="text"]').first
            password_input = page.locator('input[type="password"]').first
            username_input.fill('admin')
            password_input.fill('admin123')
            
            try:
                login_button = page.locator('button[type="submit"]').first
                login_button.click(timeout=5000)
            except:
                password_input.press('Enter')
            
            time.sleep(2)
            print("[OK] 登录成功\n")
            
            print("=" * 80)
            print("步骤 2: 访问报表分析页面")
            print("=" * 80)
            
            # 清空日志和请求
            console_logs.clear()
            api_requests.clear()
            
            page.goto('http://localhost:3000/reports', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            
            print("[OK] 页面加载完成\n")
            
            print("=" * 80)
            print("步骤 3: 分析网络请求")
            print("=" * 80)
            
            report_apis = [req for req in api_requests if 'report' in req['url'].lower()]
            print(f"\n找到 {len(report_apis)} 个报表相关 API 请求:")
            for req in report_apis:
                print(f"\n  URL: {req['url']}")
                print(f"  Method: {req['method']}")
                print(f"  Status: {req['status']}")
                print(f"  Content-Type: {req['content_type']}")
            
            if not report_apis:
                print("\n[WARNING] 没有发现任何报表 API 请求！")
                print("可能原因：")
                print("  1. 页面加载时没有自动请求数据")
                print("  2. 请求被条件阻止（如日期选择器未初始化）")
                print("  3. 请求失败但被静默处理")
            
            print("\n" + "=" * 80)
            print("步骤 4: 分析控制台日志")
            print("=" * 80)
            
            # 分类日志
            errors = [log for log in console_logs if log['type'] == 'error']
            warnings = [log for log in console_logs if log['type'] == 'warning']
            logs = [log for log in console_logs if log['type'] == 'log']
            
            if errors:
                print(f"\n[ERROR] 发现 {len(errors)} 个错误:")
                for err in errors[:5]:
                    print(f"  {err['text']}")
                    print(f"    位置: {err['location']}")
            else:
                print("\n[OK] 无错误日志")
            
            if warnings:
                print(f"\n[WARNING] 发现 {len(warnings)} 个警告:")
                for warn in warnings[:5]:
                    print(f"  {warn['text']}")
            else:
                print("\n[OK] 无警告日志")
            
            if logs:
                print(f"\n[INFO] 发现 {len(logs)} 个普通日志:")
                for log in logs[:10]:
                    if '加载' in log['text'] or '失败' in log['text'] or 'report' in log['text'].lower():
                        print(f"  {log['text']}")
            
            print("\n" + "=" * 80)
            print("步骤 5: 检查页面状态")
            print("=" * 80)
            
            # 检查日期选择器的值
            try:
                date_picker = page.locator('.el-date-editor input').first
                date_value = date_picker.input_value()
                print(f"\n日期选择器值: {date_value}")
            except:
                print("\n[WARNING] 无法读取日期选择器值")
            
            # 检查表格数据
            table_rows = page.locator('.el-table__body tr').count()
            print(f"表格行数: {table_rows}")
            
            # 检查统计卡片的值
            stat_values = page.locator('.stat-value').all()
            if stat_values:
                print(f"\n统计卡片值:")
                for i, stat in enumerate(stat_values[:4]):
                    try:
                        value = stat.inner_text()
                        print(f"  卡片 {i+1}: {value}")
                    except:
                        pass
            
            print("\n" + "=" * 80)
            print("测试完成")
            print("=" * 80)
            
            # 保存详细日志
            with open('D:\\mytest1\\report_analysis.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'api_requests': api_requests,
                    'console_logs': console_logs
                }, f, ensure_ascii=False, indent=2)
            print("\n详细日志已保存到: report_analysis.json")
            
            time.sleep(5)
            
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            
            try:
                page.screenshot(path='D:\\mytest1\\report_error_detailed.png', full_page=True)
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_report_page_detailed()
