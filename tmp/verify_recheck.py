"""重新验证疑似白屏的4个页面，增加等待时间"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
import json

results = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    console_errors = []
    page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    
    # 登录
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
    
    print(f"登录后 URL: {page.url}")
    
    # 重新验证 4 个页面，等待更长时间
    pages = [
        ("alarm", "http://localhost:3000/alarm", 6000),
        ("gateway", "http://localhost:3000/gateway", 6000),
        ("logs", "http://localhost:3000/system/logs", 6000),
        ("topology", "http://localhost:3000/topology/site-selection", 6000),
    ]
    
    for name, url, wait in pages:
        print(f"\n检查 {name} ({url})...")
        console_errors.clear()
        
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(wait)
        
        # 截图
        page.screenshot(path=f"D:/mytest1/tmp/verify2_{name}.png", full_page=False)
        
        # 获取页面文本
        body = page.query_selector("body")
        body_text = body.inner_text()[:500] if body else ""
        
        # 获取页面 HTML 长度
        html_len = len(page.content())
        
        # 检查是否有 el-table, el-card 等组件
        has_table = page.query_selector(".el-table") is not None
        has_card = page.query_selector(".el-card") is not None
        has_content = page.query_selector(".page-container, .app-container, main") is not None
        
        print(f"  body text length: {len(body_text.strip())}")
        print(f"  html length: {html_len}")
        print(f"  has table: {has_table}, has card: {has_card}, has content: {has_content}")
        print(f"  body text preview: {body_text.strip()[:200]}")
        
        if console_errors:
            print(f"  console errors: {len(console_errors)}")
            for e in console_errors[:5]:
                print(f"    {e[:150]}")
        
        results[name] = {
            "body_text_len": len(body_text.strip()),
            "html_len": html_len,
            "has_table": has_table,
            "has_card": has_card,
            "has_content": has_content,
            "console_errors": console_errors[:5],
            "body_preview": body_text.strip()[:200]
        }
    
    browser.close()

with open("D:/mytest1/tmp/verify2_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
