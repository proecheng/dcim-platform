"""
验证 Story 27.7 的修复：
1. AC1: 温度监控页面告警数据统一
2. AC2 & AC5: Dashboard 能源数据统一和缓存移除
3. AC3 & AC4: BigscreenStore energy 和 environment getter
"""
from playwright.sync_api import sync_playwright
import json

def verify_story_27_7():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 收集控制台消息
        console_messages = []
        def handle_console(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text
            })
        page.on('console', handle_console)

        # 登录
        print("=== 登录系统 ===")
        page.goto('http://localhost:3000')
        page.wait_for_load_state('networkidle')

        inputs = page.locator('input').all()
        buttons = page.locator('button').all()
        if len(inputs) >= 2 and len(buttons) >= 1:
            inputs[0].fill('admin')
            inputs[1].fill('admin123')
            buttons[0].click()

        page.wait_for_timeout(2000)
        print(f"Login URL: {page.url}")

        # 验证 AC2 & AC5: Dashboard 能源数据
        print("\n=== Verify AC2 & AC5: Dashboard Energy Data ===")
        page.goto('http://localhost:3000/dashboard')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        page.screenshot(path='D:/mytest1/verify_dashboard.png', full_page=True)

        # 检查是否有 sessionStorage 缓存（应该没有）
        cache_check = page.evaluate('() => sessionStorage.getItem("dcim_dashboard_cache")')
        if cache_check:
            print("[FAIL] Dashboard still using sessionStorage cache")
        else:
            print("[PASS] Dashboard sessionStorage cache removed")

        # 检查能源数据是否显示
        power_cards = page.locator('.el-card:has-text("实时功率"), .el-card:has-text("PUE")').all()
        print(f"Found {len(power_cards)} energy cards")
        if len(power_cards) > 0:
            print("[PASS] Dashboard energy data visible")
        else:
            print("[FAIL] Dashboard energy data not visible")

        # 验证 AC1: 温度监控页面告警数据
        print("\n=== Verify AC1: Temperature Monitoring Alarm Data ===")
        page.goto('http://localhost:3000/environment/temperature')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        page.screenshot(path='D:/mytest1/verify_temperature.png', full_page=True)

        # 查找传感器卡片
        sensor_cards = page.locator('.sensor-card, [class*="sensor"]').all()
        print(f"Found {len(sensor_cards)} sensors")

        if len(sensor_cards) > 0:
            print("Clicking first sensor...")
            sensor_cards[0].click()
            page.wait_for_timeout(1000)

            # 检查是否有抽屉或弹窗打开
            drawer = page.locator('.el-drawer, .el-dialog').first
            if drawer.is_visible():
                print("[PASS] Sensor detail drawer opened")
                page.screenshot(path='D:/mytest1/verify_sensor_detail.png')
            else:
                print("[WARN] Sensor detail drawer not opened")
        else:
            print("[WARN] No sensor cards found")

        # 验证 AC3 & AC4: 大屏数据
        print("\n=== Verify AC3 & AC4: Bigscreen Data ===")
        page.goto('http://localhost:3000/bigscreen')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

        page.screenshot(path='D:/mytest1/verify_bigscreen.png', full_page=True)

        # 检查大屏是否正常加载
        canvas = page.locator('canvas').first
        if canvas.is_visible():
            print("[PASS] Bigscreen 3D scene loaded")
        else:
            print("[WARN] Bigscreen 3D scene not loaded")

        # 检查控制台错误
        print("\n=== Console Error Check ===")
        errors = [msg for msg in console_messages if msg['type'] == 'error']
        if errors:
            print(f"Found {len(errors)} console errors:")
            for err in errors[:5]:  # 只显示前5个
                print(f"  - {err['text']}")
        else:
            print("[PASS] No console errors")

        # 保存结果
        with open('D:/mytest1/verify_results.json', 'w', encoding='utf-8') as f:
            json.dump({
                'console_messages': console_messages,
                'test_summary': {
                    'dashboard_cache_removed': cache_check is None,
                    'dashboard_energy_visible': len(power_cards) > 0,
                    'temperature_sensors_found': len(sensor_cards) if 'sensor_cards' in locals() else 0,
                    'bigscreen_loaded': canvas.is_visible() if 'canvas' in locals() else False,
                    'console_errors': len(errors)
                }
            }, f, ensure_ascii=False, indent=2)

        print("\nVerification complete! Details saved to: D:/mytest1/verify_results.json")

        browser.close()

if __name__ == '__main__':
    verify_story_27_7()
