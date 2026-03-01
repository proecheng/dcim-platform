# 测试指南

本文档介绍算力中心智能监控系统 (DCIM) 的测试框架、测试策略和最佳实践。

## 测试概览

### 测试框架

| 层级 | 框架 | 覆盖范围 | 目标覆盖率 |
|------|------|---------|-----------|
| 后端单元测试 | pytest | 业务逻辑、服务层 | > 80% |
| 后端集成测试 | pytest + TestClient | API 端点 | > 70% |
| 前端单元测试 | Vitest + Vue Test Utils | 组件、工具函数 | > 75% |
| 前端集成测试 | Vitest | 页面交互 | > 60% |
| E2E 测试 | Playwright | 关键用户流程 | 核心场景 |

### 测试统计

**后端测试 (1350+ 用例):**
- API 测试: 450+ 用例
- 服务层测试: 600+ 用例
- 集成测试: 300+ 用例

**前端测试 (1182 用例):**
- 组件测试: 800+ 用例
- 工具函数测试: 200+ 用例
- Store 测试: 182 用例

## 后端测试

### 环境准备

```bash
cd backend

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装测试依赖
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx
```

### 运行测试

**运行全部测试:**
```bash
pytest
```

**运行特定目录:**
```bash
pytest tests/api/          # API 测试
pytest tests/services/     # 服务层测试
pytest tests/demo/         # 演示系统测试
```

**运行单个测试文件:**
```bash
pytest tests/api/test_auth.py
```

**运行单个测试用例:**
```bash
pytest tests/api/test_auth.py::test_login_success
```

**按名称匹配测试:**
```bash
pytest -k "test_login"     # 运行所有包含 "login" 的测试
pytest -k "not slow"       # 排除标记为 slow 的测试
```

**显示详细输出:**
```bash
pytest -v                  # 详细模式
pytest -vv                 # 更详细
pytest -s                  # 显示 print 输出
```

**生成覆盖率报告:**
```bash
# 终端输出
pytest --cov=app --cov-report=term

# HTML 报告
pytest --cov=app --cov-report=html
# 报告位置: htmlcov/index.html

# XML 报告（CI/CD）
pytest --cov=app --cov-report=xml
```

**并行运行（加速）:**
```bash
pip install pytest-xdist
pytest -n auto  # 自动检测 CPU 核心数
pytest -n 4     # 使用 4 个进程
```

### 测试结构

```
backend/tests/
├── conftest.py              # 全局 fixtures
├── api/                     # API 测试
│   ├── test_auth.py        # 认证 API
│   ├── test_devices.py     # 设备 API
│   └── test_alarms.py      # 告警 API
├── services/                # 服务层测试
│   ├── test_alarm_engine.py
│   ├── test_energy_core.py
│   └── test_gateway.py
└── demo/                    # 演示系统测试
    └── test_demo_loader.py
```

### 编写测试

#### 基础测试示例

```python
# tests/api/test_devices.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_devices(client: AsyncClient, auth_headers: dict):
    """测试获取设备列表"""
    response = await client.get("/api/v1/devices", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_create_device(client: AsyncClient, auth_headers: dict):
    """测试创建设备"""
    device_data = {
        "name": "测试设备",
        "device_type": "UPS",
        "location": "机房A"
    }
    
    response = await client.post(
        "/api/v1/devices",
        json=device_data,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == device_data["name"]
    assert "id" in data
```

#### 使用 Fixtures

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from app.main import app
from app.core.database import async_session

