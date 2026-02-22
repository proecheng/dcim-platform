"""验证二级页面：资产/网关/运维/系统设置/大屏"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
import json

results = {}

def check_page(page, name, url, wait_ms=3000):
    print(f"  检查 {name} ({url})...")
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(wait_ms)
    
    path = f"D:/mytest1/tmp/verify_{name}.png"
    page.screenshot(path=path, full_page=False)
    
    body_text = page.inner_text("body")[:200] if page.query_selector("body") else ""
    
    has_error = False
    error_msgs = []
    
    if len(body_text.strip()) < 10:
        has_error = True
        error_msgs.append("页面可能白屏")
    
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
    
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    
    # 登录
    print("登录...")
    page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(2000)
    
    username_input = page.query_selector("input[type='text'], input[placeholder*='用户'], input[placeholder*='账号']")
    password_input = page.query_selector("input[type='password']")
    
    if username_input and password_input:
        username_input.fill("admin")
        password_input.fill("admin123")
        page.wait_for_timeout(500)
        login_btn = page.query_selector("button[type='submit'], button:has-text('登录'), .login-btn, .el-button--primary")
        if login_btn:
            login_btn.click()
            page.wait_for_timeout(3000)
    
    print("\n二级页面验证...")
    pages = [
        ("asset", "http://localhost:3000/asset", 3000),
        ("capacity", "http://localhost:3000/capacity", 3000),
        ("gateway", "http://localhost:3000/gateway", 3000),
        ("device_manage", "http://localhost:3000/device-manage", 2000),
        ("device_status", "http://localhost:3000/device-status", 2000),
        ("workorder", "http://localhost:3000/operation/workorder", 2000),
        ("inspection", "http://localhost:3000/operation/inspection", 2000),
        ("knowledge", "http://localhost:3000/operation/knowledge", 2000),
        ("users", "http://localhost:3000/system/users", 2000),
        ("logs", "http://localhost:3000/system/logs", 2000),
        ("sites", "http://localhost:3000/system/sites", 2000),
        ("reports", "http://localhost:3000/reports", 2000),
        ("topology", "http://localhost:3000/topology/site-selection", 2000),
        ("bigscreen", "http://localhost:3000/bigscreen", 4000),
    ]
    
    for name, url, wait in pages:
        try:
            check_page(page, name, url, wait)
        except Exception as e:
            results[name] = {"status": "❌", "url": url, "errors": [str(e)]}
            print(f"    ❌ {name}: {e}")
    
    if console_errors:
        unique_errors = list(set(console_errors))[:20]
        results["_console_errors"] = unique_errors
    
    browser.close()

print("\n" + "="*60)
print("二级页面验证结果")
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

with open("D:/mytest1/tmp/verify_secondary_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n截图保存在 D:/mytest1/tmp/verify_*.png")
