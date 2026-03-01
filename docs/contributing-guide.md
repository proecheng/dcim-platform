# 贡献指南

欢迎为算力中心智能监控系统 (DCIM) 贡献代码！本文档提供代码规范、开发流程和最佳实践。

## 开发环境设置

### 1. Fork 和克隆仓库

```bash
# Fork 仓库到你的 GitHub 账户
# 然后克隆你的 Fork
git clone https://github.com/your-username/dcim.git
cd dcim

# 添加上游仓库
git remote add upstream https://github.com/original-repo/dcim.git
```

### 2. 安装依赖

**后端:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**前端:**
```bash
cd frontend
npm install
```

### 3. 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置开发环境
```

### 4. 启动开发服务

```bash
# 后端
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173 开始开发。

## Git 工作流程

### 分支策略

```
main          # 主分支，稳定版本
├── develop   # 开发分支，最新功能
├── feature/* # 功能分支
├── bugfix/*  # 修复分支
└── hotfix/*  # 紧急修复分支
```

### 创建功能分支

```bash
# 从 develop 创建功能分支
git checkout develop
git pull upstream develop
git checkout -b feature/your-feature-name

# 开发完成后推送
git push origin feature/your-feature-name
```

### 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feature/<描述>` | `feature/add-alarm-filter` |
| 修复 | `bugfix/<描述>` | `bugfix/fix-login-error` |
| 热修复 | `hotfix/<描述>` | `hotfix/fix-critical-bug` |
| 文档 | `docs/<描述>` | `docs/update-readme` |
| 重构 | `refactor/<描述>` | `refactor/optimize-query` |

## 代码规范

### Python 代码规范

