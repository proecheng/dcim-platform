# -*- coding: utf-8 -*-
"""
测试配电拓扑页面 - 点击节点查看详情
"""
from playwright.sync_api import sync_playwright
import time

def test_power_topology_page():
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
            
            # 测试配电拓扑页面
            print("=" * 80)
            print("步骤 2: 访问配电拓扑页面")
            print("=" * 80)
            
            console_logs.clear()
            
            page.goto('http://localhost:3000/power/topology', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            
            print("[OK] 页面加载完成")
            
            # 截图
            page.screenshot(path='D:\\mytest1\\power_topology_page.png', full_page=True)
            print("[OK] 截图已保存\n")
            
            # 检查树节点
            tree_nodes = page.locator('.el-tree-node').count()
            print(f"树节点数量: {tree_nodes}")
            
            if tree_nodes > 0:
                print("\n步骤 3: 点击第一个树节点")
                
                # 点击第一个节点
                first_node = page.locator('.el-tree-node .tree-node').first
                if first_node:
                    node_text = first_node.inner_text()
                    print(f"节点文本: {node_text}")
                    
                    first_node.click()
                    time.sleep(1)
                    
                    # 检查是否显示属性面板
                    property_panel = page.locator('.property-panel').count()
                    if property_panel > 0:
                        print(f"\n[OK] 显示属性面板: {property_panel} 个")
                        
                        # 截图
                        page.screenshot(path='D:\\mytest1\\power_topology_panel.png', full_page=True)
                        print("[OK] 属性面板截图已保存")
                        
                        # 检查面板标题
                        try:
                            panel_title = page.locator('.property-panel .panel-header span').first.inner_text()
                            print(f"面板标题: {panel_title}")
                        except:
                            print("[WARNING] 无法读取面板标题")
                        
                        # 检查表单项
                        form_items = page.locator('.property-panel .el-form-item').count()
                        print(f"表单项数量: {form_items}")
                    else:
                        print("\n[INFO] 未显示属性面板（可能需要开启编辑模式）")
                        
                        # 尝试开启编辑模式
                        edit_switch = page.locator('.el-switch').first
                        if edit_switch:
                            print("\n步骤 4: 开启编辑模式")
                            edit_switch.click()
                            time.sleep(1)
                            
                            # 再次点击节点
                            first_node.click()
                            time.sleep(1)
                            
                            property_panel = page.locator('.property-panel').count()
                            if property_panel > 0:
                                print(f"[OK] 编辑模式下显示属性面板: {property_panel} 个")
                                page.screenshot(path='D:\\mytest1\\power_topology_edit_panel.png', full_page=True)
                            else:
                                print("[WARNING] 编辑模式下仍未显示属性面板")
            else:
                print("[WARNING] 未找到树节点")
            
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
                page.screenshot(path='D:\\mytest1\\power_topology_error.png', full_page=True)
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_power_topology_page()
