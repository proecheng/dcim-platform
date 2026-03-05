# 第二轮对抗性审查修复清单 - Story 28.2

## 修复的问题

### 1. 电价时段验证
**问题:** 五级电价时段总和需要等于24小时且无重叠
**修复:**
- 尖峰: [10, 11, 18, 19, 20] = 5小时
- 峰: [8, 9, 14, 15, 16, 17] = 6小时
- 平: [7, 12, 13, 21, 22] = 5小时
- 谷: [6, 23] = 2小时
- 深谷: [0, 1, 2, 3, 4, 5] = 6小时
- **总计: 24小时，无重叠 ✓**

### 2. 默认用户密码安全性
**问题:** `admin/admin123` 硬编码存在安全风险
**修复:**
- 增加环境变量 `DEFAULT_ADMIN_PASSWORD`（默认 admin123）
- 在文档中增加安全警告："生产环境部署后应立即修改默认密码"
- 首次登录后强制修改密码（可选，标记为 TODO）

### 3. AC-4 和 AC-7 依赖关系统一
**问题:** 两个 AC 对 seed 失败后的行为描述不一致
**修复:** 统一为"如果 seed 阶段失败，demo 阶段不执行（记录错误并跳过）"

### 4. `data_source` 字段长度
**问题:** `sa.String(20)` 可能不够用
**修复:** 改为 `sa.String(50)`，足够容纳未来扩展

### 5. 首次启动检测
**问题:** 幂等性检测不完整
**修复:** 增加"首次启动检测"逻辑：
- 检查数据库是否为空（Site 表记录数为 0）
- 如果为空，执行完整种子
- 如果不为空，执行幂等检查

### 6. 事务回滚策略
**问题:** 全局事务回滚可能导致部分失败
**修复:** 改为分阶段提交：
- 用户创建独立事务
- 站点/机房/电价使用同一事务
- 每个阶段失败不影响已提交的阶段

### 7. 配置验证范围放宽
**问题:** 1-10 限制过于严格
**修复:**
- `DEFAULT_FLOOR_COUNT`: 1-50
- `DEFAULT_ROOM_COUNT`: 1-100
- 在文档中说明"大规模配置可能影响启动性能"

### 8. EmptyState 组件说明
**问题:** 组件未定义
**修复:** 在 AC-3 中明确：
- 使用 Element Plus 的 `el-empty` 组件
- 自定义描述文案和操作按钮
- 示例代码在技术设计中提供

### 9. 电价时段可配置
**问题:** 时段硬编码不灵活
**修复:**
- 保持默认时段硬编码（简化配置）
- 在文档中说明"时段基于中国典型分时电价，如需调整请修改 `minimal_seed.py`"
- 标记为未来改进项（通过配置文件或数据库配置时段）

### 10. 模拟器警告日志明确
**问题:** 警告内容和格式不明确
**修复:** 明确警告格式：
```
WARNING: Simulator started but no points found in database.
Simulator will idle until points are created.
To add points: 1) Enable DEMO_ENABLED=true, or 2) Add devices via /collection/device-manage
```

### 11. 种子数据清理工具
**问题:** 缺少清理工具
**修复:** 新增 `backend/app/seeds/clean_seed.py`：
- 删除所有 `data_source='seed'` 的记录
- 删除默认管理员用户
- 提供 CLI 命令：`python -m app.seeds.clean_seed`

### 12. `data_source` 字段索引
**问题:** 缺少索引影响查询性能
**修复:** 在迁移脚本中为 `data_source` 字段创建索引

---

## 最终修订的关键配置

### backend/app/core/config.py（最终版）
```python
class Settings(BaseSettings):
    # === 数据初始化配置 ===
    seed_enabled: bool = Field(default=False, env="SEED_ENABLED")
    demo_enabled: bool = Field(default=False, env="DEMO_ENABLED")
    simulation_enabled: bool = Field(default=False, env="SIMULATION_ENABLED")

    # === Seed 配置 ===
    default_site_name: str = Field(default="默认站点", env="DEFAULT_SITE_NAME")
    default_floor_count: int = Field(default=1, ge=1, le=50, env="DEFAULT_FLOOR_COUNT")
    default_room_count: int = Field(default=1, ge=1, le=100, env="DEFAULT_ROOM_COUNT")
    default_admin_password: str = Field(default="admin123", env="DEFAULT_ADMIN_PASSWORD")

    # === 电价配置（五级制）===
    default_sharp_peak_price: float = Field(default=1.5, env="DEFAULT_SHARP_PEAK_PRICE")
    default_peak_price: float = Field(default=1.2, env="DEFAULT_PEAK_PRICE")
    default_flat_price: float = Field(default=0.8, env="DEFAULT_FLAT_PRICE")
    default_valley_price: float = Field(default=0.4, env="DEFAULT_VALLEY_PRICE")
    default_deep_valley_price: float = Field(default=0.2, env="DEFAULT_DEEP_VALLEY_PRICE")
```

### 数据库迁移（最终版）
```python
def upgrade():
    # 为多个表添加 data_source 字段（长度 50，带索引）
    for table in ['sites', 'floors', 'rooms', 'pricing_schemes', 'devices', 'points']:
        op.add_column(table, sa.Column('data_source', sa.String(50), nullable=True))
        op.create_index(f'ix_{table}_data_source', table, ['data_source'])
```

### 种子清理工具（新增）
```python
# backend/app/seeds/clean_seed.py
"""清理种子数据工具"""
import asyncio
from sqlalchemy import delete
from app.core.database import async_session
from app.models import Site, Floor, Room, PricingScheme, User

async def clean_seed_data():
    """删除所有种子数据"""
    async with async_session() as session:
        # 删除种子数据
        await session.execute(delete(Room).where(Room.data_source == 'seed'))
        await session.execute(delete(Floor).where(Floor.data_source == 'seed'))
        await session.execute(delete(Site).where(Site.data_source == 'seed'))
        await session.execute(delete(PricingScheme).where(PricingScheme.data_source == 'seed'))

        # 删除默认管理员
        await session.execute(delete(User).where(User.username == 'admin'))

        await session.commit()
        print("✓ 种子数据清理完成")

if __name__ == "__main__":
    asyncio.run(clean_seed_data())
```

---

**修复完成时间:** 2026-03-05
**修复工具:** BMAD Method v6.0.4 - Adversarial Review Round 2
**Co-Authored-By:** Claude Opus 4.6 <noreply@anthropic.com>
