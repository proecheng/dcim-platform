# -*- coding: utf-8 -*-
"""
测试报表分析页面
"""
from playwright.sync_api import sync_playwright
import time

def test_report_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 收集控制台日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        try:
            print("=" * 80)
            print("步骤 1: 登录系统")
            print("=" * 80)
            page.goto('http://localhost:3000', timeout=30000)
            page.wait_for_load_state('networkidle')
            
            # 登录
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
            
            # 清空日志
            console_logs.clear()
            
            # 访问页面
            page.goto('http://localhost:3000/reports', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            
            # 截图
            screenshot_path = "D:\\mytest1\\report_page_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"[OK] 截图已保存: {screenshot_path}")
            
            # 检查页面标题
            try:
                title = page.locator('.page-header, .el-page-header, h1, h2, h3').first.inner_text(timeout=3000)
                print(f"页面标题: {title}")
            except:
                print("[WARNING] 未找到页面标题")
            
            # 检查是否有空状态
            empty_state = page.locator('.el-empty').count()
            if empty_state > 0:
                try:
                    empty_text = page.locator('.el-empty .el-empty__description').inner_text()
                    print(f"[WARNING] 显示空状态: {empty_text}")
                except:
                    print("[WARNING] 显示空状态（无描述）")
            else:
                print("[OK] 未显示空状态")
            
            # 检查卡片
            cards = page.locator('.el-card').count()
            print(f"卡片数量: {cards}")
            
            # 检查表格
            tables = page.locator('.el-table').count()
            print(f"表格数量: {tables}")
            
            if tables > 0:
                table_rows = page.locator('.el-table__body tr').count()
                print(f"表格行数: {table_rows}")
            
            # 检查按钮
            buttons = page.locator('button.el-button').count()
            print(f"按钮数量: {buttons}")
            
            # 检查标签页
            tabs = page.locator('.el-tabs__item').count()
            if tabs > 0:
                print(f"标签页数量: {tabs}")
                tab_labels = page.locator('.el-tabs__item').all()
                print("标签页列表:")
                for i, tab in enumerate(tab_labels[:5]):
                    try:
                        label = tab.inner_text()
                        print(f"  {i+1}. {label}")
                    except:
                        pass
            
            # 检查图表
            charts = page.locator('[id^="chart"], .chart-container, canvas').count()
            print(f"图表元素数量: {charts}")
            
            # 检查控制台错误
            errors = [log for log in console_logs if 'error' in log.lower() and 'websocket' not in log.lower()]
            if errors:
                print(f"\n[ERROR] 发现 {len(errors)} 个控制台错误:")
                for err in errors[:5]:
                    print(f"  {err}")
            else:
                print("\n[OK] 无控制台错误")
            
            print("\n" + "=" * 80)
            print("测试完成")
            print("=" * 80)
            
            # 保持浏览器打开 5 秒
            time.sleep(5)
            
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            
            try:
                page.screenshot(path='D:\\mytest1\\report_error_screenshot.png', full_page=True)
                print("错误截图已保存: report_error_screenshot.png")
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_report_page()
