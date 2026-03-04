"""
Phase 2 负荷转移系统 - 自动化端到端测试脚本
使用 Playwright 测试所有 Phase 2 前端页面
"""
import json
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright, Page
# 测试配置
BASE_URL = "http://localhost:3000"
TEST_USER = "admin"
TEST_PASSWORD = "admin123"

# 测试结果存储
test_results = []

def log_test(page_name: str, test_name: str, status: str, details: str = ""):
    """记录测试结果"""
    result = {
        "page": page_name,
        "test": test_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    status_icon = "PASS" if status == "PASS" else "FAIL"
    print(f"[{status_icon}] [{page_name}] {test_name}: {status}")
    if details:
        print(f"   Details: {details}")

def login(page: Page) -> bool:
    """登录系统"""
    try:
        print("\n[INFO] Starting login...")
        page.goto(BASE_URL)
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        
        # 检查是否已登录
        if "/login" not in page.url:
            print("[INFO] Already logged in, skipping login")
            return True
        
        # 填写登录表单 - 使用更精确的选择器
        page.fill('input[placeholder="用户名"]', TEST_USER)
        page.fill('input[placeholder="密码"]', TEST_PASSWORD)
        
        # 点击登录按钮 - 使用文本选择器
        page.click('button:has-text("登 录")')
        
        # 等待登录完成
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        # 验证登录成功
        if "/login" in page.url:
            log_test("Login", "User login", "FAIL", "Still on login page")
            return False
        
        log_test("Login", "User login", "PASS", f"Logged in as {TEST_USER}")
        return True
    except Exception as e:
        log_test("Login", "User login", "FAIL", str(e))
        return False

def test_page(page: Page, page_name: str, route: str, expected_texts: list) -> bool:
    """测试页面渲染"""
    try:
        print(f"\n[INFO] Testing page: {page_name}")
        print(f"   Route: {route}")
        
        # 导航到页面
        page.goto(f"{BASE_URL}{route}")
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        # 截图
        screenshot_name = page_name.replace(' ', '_').replace('/', '_')
        screenshot_path = f"test_screenshots/{screenshot_name}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        log_test(page_name, "Screenshot", "PASS", f"Saved to {screenshot_path}")
        
        # 验证预期文本
        page_content = page.content()
        all_found = True
        
        for text in expected_texts:
            if text in page_content:
                log_test(page_name, f"Text: {text}", "PASS")
            else:
                log_test(page_name, f"Text: {text}", "FAIL", "Text not found")
                all_found = False
        
        return all_found
    except Exception as e:
        log_test(page_name, "Page rendering", "FAIL", str(e))
        return False

def generate_report():
    """生成测试报告"""
    print("\n" + "="*80)
    print("[INFO] Generating test report...")
    print("="*80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r["status"] == "PASS")
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    report = f"""
# Phase 2 Load Shift System - Automated Test Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Test Environment**: {BASE_URL}  
**Test User**: {TEST_USER}

---

## Test Summary

| Metric | Value |
|--------|-------|
| Total Tests | {total_tests} |
| Passed | {passed_tests} |
| Failed | {failed_tests} |
| Pass Rate | {pass_rate:.1f}% |

---

## Test Details

"""
    
    # 按页面分组
    pages = {}
    for result in test_results:
        page = result["page"]
        if page not in pages:
            pages[page] = []
        pages[page].append(result)
    
    for page_name, results in pages.items():
        report += f"\n### {page_name}\n\n"
        report += "| Test | Status | Details |\n"
        report += "|------|--------|---------|\n"
        
        for result in results:
            status_icon = "PASS" if result["status"] == "PASS" else "FAIL"
            details = result["details"][:50] + "..." if len(result["details"]) > 50 else result["details"]
            report += f"| {result['test']} | {status_icon} | {details} |\n"
    
    report += "\n---\n\n## Conclusion\n\n"
    
    if pass_rate == 100:
        report += "All tests passed! Phase 2 is fully functional.\n"
    elif pass_rate >= 80:
        report += f"Most tests passed ({pass_rate:.1f}%), but some issues need fixing.\n"
    else:
        report += f"High failure rate ({100-pass_rate:.1f}%), requires investigation.\n"
    
    # 保存报告
    report_path = "docs/Phase2_Automated_Test_Report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n[INFO] Test report saved to: {report_path}")
    print(f"[INFO] Test summary: {passed_tests}/{total_tests} passed ({pass_rate:.1f}%)")
    
    return report_path

def main():
    """主测试流程"""
    print("="*80)
    print("Phase 2 Load Shift System - Automated E2E Testing")
    print("="*80)
    
    # 创建截图目录
    os.makedirs("test_screenshots", exist_ok=True)
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN"
        )
        page = context.new_page()
        
        try:
            # 登录
            if not login(page):
                print("[ERROR] Login failed, aborting tests")
                return
            
            # 测试所有 Phase 2 页面
            test_page(page, "Execution List", "/#/energy/shift/execution/list", [
                "今日执行次数", "成功率", "节省电费", "执行时间", "方案名称"
            ])
            
            test_page(page, "Execution Detail", "/#/energy/shift/execution/detail/1", [
                "执行详情", "基本信息", "执行结果"
            ])
            
            test_page(page, "Execution Monitor", "/#/energy/shift/execution/monitor", [
                "当前执行状态", "执行进度", "实时负荷监控"
            ])
            
            test_page(page, "Cooling Config", "/#/energy/shift/cooling/config", [
                "联动状态", "当前 COP", "基础配置", "滞后时间"
            ])
            
            test_page(page, "Cooling Monitor", "/#/energy/shift/cooling/monitor", [
                "联动状态", "COP 趋势", "制冷设备状态"
            ])
            
            test_page(page, "Constraint Config", "/#/energy/shift/constraint/config", [
                "总约束数", "启用约束数", "约束名称", "约束类型"
            ])
            
            test_page(page, "Reports", "/#/energy/shift/reports", [
                "本月节省电费", "本月减少负荷", "月度报表", "年度报表"
            ])
            
            # 生成报告
            generate_report()
            
        except Exception as e:
            print(f"\n[ERROR] Test execution failed: {e}")
            log_test("System", "Test execution", "FAIL", str(e))
        finally:
            # 关闭浏览器
            browser.close()
            print("\n[INFO] Testing completed")

if __name__ == "__main__":
    main()
