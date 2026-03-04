# -*- coding: utf-8 -*-
"""
测试配电配置 - 转移配置页面 - 点击设备名称弹出抽屉
"""
from playwright.sync_api import sync_playwright
import time

def test_shift_config_drawer():
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
            print("步骤 2: 访问配电配置页面")
            print("=" * 80)
            
            console_logs.clear()
            
            page.goto('http://localhost:3000/collection/power-config', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            print("[OK] 页面加载完成")
            
            # 截图
            page.screenshot(path='D:\\mytest1\\shift_config_page.png', full_page=True)
            print("[OK] 截图已保存\n")
            
            print("=" * 80)
            print("步骤 3: 切换到转移配置标签页")
            print("=" * 80)
            
            # 查找转移配置标签
            tabs = page.locator('.el-tabs__item').all()
            shift_tab = None
            for tab in tabs:
                try:
                    if '转移配置' in tab.inner_text():
                        shift_tab = tab
                        break
                except:
                    pass
            
            if shift_tab:
                print("[OK] 找到转移配置标签页")
                shift_tab.click()
                time.sleep(2)
                
                # 截图
                page.screenshot(path='D:\\mytest1\\shift_config_tab.png', full_page=True)
                print("[OK] 切换成功，截图已保存\n")
                
                # 检查表格
                table_rows = page.locator('.el-table__body tr').count()
                print(f"表格行数: {table_rows}")
                
                if table_rows > 0:
                    print("\n步骤 4: 点击第一个设备名称")
                    
                    # 查找设备名称链接
                    device_links = page.locator('.el-table__body .el-link').all()
                    if device_links:
                        print(f"找到 {len(device_links)} 个设备链接")
                        
                        # 获取第一个设备名称
                        first_device_name = device_links[0].inner_text()
                        print(f"设备名称: {first_device_name}")
                        
                        # 点击设备名称
                        device_links[0].click()
                        time.sleep(2)
                        
                        # 检查是否弹出抽屉
                        drawer = page.locator('.el-drawer').count()
                        if drawer > 0:
                            print(f"\n[OK] 成功弹出抽屉: {drawer} 个")
                            
                            # 截图
                            page.screenshot(path='D:\\mytest1\\shift_config_drawer.png', full_page=True)
                            print("[OK] 抽屉截图已保存")
                            
                            # 检查抽屉标题
                            try:
                                drawer_title = page.locator('.el-drawer__header .device-name').first.inner_text()
                                print(f"抽屉标题: {drawer_title}")
                            except:
                                try:
                                    drawer_title = page.locator('.el-drawer__header').first.inner_text()
                                    print(f"抽屉标题: {drawer_title}")
                                except:
                                    print("[WARNING] 无法读取抽屉标题")
                            
                            # 检查抽屉内容
                            metric_cards = page.locator('.el-drawer .metric-card').count()
                            print(f"指标卡片数量: {metric_cards}")
                            
                            # 检查图表
                            charts = page.locator('.el-drawer .power-chart').count()
                            print(f"图表数量: {charts}")
                            
                            # 检查约束条件
                            constraints = page.locator('.el-drawer .constraint-item').count()
                            print(f"约束条件数量: {constraints}")
                            
                            # 检查底部按钮
                            footer_buttons = page.locator('.el-drawer__footer .el-button').count()
                            print(f"底部按钮数量: {footer_buttons}")
                            
                        else:
                            print("\n[ERROR] 点击后没有弹出抽屉")
                    else:
                        print("[WARNING] 未找到设备链接")
                else:
                    print("\n[INFO] 表格无数据，无法测试点击")
            else:
                print("[ERROR] 未找到转移配置标签页")
            
            # 检查控制台错误
            errors = [log for log in console_logs if log['type'] == 'error' and 'websocket' not in log['text'].lower()]
            if errors:
                print(f"\n[ERROR] 发现 {len(errors)} 个控制台错误:")
                for err in errors[:5]:
                    print(f"  {err['text']}")
            else:
                print("\n[OK] 无控制台错误")
            
            print("\n" + "=" * 80)
            print("测试完成")
            print("=" * 80)
            
            time.sleep(5)
            
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            
            try:
                page.screenshot(path='D:\\mytest1\\shift_config_error.png', full_page=True)
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_shift_config_drawer()
