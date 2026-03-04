"""
使用Playwright访问配电配置页面并检查问题
"""
import asyncio
from playwright.async_api import async_playwright
import time

async def check_power_config_page():
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 1. 访问登录页
            print("访问登录页...")
            await page.goto("http://localhost:3000")
            await page.wait_for_load_state("networkidle")
            
            # 2. 登录
            print("登录系统...")
            await page.fill('input[type="text"]', "admin")
            await page.fill('input[type="password"]', "admin123")
            await page.click('.login-btn')
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 3. 导航到配电配置页
            print("导航到配电配置页...")
            # 查找菜单项
            menu_items = await page.query_selector_all('.el-menu-item, .el-sub-menu__title')
            
            # 打印所有菜单项
            print("\n可用菜单项:")
            for item in menu_items:
                text = await item.inner_text()
                print(f"  - {text}")
            
            # 尝试点击"采集配置"或"配电配置"
            collection_menu = await page.query_selector('text=采集配置')
            if collection_menu:
                await collection_menu.click()
                await asyncio.sleep(1)
            
            # 查找"配电配置"链接
            power_config_link = await page.query_selector('text=配电配置')
            if power_config_link:
                print("找到配电配置链接，点击...")
                await power_config_link.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
            else:
                # 尝试直接访问URL
                print("直接访问配电配置URL...")
                await page.goto("http://localhost:3000/collection/power-config")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
            
            # 4. 检查页面内容
            print("\n检查页面内容...")
            
            # 检查是否有错误信息
            error_messages = await page.query_selector_all('.el-message--error, .error-message')
            if error_messages:
                print(f"发现 {len(error_messages)} 个错误信息:")
                for msg in error_messages:
                    text = await msg.inner_text()
                    print(f"  错误: {text}")
            
            # 检查控制台错误
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
            
            # 检查网络错误
            network_errors = []
            page.on("response", lambda response: network_errors.append(response) if response.status >= 400 else None)
            
            await asyncio.sleep(2)
            
            if console_errors:
                print(f"\n控制台错误 ({len(console_errors)}):")
                for err in console_errors[:5]:  # 只显示前5个
                    print(f"  {err.text}")
            
            if network_errors:
                print(f"\n网络错误 ({len(network_errors)}):")
                for resp in network_errors[:5]:
                    print(f"  {resp.status} {resp.url}")
            
            # 5. 截图
            screenshot_path = "power_config_page.png"
            await page.screenshot(path=screenshot_path)
            print(f"\n页面截图已保存: {screenshot_path}")
            
            # 6. 获取页面HTML
            html = await page.content()
            with open("power_config_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("页面HTML已保存: power_config_page.html")
            
            # 7. 检查页面标题和URL
            title = await page.title()
            url = page.url
            print(f"\n页面标题: {title}")
            print(f"当前URL: {url}")
            
            # 保持浏览器打开以便手动检查
            print("\n浏览器将保持打开30秒，请手动检查...")
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_power_config_page())
