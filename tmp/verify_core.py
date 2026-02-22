"""验证核心页面：登录 → 仪表盘 → 告警 → 能源管理"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
import json

results = {}

def check_page(page, name, url, wait_ms=3000):
    """导航到页面，截图，检查控制台错误"""
    print(f"  检查 {name} ({url})...")
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(wait_ms)
    
    # 截图
    path = f"D:/mytest1/tmp/verify_{name}.png"
    page.screenshot(path=path, full_page=False)
    
    # 检查页面内容
    title = page.title()
    body_text = page.inner_text("body")[:200] if page.query_selector("body") else ""
    
    # 检查是否有明显错误
    has_error = False
    error_msgs = []
    
    # 检查白屏
    if len(body_text.strip()) < 10:
        has_error = True
        error_msgs.append("页面可能白屏")
    
    # 检查 Element Plus 错误弹窗
    error_el = page.query_selector(".el-message--error")
    if error_el:
        error_msgs.append(f"错误提示: {error_el.inner_text()}")
    
    status = "❌" if has_error else "✅"
    results[name] = {"status": status, "url": url, "errors": error_msgs}
    print(f"    {status} {name}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # 收集控制台错误
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    
    # 1. 登录
    print("1. 登录...")
    page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(2000)
    page.screenshot(path="D:/mytest1/tmp/verify_login_page.png")
    
    # 填写登录表单
    username_input = page.query_selector("input[type='text'], input[placeholder*='用户'], input[placeholder*='账号']")
    password_input = page.query_selector("input[type='password']")
    
    if username_input and password_input:
        username_input.fill("admin")
        password_input.fill("admin123")
        page.wait_for_timeout(500)
        
        # 点击登录按钮
        login_btn = page.query_selector("button[type='submit'], button:has-text('登录'), .login-btn, .el-button--primary")
        if login_btn:
            login_btn.click()
            page.wait_for_timeout(3000)
        
        page.screenshot(path="D:/mytest1/tmp/verify_after_login.png")
        
        # 检查是否登录成功（URL 不再是 /login）
        current_url = page.url
        if "/login" not in current_url:
            results["login"] = {"status": "✅", "url": current_url, "errors": []}
            print(f"  ✅ 登录成功，跳转到 {current_url}")
        else:
            results["login"] = {"status": "❌", "url": current_url, "errors": ["登录后仍在登录页"]}
            print("  ❌ 登录失败")
    else:
        results["login"] = {"status": "❌", "url": page.url, "errors": ["找不到登录表单"]}
        print("  ❌ 找不到登录表单")
    
    # 2. 核心页面验证
    print("\n2. 核心页面验证...")
    pages_to_check = [
        ("dashboard", "http://localhost:3000/dashboard", 3000),
        ("alarm", "http://localhost:3000/alarm", 3000),
        ("energy_monitor", "http://localhost:3000/energy/monitor", 3000),
        ("energy_topology", "http://localhost:3000/energy/topology", 3000),
        ("energy_statistics", "http://localhost:3000/energy/statistics", 3000),
        ("environment_overview", "http://localhost:3000/environment/overview", 2000),
        ("environment_temperature", "http://localhost:3000/environment/temperature", 2000),
        ("power_overview", "http://localhost:3000/power/overview", 2000),
        ("cooling_overview", "http://localhost:3000/cooling/overview", 2000),
        ("security_overview", "http://localhost:3000/security/overview", 2000),
    ]
    
    for name, url, wait in pages_to_check:
        try:
            check_page(page, name, url, wait)
        except Exception as e:
            results[name] = {"status": "❌", "url": url, "errors": [str(e)]}
            print(f"    ❌ {name}: {e}")
    
    # 3. 汇总控制台错误
    if console_errors:
        # 去重
        unique_errors = list(set(console_errors))[:20]
        results["_console_errors"] = unique_errors
    
    browser.close()

# 输出结果
print("\n" + "="*60)
print("核心页面验证结果")
print("="*60)
for name, info in results.items():
    if name.startswith("_"):
        continue
    errors_str = f" — {', '.join(info['errors'])}" if info.get('errors') else ""
    print(f"  {info['status']} {name}{errors_str}")

if results.get("_console_errors"):
    print(f"\n  ⚠️ 控制台错误 ({len(results['_console_errors'])} 条):")
    for e in results["_console_errors"][:10]:
        print(f"    - {e[:120]}")

# 保存 JSON
with open("D:/mytest1/tmp/verify_core_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n截图保存在 D:/mytest1/tmp/verify_*.png")
