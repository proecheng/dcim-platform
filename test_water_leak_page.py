# -*- coding: utf-8 -*-
"""
测试水浸检测页面数据显示
"""
from playwright.sync_api import sync_playwright
import json
import time

def test_water_leak_page():
    with sync_playwright() as p:
        # 启动浏览器（无头模式）
        browser = p.chromium.launch(headless=False)  # 使用有头模式便于观察
        context = browser.new_context()
        page = context.new_page()
        
        # 收集控制台日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        # 收集网络请求
        api_requests = []
        page.on("response", lambda response: api_requests.append({
            "url": response.url,
            "status": response.status,
            "method": response.request.method
        }) if "/api/" in response.url else None)
        
        try:
            print("=" * 80)
            print("步骤 1: 访问登录页面")
            print("=" * 80)
            page.goto('http://localhost:3000', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(1)
            
            print("\n步骤 2: 执行登录")
            # 查找用户名和密码输入框
            username_input = page.locator('input[type="text"]').first
            password_input = page.locator('input[type="password"]').first
            
            username_input.fill('admin')
            password_input.fill('admin123')
            
            # 点击登录按钮
            login_button = page.locator('button:has-text("登录")').first
            # 点击登录按钮 - 尝试多种选择器
            try:
                login_button = page.locator('button[type="submit"]').first
                login_button.click(timeout=5000)
            except:
                try:
                    login_button = page.locator('button.el-button--primary').first
                    login_button.click(timeout=5000)
                except:
                    # 最后尝试按回车键
                    password_input.press('Enter')
            
            # 等待登录完成
            print("[OK] 登录成功")
            
            print("\n" + "=" * 80)
            print("步骤 3: 导航到水浸检测页面")
            print("=" * 80)
            page.goto('http://localhost:3000/environment/water-leak', timeout=30000)
            page.wait_for_load_state('networkidle')
            time.sleep(3)  # 等待数据加载
            
            print("[OK] 页面加载完成")
            
            # 截图
            screenshot_path = 'D:\\mytest1\\water_leak_page_screenshot.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n[OK] 截图已保存: {screenshot_path}")
            
            print("\n" + "=" * 80)
            print("步骤 4: 检查页面数据")
            print("=" * 80)
            
            # 检查统计卡片
            print("\n【统计卡片数据】")
            stat_cards = page.locator('.stat-card').all()
            print(f"找到 {len(stat_cards)} 个统计卡片")
            
            for i, card in enumerate(stat_cards):
                try:
                    label = card.locator('.stat-label').inner_text()
                    value = card.locator('.stat-value').inner_text()
                    print(f"  卡片 {i+1}: {label} = {value}")
                except:
                    print(f"  卡片 {i+1}: 无法读取")
            
            # 检查区域分组卡片
            print("\n【区域分组卡片】")
            zone_cards = page.locator('.zone-card').all()
            print(f"找到 {len(zone_cards)} 个区域卡片")
            
            for i, card in enumerate(zone_cards[:5]):  # 只显示前5个
                try:
                    zone_name = card.locator('.zone-name').inner_text()
                    sensor_count = card.locator('.zone-metric .metric-value').first.inner_text()
                    print(f"  区域 {i+1}: {zone_name} - {sensor_count} 个传感器")
                except:
                    print(f"  区域 {i+1}: 无法读取")
            
            # 检查表格数据
            print("\n【底部表格数据】")
            
            # 检查是否有空状态提示
            empty_state = page.locator('.el-empty').count()
            if empty_state > 0:
                empty_text = page.locator('.el-empty .el-empty__description').inner_text()
                print(f"[WARNING] 显示空状态: {empty_text}")
            else:
                print("[OK] 未显示空状态提示")
            
            # 检查表格行数
            table_rows = page.locator('.el-table__body tr').all()
            print(f"表格行数: {len(table_rows)}")
            
            if len(table_rows) > 0:
                print("\n前 5 行数据:")
                for i, row in enumerate(table_rows[:5]):
                    try:
                        cells = row.locator('td').all()
                        if len(cells) >= 3:
                            name = cells[0].inner_text().strip()
                            area = cells[1].inner_text().strip()
                            status = cells[2].inner_text().strip()
                            print(f"  行 {i+1}: {name} | {area} | {status}")
                    except:
                        print(f"  行 {i+1}: 无法读取")
            else:
                print("[WARNING] 表格无数据")
            
            # 检查 API 请求
            print("\n" + "=" * 80)
            print("步骤 5: 检查 API 请求")
            print("=" * 80)
            
            water_leak_apis = [req for req in api_requests if 'realtime' in req['url'] or 'alarm' in req['url']]
            print(f"\n找到 {len(water_leak_apis)} 个相关 API 请求:")
            for req in water_leak_apis[:10]:
                print(f"  {req['method']} {req['url']} - Status: {req['status']}")
            
            # 检查控制台错误
            print("\n" + "=" * 80)
            print("步骤 6: 检查控制台日志")
            print("=" * 80)
            
            errors = [log for log in console_logs if 'error' in log.lower()]
            warnings = [log for log in console_logs if 'warning' in log.lower() or 'warn' in log.lower()]
            
            if errors:
                print(f"\n[WARNING] 发现 {len(errors)} 个错误:")
                for err in errors[:5]:
                    print(f"  {err}")
            else:
                print("\n[OK] 无控制台错误")
            
            if warnings:
                print(f"\n[WARNING] 发现 {len(warnings)} 个警告:")
                for warn in warnings[:5]:
                    print(f"  {warn}")
            
            # 获取实时数据 API 的响应
            print("\n" + "=" * 80)
            print("步骤 7: 检查实时数据 API 响应")
            print("=" * 80)
            
            # 手动调用 API 检查返回数据
            response = page.request.get('http://localhost:8080/api/v1/realtime/all')
            if response.ok:
                data = response.json()
                print(f"\n[OK] API 返回成功，状态码: {response.status}")
                print(f"返回数据数量: {len(data) if isinstance(data, list) else 'N/A'}")
                
                # 筛选 WATER 类型的数据
                if isinstance(data, list):
                    water_sensors = [d for d in data if d.get('device_type') == 'WATER']
                    print(f"WATER 类型传感器数量: {len(water_sensors)}")
                    
                    if water_sensors:
                        print("\n前 3 个 WATER 传感器数据:")
                        for i, sensor in enumerate(water_sensors[:3]):
                            print(f"  {i+1}. {sensor.get('point_name')} - {sensor.get('device_type')} - {sensor.get('status')}")
                    else:
                        print("\n[WARNING] API 返回的数据中没有 device_type='WATER' 的传感器")
                        
                        # 检查是否有其他类型
                        device_types = set(d.get('device_type') for d in data if d.get('device_type'))
                        print(f"\n实际存在的设备类型: {sorted(device_types)}")
            else:
                print(f"\n[ERROR] API 请求失败，状态码: {response.status}")
            
            print("\n" + "=" * 80)
            print("测试完成")
            print("=" * 80)
            
            # 保持浏览器打开 5 秒便于观察
            time.sleep(5)
            
        except Exception as e:
            print("ERROR: " + str(e))
            import traceback
            traceback.print_exc()
            
            # 出错时也截图
            try:
                page.screenshot(path='D:\\mytest1\\water_leak_error_screenshot.png', full_page=True)
                print("错误截图已保存: water_leak_error_screenshot.png")
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    test_water_leak_page()
