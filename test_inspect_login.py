"""
简化版测试脚本 - 先查看登录页面结构
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("访问登录页面...")
    page.goto('http://localhost:3000', wait_until='networkidle')
    time.sleep(2)
    
    # 保存页面截图和 HTML
    page.screenshot(path='login_page.png', full_page=True)
    
    with open('login_page.html', 'w', encoding='utf-8') as f:
        f.write(page.content())
    
    print("已保存 login_page.png 和 login_page.html")
    print("查找输入框...")
    
    # 查找所有输入框
    inputs = page.locator('input').all()
    print(f"找到 {len(inputs)} 个输入框:")
    for i, inp in enumerate(inputs):
        try:
            placeholder = inp.get_attribute('placeholder')
            input_type = inp.get_attribute('type')
            print(f"  {i+1}. type={input_type}, placeholder={placeholder}")
        except:
            pass
    
    input("按 Enter 关闭...")
    browser.close()