@pytest.fixture
async def client():
    """异步 HTTP 客户端"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client: AsyncClient):
    """认证头"""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def db_session():
    """数据库会话"""
    async with async_session() as session:
        yield session
        await session.rollback()  # 测试后回滚
```

#### 参数化测试

```python
@pytest.mark.parametrize("username,password,expected_status", [
    ("admin", "admin123", 200),      # 正确凭证
    ("admin", "wrong", 401),         # 错误密码
    ("nonexist", "admin123", 401),   # 不存在的用户
    ("", "", 422),                   # 空凭证
])
@pytest.mark.asyncio
async def test_login_scenarios(client, username, password, expected_status):
    """测试多种登录场景"""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password}
    )
    assert response.status_code == expected_status
```

#### Mock 外部依赖

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_weather_api_with_mock(client, auth_headers):
    """测试天气 API（Mock 外部调用）"""
    mock_weather_data = {
        "temperature": 25.5,
        "humidity": 60
    }
    
    with patch("app.services.weather.fetch_weather", new=AsyncMock(return_value=mock_weather_data)):
        response = await client.get("/api/v1/weather", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["temperature"] == 25.5
```

### 测试最佳实践

1. **测试命名规范**
   - 文件: `test_<module>.py`
   - 函数: `test_<action>_<expected_result>`
   - 示例: `test_create_device_success`, `test_login_invalid_password`

2. **AAA 模式**
   ```python
   async def test_example():
       # Arrange - 准备测试数据
       device_data = {"name": "测试设备"}
       
       # Act - 执行操作
       response = await client.post("/api/v1/devices", json=device_data)
       
       # Assert - 验证结果
       assert response.status_code == 201
   ```

3. **测试隔离**
   - 每个测试独立运行
   - 使用 fixtures 清理数据
   - 避免测试间依赖

4. **覆盖边界情况**
   - 正常情况
   - 异常情况（错误输入、权限不足）
   - 边界值（空值、最大值、最小值）

## 前端测试

### 环境准备

```bash
cd frontend

# 安装依赖
npm install

# 安装测试依赖（已包含在 package.json）
npm install -D vitest @vue/test-utils happy-dom
```

### 运行测试

**运行全部测试:**
```bash
npm run test
```

**监听模式（开发时）:**
```bash
npm run test:watch
```

**生成覆盖率报告:**
```bash
npm run test:coverage
# 报告位置: coverage/index.html
```

**运行特定测试:**
```bash
npm run test -- components/AlarmList.test.ts
```

### 测试结构

```
frontend/src/__tests__/
├── setup.ts                 # 测试配置
├── components/              # 组件测试
│   ├── AlarmList.test.ts
│   ├── DeviceCard.test.ts
│   └── EnergyChart.test.ts
├── stores/                  # Store 测试
│   ├── user.test.ts
│   ├── alarm.test.ts
│   └── energy.test.ts
├── utils/                   # 工具函数测试
│   ├── format.test.ts
│   └── validate.test.ts
└── views/                   # 页面测试
    ├── Dashboard.test.ts
    └── Login.test.ts
```

### 编写测试

#### 组件测试

```typescript
// src/__tests__/components/AlarmList.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AlarmList from '@/components/AlarmList.vue'

describe('AlarmList', () => {
  it('渲染告警列表', () => {
    const alarms = [
      { id: 1, level: 'critical', message: '温度过高' },
      { id: 2, level: 'warning', message: '湿度异常' }
    ]
    
    const wrapper = mount(AlarmList, {
      props: { alarms }
    })
    
    expect(wrapper.findAll('.alarm-item')).toHaveLength(2)
    expect(wrapper.text()).toContain('温度过高')
  })
  
  it('点击告警触发事件', async () => {
    const wrapper = mount(AlarmList, {
      props: { alarms: [{ id: 1, level: 'critical', message: '测试' }] }
    })
    
    await wrapper.find('.alarm-item').trigger('click')
    
    expect(wrapper.emitted('alarm-click')).toBeTruthy()
    expect(wrapper.emitted('alarm-click')?.[0]).toEqual([1])
  })
})
```

#### Store 测试

```typescript
// src/__tests__/stores/user.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

describe('User Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('初始状态', () => {
    const store = useUserStore()
    
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
  })
  
  it('登录成功', async () => {
    const store = useUserStore()
    
    await store.login('admin', 'admin123')
    
    expect(store.isLoggedIn).toBe(true)
    expect(store.user?.username).toBe('admin')
  })
  
  it('登出清除状态', async () => {
    const store = useUserStore()
    await store.login('admin', 'admin123')
    
    store.logout()
    
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
  })
})
```

#### 工具函数测试

```typescript
// src/__tests__/utils/format.test.ts
import { describe, it, expect } from 'vitest'
import { formatNumber, formatDate } from '@/utils/format'

describe('formatNumber', () => {
  it('格式化整数', () => {
    expect(formatNumber(1234)).toBe('1,234')
  })
  
  it('格式化小数', () => {
    expect(formatNumber(1234.56, 2)).toBe('1,234.56')
  })
  
  it('处理 null', () => {
    expect(formatNumber(null)).toBe('-')
  })
})

describe('formatDate', () => {
  it('格式化日期', () => {
    const date = new Date('2026-03-01 12:00:00')
    expect(formatDate(date)).toBe('2026-03-01 12:00:00')
  })
})
```

#### Mock API 请求

```typescript
import { describe, it, expect, vi } from 'vitest'
import { getDevices } from '@/api/modules/device'

// Mock axios
vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: {
        items: [{ id: 1, name: '设备1' }],
        total: 1
      }
    }))
  }
}))

describe('Device API', () => {
  it('获取设备列表', async () => {
    const result = await getDevices()
    
    expect(result.items).toHaveLength(1)
    expect(result.items[0].name).toBe('设备1')
  })
})
```

### 前端测试最佳实践

1. **测试用户行为，而非实现细节**
   ```typescript
   // ❌ 不好 - 测试实现细节
   expect(wrapper.vm.internalCounter).toBe(5)
   
   // ✅ 好 - 测试用户可见的行为
   expect(wrapper.text()).toContain('5')
   ```

2. **使用语义化查询**
   ```typescript
   // ✅ 推荐
   wrapper.find('[data-testid="submit-button"]')
   wrapper.find('button[type="submit"]')
   
   // ❌ 避免
   wrapper.find('.btn.btn-primary.mt-3')
   ```

3. **异步操作使用 await**
   ```typescript
   await wrapper.find('button').trigger('click')
   await wrapper.vm.$nextTick()
   ```

4. **隔离组件依赖**
   ```typescript
   const wrapper = mount(MyComponent, {
     global: {
       stubs: {
         'el-button': true,  // Stub Element Plus 组件
         'router-link': true
       }
     }
   })
   ```

## E2E 测试

### 环境准备

```bash
# 安装 Playwright
npm install -D @playwright/test

# 安装浏览器
npx playwright install
```

### 运行 E2E 测试

```bash
# 运行全部 E2E 测试
npm run test:e2e

# 运行特定浏览器
npx playwright test --project=chromium

# 调试模式
npx playwright test --debug

# 生成报告
npx playwright show-report
```

### 编写 E2E 测试

```typescript
// e2e/login.spec.ts
import { test, expect } from '@playwright/test'

test.describe('登录流程', () => {
  test('成功登录', async ({ page }) => {
    // 访问登录页
    await page.goto('http://localhost:3000/login')
    
    // 填写表单
    await page.fill('input[name="username"]', 'admin')
    await page.fill('input[name="password"]', 'admin123')
    
    // 点击登录
    await page.click('button[type="submit"]')
    
    // 验证跳转到首页
    await expect(page).toHaveURL('http://localhost:3000/dashboard')
    
    // 验证用户信息显示
    await expect(page.locator('.user-info')).toContainText('admin')
  })
  
  test('错误密码提示', async ({ page }) => {
    await page.goto('http://localhost:3000/login')
    
    await page.fill('input[name="username"]', 'admin')
    await page.fill('input[name="password"]', 'wrong')
    await page.click('button[type="submit"]')
    
    // 验证错误提示
    await expect(page.locator('.error-message')).toBeVisible()
    await expect(page.locator('.error-message')).toContainText('用户名或密码错误')
  })
})
```

### E2E 测试场景

**核心用户流程:**
1. 登录/登出
2. 查看实时数据
3. 创建/处理告警
4. 查看能耗统计
5. 导出报表

**示例: 告警处理流程**
```typescript
test('告警处理流程', async ({ page }) => {
  // 登录
  await page.goto('http://localhost:3000/login')
  await page.fill('input[name="username"]', 'admin')
  await page.fill('input[name="password"]', 'admin123')
  await page.click('button[type="submit"]')
  
  // 进入告警页面
  await page.click('text=告警管理')
  await expect(page).toHaveURL(/.*alarms/)
  
  // 选择第一条告警
  await page.click('.alarm-list .alarm-item:first-child')
  
  // 确认告警
  await page.click('button:has-text("确认")')
  await page.fill('textarea[name="remark"]', '已确认，正在处理')
  await page.click('button:has-text("提交")')
  
  // 验证状态更新
  await expect(page.locator('.alarm-status')).toContainText('处理中')
})
```

## CI/CD 集成

### GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Run tests
        run: |
          cd frontend
          npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend/coverage/coverage-final.json
```

### 测试覆盖率要求

| 层级 | 最低覆盖率 | 推荐覆盖率 |
|------|-----------|-----------|
| 后端核心服务 | 80% | 90% |
| 后端 API | 70% | 85% |
| 前端组件 | 75% | 85% |
| 前端工具函数 | 90% | 95% |

### 质量门禁

```yaml
# 在 CI 中强制覆盖率要求
pytest --cov=app --cov-fail-under=80
```

## 性能测试

### 使用 Locust 进行负载测试

```python
# locustfile.py
from locust import HttpUser, task, between

class DCIMUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """登录获取 Token"""
        response = self.client.post("/api/v1/auth/login", data={
            "username": "admin",
            "password": "admin123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def get_realtime_data(self):
        """获取实时数据"""
        self.client.get("/api/v1/realtime", headers=self.headers)
    
    @task(2)
    def get_alarms(self):
        """获取告警列表"""
        self.client.get("/api/v1/alarms", headers=self.headers)
    
    @task(1)
    def get_devices(self):
        """获取设备列表"""
        self.client.get("/api/v1/devices", headers=self.headers)
```

**运行负载测试:**
```bash
pip install locust
locust -f locustfile.py --host=http://localhost:8080
# 访问 http://localhost:8089 查看测试界面
```

## 测试数据管理

### 使用 Fixtures 准备测试数据

```python
# tests/conftest.py
@pytest.fixture
async def sample_devices(db_session):
    """创建示例设备"""
    devices = [
        Device(name="UPS-01", device_type="UPS", location="机房A"),
        Device(name="空调-01", device_type="空调", location="机房A"),
    ]
    db_session.add_all(devices)
    await db_session.commit()
    return devices

@pytest.fixture
async def sample_alarms(db_session, sample_devices):
    """创建示例告警"""
    alarms = [
        Alarm(
            device_id=sample_devices[0].id,
            level="critical",
            message="温度过高"
        )
    ]
    db_session.add_all(alarms)
    await db_session.commit()
    return alarms
```

### 测试数据库隔离

```python
# 使用事务回滚确保测试隔离
@pytest.fixture
async def db_session():
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

## 调试技巧

### 后端调试

```bash
# 运行单个测试并进入调试器
pytest tests/api/test_auth.py::test_login -s --pdb

# 在测试中设置断点
import pdb; pdb.set_trace()
```

### 前端调试

```typescript
// 在测试中打印组件 HTML
console.log(wrapper.html())

// 打印组件数据
console.log(wrapper.vm.$data)

// 使用 debug 模式
wrapper.find('button').trigger('click')
await wrapper.vm.$nextTick()
console.log(wrapper.html())
```

## 常见问题

### 1. 测试数据库冲突

**问题:** 测试运行时数据库被锁定。

**解决:**
```python
# 使用独立的测试数据库
DATABASE_URL=sqlite+aiosqlite:///./test.db pytest
```

### 2. 异步测试超时

**问题:** 异步测试运行超时。

**解决:**
```python
@pytest.mark.asyncio
@pytest.mark.timeout(10)  # 设置 10 秒超时
async def test_slow_operation():
    ...
```

### 3. 前端组件找不到

**问题:** `Cannot find module '@/components/xxx'`

**解决:**
```typescript
// vitest.config.ts
export default {
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
}
```

## 测试清单

**提交代码前检查:**
- [ ] 所有测试通过
- [ ] 新功能有对应测试
- [ ] 覆盖率达标
- [ ] 无 console.log 残留
- [ ] 测试命名清晰
- [ ] 边界情况已覆盖

**发布前检查:**
- [ ] 全部单元测试通过
- [ ] 全部集成测试通过
- [ ] E2E 核心流程通过
- [ ] 性能测试达标
- [ ] 覆盖率报告生成

## 参考资源

- [pytest 文档](https://docs.pytest.org/)
- [Vitest 文档](https://vitest.dev/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [Playwright 文档](https://playwright.dev/)
- [测试最佳实践](https://testingjavascript.com/)