遵循 [PEP 8](https://pep8.org/) 和项目特定规范。

**格式化工具:**
```bash
# 安装工具
pip install black isort ruff

# 格式化代码
black backend/app
isort backend/app

# 检查代码质量
ruff check backend/app
```

**命名规范:**
```python
# 类名: PascalCase
class DeviceService:
    pass

# 函数/变量: snake_case
def get_device_list():
    device_count = 10
    return device_count

# 常量: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

# 私有成员: 前缀 _
class MyClass:
    def __init__(self):
        self._private_var = 0
    
    def _private_method(self):
        pass
```

**类型注解:**
```python
from typing import List, Optional, Dict

def get_devices(
    skip: int = 0,
    limit: int = 100,
    device_type: Optional[str] = None
) -> List[Dict[str, any]]:
    """获取设备列表
    
    Args:
        skip: 跳过记录数
        limit: 返回记录数
        device_type: 设备类型过滤
    
    Returns:
        设备列表
    """
    pass
```

**异步代码:**
```python
# 使用 async/await
async def get_device(device_id: int) -> Device:
    async with async_session() as session:
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        return result.scalar_one_or_none()
```

**错误处理:**
```python
from fastapi import HTTPException

# 使用具体的异常类型
try:
    device = await get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### TypeScript 代码规范

遵循 [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript) 和 Vue 3 规范。

**格式化工具:**
```bash
# 安装工具（已包含在 package.json）
npm install -D eslint prettier

# 格式化代码
npm run lint
npm run format
```

**命名规范:**
```typescript
// 接口/类型: PascalCase
interface DeviceInfo {
  id: number
  name: string
}

// 变量/函数: camelCase
const deviceCount = 10
function getDeviceList() {}

// 常量: UPPER_SNAKE_CASE
const MAX_RETRY_COUNT = 3
const API_BASE_URL = '/api/v1'

// 组件: PascalCase
const DeviceList = defineComponent({})
```

**Vue 组件结构:**
```vue
<script setup lang="ts">
// 1. 导入
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

// 2. Props 和 Emits
interface Props {
  deviceId: number
}
const props = defineProps<Props>()

interface Emits {
  (e: 'update', value: string): void
}
const emit = defineEmits<Emits>()

// 3. 响应式数据
const loading = ref(false)
const devices = ref<Device[]>([])

// 4. 计算属性
const deviceCount = computed(() => devices.value.length)

// 5. 方法
const fetchDevices = async () => {
  loading.value = true
  try {
    devices.value = await getDevices()
  } finally {
    loading.value = false
  }
}

// 6. 生命周期
onMounted(() => {
  fetchDevices()
})
</script>

<template>
  <div class="device-list">
    <!-- 模板内容 -->
  </div>
</template>

<style scoped lang="scss">
.device-list {
  // 样式
}
</style>
```

**类型定义:**
```typescript
// 使用 interface 定义对象类型
interface Device {
  id: number
  name: string
  type: DeviceType
  status: 'online' | 'offline'
}

// 使用 type 定义联合类型
type DeviceType = 'UPS' | '空调' | 'PDU'

// 使用泛型
interface ApiResponse<T> {
  code: number
  data: T
  message: string
}
```

**异步处理:**
```typescript
// 使用 async/await
const fetchData = async () => {
  try {
    const response = await api.getDevices()
    devices.value = response.data
  } catch (error) {
    console.error('获取设备失败:', error)
    ElMessage.error('获取设备失败')
  }
}

// 使用 Promise
api.getDevices()
  .then(response => {
    devices.value = response.data
  })
  .catch(error => {
    console.error('获取设备失败:', error)
  })
```

### 注释规范

**Python 文档字符串:**
```python
def calculate_pue(it_power: float, total_power: float) -> float:
    """计算 PUE 值
    
    PUE (Power Usage Effectiveness) 是数据中心能效指标，
    计算公式: PUE = 总功率 / IT 设备功率
    
    Args:
        it_power: IT 设备功率 (kW)
        total_power: 总功率 (kW)
    
    Returns:
        PUE 值，正常范围 1.0-3.0
    
    Raises:
        ValueError: 当功率值无效时
    
    Example:
        >>> calculate_pue(100, 150)
        1.5
    """
    if it_power <= 0 or total_power <= 0:
        raise ValueError("功率值必须大于 0")
    return total_power / it_power
```

**TypeScript JSDoc:**
```typescript
/**
 * 格式化数字为千分位
 * 
 * @param value - 要格式化的数字
 * @param decimals - 小数位数，默认 0
 * @returns 格式化后的字符串
 * 
 * @example
 * formatNumber(1234.56, 2) // "1,234.56"
 */
export function formatNumber(value: number, decimals = 0): string {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}
```

**行内注释:**
```python
# 好的注释 - 解释为什么
# 使用指数退避避免频繁重试导致服务过载
retry_delay = base_delay * (2 ** retry_count)

# 不好的注释 - 重复代码
# 设置重试延迟
retry_delay = base_delay * (2 ** retry_count)
```

## 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

### 提交格式

```
<类型>(<范围>): <简短描述>

<详细描述>

<关联 Issue>
```

### 提交类型

| 类型 | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | `feat(alarm): 添加告警过滤功能` |
| fix | 修复 Bug | `fix(login): 修复登录失败问题` |
| docs | 文档更新 | `docs(readme): 更新安装说明` |
| style | 代码格式（不影响功能） | `style(api): 格式化代码` |
| refactor | 重构 | `refactor(energy): 优化能耗计算逻辑` |
| perf | 性能优化 | `perf(query): 优化数据库查询` |
| test | 测试相关 | `test(device): 添加设备 API 测试` |
| chore | 构建/工具相关 | `chore(deps): 升级依赖版本` |

### 提交示例

```bash
# 功能提交
git commit -m "feat(alarm): 添加告警级别过滤

- 支持按告警级别筛选
- 添加级别下拉选择器
- 更新 API 接口

Closes #123"

# 修复提交
git commit -m "fix(login): 修复 bcrypt 版本兼容问题

降级 bcrypt 到 4.0.1 以兼容 passlib 1.7.4

Fixes #456"

# 文档提交
git commit -m "docs(deployment): 完善部署指南

添加 Docker 部署章节和常见问题排查"
```

### 提交最佳实践

1. **原子提交** - 每次提交只做一件事
2. **清晰描述** - 说明做了什么和为什么
3. **关联 Issue** - 使用 `Closes #123` 或 `Fixes #456`
4. **中文描述** - 项目使用中文，提交信息也用中文

## Pull Request 流程

### 1. 创建 PR

```bash
# 确保代码最新
git checkout develop
git pull upstream develop

# 合并到你的功能分支
git checkout feature/your-feature
git merge develop

# 解决冲突（如有）
# 推送到你的 Fork
git push origin feature/your-feature
```

在 GitHub 上创建 Pull Request，从你的 `feature/your-feature` 到上游的 `develop`。

### 2. PR 标题和描述

**标题格式:**
```
feat(alarm): 添加告警级别过滤功能
```

**描述模板:**
```markdown
## 变更说明
简要描述这个 PR 做了什么。

## 变更类型
- [ ] 新功能
- [ ] Bug 修复
- [ ] 文档更新
- [ ] 代码重构
- [ ] 性能优化
- [ ] 测试相关

## 测试
- [ ] 添加了单元测试
- [ ] 添加了集成测试
- [ ] 手动测试通过

## 截图（如适用）
添加截图展示变更效果。

## 关联 Issue
Closes #123

## 检查清单
- [ ] 代码遵循项目规范
- [ ] 通过所有测试
- [ ] 更新了相关文档
- [ ] 无 console.log 残留
- [ ] 提交信息符合规范
```

### 3. 代码审查

**审查者关注点:**
- 代码质量和可读性
- 是否遵循项目规范
- 测试覆盖率
- 性能影响
- 安全问题

**作者响应:**
- 及时回复审查意见
- 解释设计决策
- 修改代码并推送更新
- 标记已解决的评论

### 4. 合并要求

PR 合并前必须满足:
- [ ] 至少 1 个审查者批准
- [ ] 所有 CI 检查通过
- [ ] 无未解决的评论
- [ ] 代码冲突已解决
- [ ] 提交历史清晰（必要时 squash）

## 代码审查标准

### 审查清单

**功能性:**
- [ ] 实现了需求功能
- [ ] 边界情况处理正确
- [ ] 错误处理完善

**代码质量:**
- [ ] 命名清晰易懂
- [ ] 逻辑简洁明了
- [ ] 无重复代码
- [ ] 注释恰当

**性能:**
- [ ] 无明显性能问题
- [ ] 数据库查询优化
- [ ] 避免不必要的计算

**安全:**
- [ ] 输入验证
- [ ] SQL 注入防护
- [ ] XSS 防护
- [ ] 敏感信息保护

**测试:**
- [ ] 有对应测试
- [ ] 测试覆盖关键路径
- [ ] 测试可读性好

### 审查示例

**好的审查评论:**
```
建议使用 `filter()` 替代列表推导式，提高可读性:

```python
# 当前
devices = [d for d in all_devices if d.status == 'online']

# 建议
devices = list(filter(lambda d: d.status == 'online', all_devices))
```

或者更简洁:
```python
devices = [d for d in all_devices if d.is_online]
```
```

**不好的审查评论:**
```
这段代码不好，重写。
```

## 开发最佳实践

### 1. 保持代码简洁

```python
# ❌ 不好 - 过于复杂
def process_device(device):
    if device is not None:
        if device.status == 'online':
            if device.type == 'UPS':
                return True
    return False

# ✅ 好 - 简洁清晰
def is_online_ups(device):
    return (
        device is not None
        and device.status == 'online'
        and device.type == 'UPS'
    )
```

### 2. 避免魔法数字

```python
# ❌ 不好
if temperature > 30:
    trigger_alarm()

# ✅ 好
TEMPERATURE_THRESHOLD = 30  # 摄氏度

if temperature > TEMPERATURE_THRESHOLD:
    trigger_alarm()
```

### 3. 使用有意义的变量名

```python
# ❌ 不好
d = get_data()
for i in d:
    process(i)

# ✅ 好
devices = get_devices()
for device in devices:
    process_device(device)
```

### 4. 单一职责原则

```python
# ❌ 不好 - 函数做太多事
def process_and_save_device(device_data):
    # 验证数据
    if not device_data.get('name'):
        raise ValueError('缺少设备名称')
    
    # 转换数据
    device = Device(**device_data)
    
    # 保存到数据库
    db.add(device)
    db.commit()
    
    # 发送通知
    send_notification(f'设备 {device.name} 已创建')
    
    return device

# ✅ 好 - 职责分离
def validate_device_data(device_data):
    if not device_data.get('name'):
        raise ValueError('缺少设备名称')

def create_device(device_data):
    validate_device_data(device_data)
    device = Device(**device_data)
    db.add(device)
    db.commit()
    return device

def notify_device_created(device):
    send_notification(f'设备 {device.name} 已创建')
```

### 5. 错误处理

```python
# ❌ 不好 - 捕获所有异常
try:
    result = risky_operation()
except:
    pass

# ✅ 好 - 具体异常处理
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f'数据验证失败: {e}')
    raise HTTPException(status_code=400, detail=str(e))
except DatabaseError as e:
    logger.error(f'数据库错误: {e}')
    raise HTTPException(status_code=500, detail='数据库操作失败')
```

## 测试要求

### 新功能必须包含测试

```python
# 功能代码
def calculate_pue(it_power: float, total_power: float) -> float:
    if it_power <= 0 or total_power <= 0:
        raise ValueError("功率值必须大于 0")
    return total_power / it_power

# 对应测试
def test_calculate_pue_normal():
    assert calculate_pue(100, 150) == 1.5

def test_calculate_pue_invalid_input():
    with pytest.raises(ValueError):
        calculate_pue(0, 150)
    
    with pytest.raises(ValueError):
        calculate_pue(100, -50)
```

### 测试覆盖率要求

- 新增代码覆盖率 > 80%
- 核心业务逻辑覆盖率 > 90%
- 运行 `pytest --cov` 检查覆盖率

## 文档要求

### 更新相关文档

代码变更时，同步更新:
- API 文档（如果接口变更）
- README.md（如果功能变更）
- 用户手册（如果 UI 变更）
- CHANGELOG.md（记录变更）

### 文档风格

- 使用中文
- 结构清晰，易于查找
- 包含示例代码
- 保持更新

## 发布流程

### 版本号规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：`主版本.次版本.修订号`

- **主版本**: 不兼容的 API 变更
- **次版本**: 向下兼容的功能新增
- **修订号**: 向下兼容的问题修正

示例: `3.2.1`

### 发布步骤

1. **更新版本号**
   ```bash
   # backend/app/core/config.py
   app_version: str = "3.2.0"
   
   # frontend/package.json
   "version": "3.2.0"
   ```

2. **更新 CHANGELOG.md**
   记录本次发布的所有变更。

3. **创建发布分支**
   ```bash
   git checkout -b release/v3.2.0
   ```

4. **运行完整测试**
   ```bash
   # 后端
   cd backend && pytest
   
   # 前端
   cd frontend && npm run test
   ```

5. **构建生产版本**
   ```bash
   cd frontend && npm run build
   ```

6. **创建 Git Tag**
   ```bash
   git tag -a v3.2.0 -m "Release v3.2.0"
   git push origin v3.2.0
   ```

7. **发布到 GitHub Releases**
   在 GitHub 上创建 Release，附上 CHANGELOG。

## 获取帮助

如有问题，可以通过以下方式获取帮助:

- 查看 [开发指南](development-guide.md)
- 查看 [故障排查手册](troubleshooting-guide.md)
- 提交 Issue 描述问题
- 在 PR 中 @维护者

## 行为准则

- 尊重他人，友善交流
- 建设性反馈，避免人身攻击
- 欢迎新手，耐心解答
- 遵守开源协议

感谢你的贡献！🎉
