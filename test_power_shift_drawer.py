"""
测试功率配置页面的设备转移详情抽屉功能
"""
from playwright.sync_api import sync_playwright
import time

def test_power_shift_drawer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 使用有头模式便于观察
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 1. 访问登录页面
            print("访问登录页面...")
            page.goto('http://localhost:3000')
            page.wait_for_load_state('networkidle')
            
            # 2. 登录
            print("执行登录...")
            page.wait_for_selector('.login-form', timeout=10000)
            page.fill('input[placeholder="用户名"]', 'admin')
            page.fill('input[placeholder="密码"]', 'admin123')
            page.click('.login-btn')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            # 3. 导航到功率配置页面
            print("导航到功率配置页面...")
            page.goto('http://localhost:3000/collection/power-config')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            # 4. 点击"转移配置"标签页
            print("点击转移配置标签页...")
            page.click('text=转移配置')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            # 5. 截图查看当前状态
            print("截图查看转移配置页面...")
            page.screenshot(path='D:\\mytest1\\screenshot_shift_config.png', full_page=True)
            
            # 6. 查找并点击第一个设备名称链接
            print("查找设备名称链接...")
            device_links = page.locator('a.device-name-link, .el-link').all()
            print(f"找到 {len(device_links)} 个设备链接")
            
            if len(device_links) > 0:
                print("点击第一个设备链接...")
                device_links[0].click()
                time.sleep(3)  # 等待抽屉打开
                
                # 7. 截图查看抽屉内容
                print("截图查看抽屉内容...")
                page.screenshot(path='D:\\mytest1\\screenshot_drawer_opened.png', full_page=True)
                
                # 8. 检查抽屉中的关键元素
                print("\n检查抽屉内容:")
                
                # 检查是否有"暂无历史数据"或"模拟数据"标签
                no_data_label = page.locator('text=暂无历史数据').count()
                sim_data_label = page.locator('text=模拟数据').count()
                print(f"  - '暂无历史数据' 标签数量: {no_data_label}")
                print(f"  - '模拟数据' 标签数量: {sim_data_label}")
                
                # 检查是否有图表
                chart_elements = page.locator('.echarts, [id*="chart"]').count()
                print(f"  - 图表元素数量: {chart_elements}")
                
                # 检查是否有约束条件信息
                constraint_text = page.locator('text=/温度|冗余|PUE|约束/').count()
                print(f"  - 约束条件相关文本数量: {constraint_text}")
                
                # 获取抽屉的完整 HTML 内容（用于调试）
                drawer_html = page.locator('.el-drawer__body').inner_html()
                with open('D:\\mytest1\\drawer_content.html', 'w', encoding='utf-8') as f:
                    f.write(drawer_html)
                print("  - 抽屉 HTML 内容已保存到 drawer_content.html")
                
                # 等待一段时间便于观察
                time.sleep(5)
                
                print("\n✅ 测试完成！请查看截图文件:")
                print("  - screenshot_shift_config.png (转移配置页面)")
                print("  - screenshot_drawer_opened.png (抽屉打开后)")
                print("  - drawer_content.html (抽屉 HTML 内容)")
            else:
                print("❌ 未找到设备链接")
                
        except Exception as e:
            print("\u6d4b\u8bd5\u5931\u8d25:", str(e))
            page.screenshot(path='D:\\mytest1\\screenshot_error.png', full_page=True)
            raise
        finally:
            browser.close()

if __name__ == '__main__':
    test_power_shift_drawer()
