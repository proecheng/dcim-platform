# -*- coding: utf-8 -*-
"""
测试配电配置页面 - 点击设备名称弹出详情
"""
from playwright.sync_api import sync_playwright
import time
import json

def test_power_config_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 收集日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text
        }))
        
        # 收集网络请求
        api_requests = []
        page.on("response", lambda response: api_requests.append({
            "url": response.url,
            "status": response.status,
            "method": response.request.method
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
            
            # 测试配电配置页面
            print("=" * 80)
            print("步骤 2: 访问配电配置页面")
            print("=" * 80)
            
            console_logs.clear()
            api_requests.clear()
            
            page.goto('http://localhost:3000/energy/config', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            print("[OK] 页面加载完成")
            
            # 截图
            page.screenshot(path='D:\\mytest1\\power_config_page.png', full_page=True)
            print("[OK] 截图已保存\n")
            
            # 检查标签页
            tabs = page.locator('.el-tabs__item').all()
            print(f"标签页数量: {len(tabs)}")
            if tabs:
                print("标签页列表:")
                for i, tab in enumerate(tabs):
                    try:
                        label = tab.inner_text()
                        print(f"  {i+1}. {label}")
                    except:
                        pass
            
            # 检查表格
            tables = page.locator('.el-table').count()
            print(f"\n表格数量: {tables}")
            
            if tables > 0:
                # 获取第一个表格的行数
                rows = page.locator('.el-table__body tr').count()
                print(f"第一个表格行数: {rows}")
                
                if rows > 0:
                    print("\n步骤 3: 点击第一行的编辑按钮")
                    
                    # 查找编辑按钮
                    edit_buttons = page.locator('.el-table__body tr .el-button--primary').all()
                    if edit_buttons:
                        print(f"找到 {len(edit_buttons)} 个编辑按钮")
                        
                        # 点击第一个编辑按钮
                        edit_buttons[0].click()
                        time.sleep(1)
                        
                        # 检查是否弹出对话框或抽屉
                        dialog = page.locator('.el-dialog').count()
                        drawer = page.locator('.el-drawer').count()
                        
                        if dialog > 0:
                            print(f"\n[OK] 弹出对话框: {dialog} 个")
                            
                            # 截图
                            page.screenshot(path='D:\\mytest1\\power_config_dialog.png', full_page=True)
                            print("[OK] 对话框截图已保存")
                            
                            # 检查对话框标题
                            try:
                                dialog_title = page.locator('.el-dialog__title').first.inner_text()
                                print(f"对话框标题: {dialog_title}")
                            except:
                                print("[WARNING] 无法读取对话框标题")
                            
                            # 检查对话框内容
                            form_items = page.locator('.el-dialog .el-form-item').count()
                            print(f"表单项数量: {form_items}")
                            
                        elif drawer > 0:
                            print(f"\n[OK] 弹出抽屉: {drawer} 个")
                            
                            # 截图
                            page.screenshot(path='D:\\mytest1\\power_config_drawer.png', full_page=True)
                            print("[OK] 抽屉截图已保存")
                            
                            # 检查抽屉标题
                            try:
                                drawer_title = page.locator('.el-drawer__title').first.inner_text()
                                print(f"抽屉标题: {drawer_title}")
                            except:
                                print("[WARNING] 无法读取抽屉标题")
                        else:
                            print("\n[WARNING] 点击后没有弹出对话框或抽屉")
                    else:
                        print("[WARNING] 未找到编辑按钮")
                else:
                    print("\n[INFO] 表格无数据，无法测试点击")
            
            # 检查控制台错误
            errors = [log for log in console_logs if log['type'] == 'error' and 'websocket' not in log['text'].lower()]
            if errors:
                print(f"\n[ERROR] 发现 {len(errors)} 个控制台错误:")
                for err in errors[:5]:
                    print(f"  {err['text']}")
            else:
                print("\n[OK] 无控制台错误")
            
            # 检查 API 请求
            config_apis = [req for req in api_requests if 'energy' in req['url'].lower() or 'power' in req['url'].lower() or 'topology' in req['url'].lower()]
            if config_apis:
                print(f"\n相关 API 请求 ({len(config_apis)} 个):")
                for req in config_apis[:10]:
                    print(f"  {req['method']} {req['url']} - Status: {req['status']}")
            
            print("\n" + "=" * 80)
            print("测试完成")
            print("=" * 80)
            
            # 保持浏览器打开
            time.sleep(5)
            
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            
            try:
                page.screenshot(path='D:\\mytest1\\power_config_error.png', full_page=True)
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_power_config_page()
