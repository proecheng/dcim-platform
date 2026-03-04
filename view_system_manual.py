"""
简化版浏览器查看脚本 - 手动登录后查看页面
"""
from playwright.sync_api import sync_playwright
import time

print("=" * 80)
print("Phase 2 负荷转移系统 - 浏览器查看工具")
print("=" * 80)
print("\n说明:")
print("1. 浏览器将自动打开 http://localhost:3000")
print("2. 请手动登录（用户名: admin, 密码: admin123）")
print("3. 登录后，脚本将自动导航到 Phase 2 页面并截图")
print("\n按 Enter 键开始...")
input()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    print("\n正在打开系统...")
    page.goto('http://localhost:3000')
    
    print("\n请在浏览器中手动登录...")
    print("登录后，按 Enter 键继续...")
    input()
    
    print("\n正在导航到执行监控列表页面...")
    page.goto('http://localhost:3000/#/energy/shift/execution/list')
    time.sleep(3)
    page.screenshot(path='test_screenshots/shift_execution_list_manual.png', full_page=True)
    print("✅ 截图已保存: test_screenshots/shift_execution_list_manual.png")
    
    print("\n正在导航到制冷联动配置页面...")
    page.goto('http://localhost:3000/#/energy/shift/cooling/config')
    time.sleep(3)
    page.screenshot(path='test_screenshots/cooling_config_manual.png', full_page=True)
    print("✅ 截图已保存: test_screenshots/cooling_config_manual.png")
    
    print("\n正在导航到约束管理页面...")
    page.goto('http://localhost:3000/#/energy/shift/constraint/config')
    time.sleep(3)
    page.screenshot(path='test_screenshots/constraint_config_manual.png', full_page=True)
    print("✅ 截图已保存: test_screenshots/constraint_config_manual.png")
    
    print("\n正在导航到收益报表页面...")
    page.goto('http://localhost:3000/#/energy/shift/reports')
    time.sleep(3)
    page.screenshot(path='test_screenshots/reports_manual.png', full_page=True)
    print("✅ 截图已保存: test_screenshots/reports_manual.png")
    
    print("\n所有截图已保存完成！")
    print("浏览器将保持打开状态，您可以继续浏览...")
    print("按 Enter 键关闭浏览器...")
    input()
    
    browser.close()
    print("\n✅ 完成")
