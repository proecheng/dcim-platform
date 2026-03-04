const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('=== 性能测试开始 ===\n');

  // 1. 访问登录页
  console.log('1. 访问登录页...');
  const loginStart = Date.now();
  await page.goto('http://localhost:3000/login');
  await page.waitForLoadState('networkidle');
  console.log(`   登录页加载时间: ${Date.now() - loginStart}ms\n`);

  // 2. 登录
  console.log('2. 执行登录...');
  await page.fill('input[placeholder="用户名"]', 'admin');
  await page.fill('input[placeholder="密码"]', 'admin123');
  
  const loginClickStart = Date.now();
  await page.click('button.login-btn');
  
  // 等待跳转到首页
  await page.waitForFunction(() => {
    return window.location.pathname !== '/login';
  }, { timeout: 10000 });
  
  await page.waitForLoadState('networkidle');
  console.log(`   登录+跳转时间: ${Date.now() - loginClickStart}ms\n`);

  // 等待 2 秒让页面稳定
  await page.waitForTimeout(2000);

  // 3. 点击供配电监控
  console.log('3. 点击供配电监控菜单...');
  
  // 查找并点击供配电监控菜单
  const powerMenu = page.locator('text=供配电监控').first();
  await powerMenu.click();
  
  // 等待子菜单展开
  await page.waitForTimeout(500);
  
  // 点击供配电总览
  const overviewStart = Date.now();
  const overviewLink = page.locator('text=供配电总览').first();
  await overviewLink.click();
  
  // 等待 URL 变化
  await page.waitForURL('**/power/overview', { timeout: 10000 });
  
  // 等待页面加载完成
  await page.waitForLoadState('networkidle');
  
  // 等待关键元素出现
  await page.waitForSelector('.stat-card', { timeout: 10000 });
  
  const overviewLoadTime = Date.now() - overviewStart;
  console.log(`   供配电总览页面加载时间: ${overviewLoadTime}ms\n`);

  // 4. 测试页面交互响应
  console.log('4. 测试页面交互响应...');
  
  // 点击统计卡片
  const cardClickStart = Date.now();
  const firstCard = page.locator('.stat-card').first();
  await firstCard.click();
  await page.waitForTimeout(500);
  const cardClickTime = Date.now() - cardClickStart;
  console.log(`   卡片点击响应时间: ${cardClickTime}ms\n`);

  // 5. 测试窗口 resize
  console.log('5. 测试窗口 resize...');
  const resizeStart = Date.now();
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.waitForTimeout(500);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);
  const resizeTime = Date.now() - resizeStart;
  console.log(`   窗口 resize 响应时间: ${resizeTime}ms\n`);

  // 6. 切换到其他供配电子页面
  console.log('6. 切换到 UPS 监控页面...');
  const upsStart = Date.now();
  const upsLink = page.locator('text=UPS监控').first();
  await upsLink.click();
  await page.waitForURL('**/power/ups', { timeout: 10000 });
  await page.waitForLoadState('networkidle');
  const upsLoadTime = Date.now() - upsStart;
  console.log(`   UPS 监控页面加载时间: ${upsLoadTime}ms\n`);

  // 总结
  console.log('=== 性能测试完成 ===');
  console.log(`\n关键指标:`);
  console.log(`  - 供配电总览加载: ${overviewLoadTime}ms ${overviewLoadTime < 1000 ? '✅ 优秀' : overviewLoadTime < 2000 ? '⚠️ 一般' : '❌ 需优化'}`);
  console.log(`  - 页面交互响应: ${cardClickTime}ms ${cardClickTime < 500 ? '✅ 流畅' : '⚠️ 一般'}`);
  console.log(`  - 窗口 resize: ${resizeTime}ms ${resizeTime < 1000 ? '✅ 流畅' : '⚠️ 一般'}`);
  console.log(`  - UPS 页面加载: ${upsLoadTime}ms ${upsLoadTime < 1000 ? '✅ 优秀' : '⚠️ 一般'}`);
  
  // 保持浏览器打开 10 秒供人工观察
  console.log('\n浏览器将在 10 秒后关闭...');
  await page.waitForTimeout(10000);

  await browser.close();
})();
