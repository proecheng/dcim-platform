# 第一轮对抗性审查修复清单 - Story 28.2

## 修复的问题

### 1. AC-2 增加默认用户创建
**问题:** 最小化种子没有创建默认管理员用户，无法登录
**修复:** 在 AC-2 中增加"默认管理员用户: username=admin, password=admin123（首次启动时创建）"

### 2. AC-5 明确"真实设备 + 模拟数据"场景
**问题:** `DEMO_ENABLED=false, SIMULATION_ENABLED=true` 场景未定义清楚
**修复:** 明确"模拟器查询数据库中所有点位（包括真实点位），为其生成模拟数据。如果数据库中没有任何点位，模拟器记录警告日志但不报错"

### 3. AC-7 重构错误处理策略
**问题:** "前一阶段失败不影响后续阶段"可能导致不一致状态
**修复:** 定义明确的错误处理策略：
- Seed 失败 → 跳过 Demo，继续 Simulation
- Demo 失败 → 继续 Simulation
- Simulation 失败 → 不影响应用启动

### 4. AC-2 改进幂等性实现
**问题:** 修改配置后重新运行种子会创建额外数据
**修复:**
- 使用唯一标识（`code="DEFAULT"`）检测已存在
- 机房命名改为 `ROOM_001` 格式（支持超过 26 个）
- 种子执行使用事务，失败时回滚

### 5. 新增 AC-8: 数据库迁移
**问题:** `data_source` 字段未在数据库模型中定义
**修复:** 明确需要数据库迁移，为 Site/Floor/Room/PricingScheme/Device/Point 添加 `data_source` 字段（nullable=True）

### 6. 电价配置改为五级制
**问题:** 原设计为三级制（峰/平/谷），不符合中国电价标准
**修复:** 改为五级制（尖峰/峰/平/谷/深谷），增加对应配置项

### 7. AC-2 明确告警级别存储方式
**问题:** 告警级别配置实现被注释，未说明存储方式
**修复:** 明确"告警级别硬编码在代码中，不存储到数据库"

### 8. AC-1 修改 `SEED_ENABLED` 默认值
**问题:** 默认值为 `true` 可能在已有数据环境中导致冲突
**修复:** 改为默认 `false`，在文档中说明"首次部署时设置为 true"

### 9. AC-2 增加事务回滚机制
**问题:** 种子执行到一半失败没有回滚
**修复:** 明确"种子执行使用事务，失败时回滚所有更改"

### 10. AC-3 明确空状态引导
**问题:** "引导用户"未定义具体形式
**修复:** 明确使用 EmptyState 组件，包含"添加设备"和"接入网关"按钮

### 11. AC-1 增加配置验证
**问题:** `DEFAULT_FLOOR_COUNT` 和 `DEFAULT_ROOM_COUNT` 无边界值验证
**修复:** 明确范围为 1-10，在配置类中使用 Pydantic 验证

### 12. AC-2 修复机房命名逻辑
**问题:** `chr(64 + room_num)` 超过 26 会失败
**修复:** 改为 `ROOM_001` 格式，支持任意数量机房

### 13. 测试策略增加性能测试（待补充）
**问题:** 缺少大规模配置下的性能测试
**修复:** 在测试策略中增加性能测试项

### 14. AC-9 增加配置迁移指南（待补充）
**问题:** 向后兼容性缓解措施不足
**修复:** 在 `.env.example` 和 `CLAUDE.md` 中提供详细的配置迁移指南

---

## 修订后的关键 AC

### AC-2: 最小化种子实现（修订版）
- **Given** `SEED_ENABLED=true, DEMO_ENABLED=false, SIMULATION_ENABLED=false`
- **When** 系统启动
- **Then** 执行 `minimal_seed.py`，创建以下最小配置：
  - **默认管理员用户:** username=admin, password=admin123（首次启动时创建）
  - **默认站点:** 站点名称可通过 `DEFAULT_SITE_NAME` 配置（默认"默认站点"）
  - **基础空间结构:** 1 个 Floor（"1F"）+ 1 个 Room（"机房A"），数量可通过 `DEFAULT_FLOOR_COUNT`（1-10）和 `DEFAULT_ROOM_COUNT`（1-10）配置
  - **默认电价配置:** 五级分时电价模板（尖峰/峰/平/谷/深谷，价格和时段可配置，默认为中国典型分时电价）
  - **默认告警级别配置:** critical/major/minor/info 四级（硬编码在代码中，不存储到数据库）
  - **不创建设备和点位**
- **And** 种子数据标记为 `data_source='seed'`（需要数据库迁移添加此字段）
- **And** 种子执行幂等（重复执行不报错，检测到已存在则跳过）
- **And** 种子执行使用事务，失败时回滚所有更改
- **And** 机房命名使用 `ROOM_001` 格式（支持超过 26 个机房）

### AC-8: 数据库迁移（新增）
- **Given** 需要为多个模型添加 `data_source` 字段
- **When** 执行数据库迁移
- **Then** 以下模型添加 `data_source` 字段（nullable=True, default=None）：
  - Site
  - Floor
  - Room
  - PricingScheme
  - Device（为 Story 28.1 预留）
  - Point（为 Story 28.1 预留）
- **And** 迁移脚本向后兼容，现有数据的 `data_source` 字段为 NULL

---

## 修订后的配置设计

### backend/app/core/config.py（修订版）
```python
class Settings(BaseSettings):
    # === 数据初始化配置 ===
    seed_enabled: bool = Field(default=False, env="SEED_ENABLED")  # 改为 false
    demo_enabled: bool = Field(default=False, env="DEMO_ENABLED")
    simulation_enabled: bool = Field(default=False, env="SIMULATION_ENABLED")

    # === Seed 配置 ===
    default_site_name: str = Field(default="默认站点", env="DEFAULT_SITE_NAME")
    default_floor_count: int = Field(default=1, ge=1, le=10, env="DEFAULT_FLOOR_COUNT")  # 增加验证
    default_room_count: int = Field(default=1, ge=1, le=10, env="DEFAULT_ROOM_COUNT")    # 增加验证

    # === 电价配置（五级制）===
    default_sharp_peak_price: float = Field(default=1.5, env="DEFAULT_SHARP_PEAK_PRICE")  # 尖峰
    default_peak_price: float = Field(default=1.2, env="DEFAULT_PEAK_PRICE")              # 峰
    default_flat_price: float = Field(default=0.8, env="DEFAULT_FLAT_PRICE")              # 平
    default_valley_price: float = Field(default=0.4, env="DEFAULT_VALLEY_PRICE")          # 谷
    default_deep_valley_price: float = Field(default=0.2, env="DEFAULT_DEEP_VALLEY_PRICE") # 深谷
```

### .env.example（修订版）
```env
# === 数据初始化配置 ===
# SEED_ENABLED: 启用最小化种子（站点、机房、电价、告警级别、默认用户）
#   - 默认 false，避免在已有数据的环境中意外创建
#   - 首次部署时设置为 true
# DEMO_ENABLED: 启用 Demo 数据（设备、点位、历史数据）
#   - 仅用于演示和测试环境
# SIMULATION_ENABLED: 启用数据模拟器（为点位生成模拟数据）
#   - 可独立于 DEMO_ENABLED 使用（为真实点位生成模拟数据）
SEED_ENABLED=false
DEMO_ENABLED=false
SIMULATION_ENABLED=false

# === Seed 配置 ===
DEFAULT_SITE_NAME=默认站点
DEFAULT_FLOOR_COUNT=1    # 范围: 1-10
DEFAULT_ROOM_COUNT=1     # 范围: 1-10

# === 电价配置（中国五级分时电价）===
DEFAULT_SHARP_PEAK_PRICE=1.5  # 尖峰（10:00-12:00, 18:00-21:00）
DEFAULT_PEAK_PRICE=1.2         # 峰（8:00-10:00, 14:00-18:00）
DEFAULT_FLAT_PRICE=0.8         # 平（7:00-8:00, 12:00-14:00, 21:00-23:00）
DEFAULT_VALLEY_PRICE=0.4       # 谷（23:00-24:00, 6:00-7:00）
DEFAULT_DEEP_VALLEY_PRICE=0.2  # 深谷（0:00-6:00）
```

---

## 修订后的种子实现关键代码

### 创建默认用户（新增）
```python
async def _create_default_admin_user(session: AsyncSession):
    """创建默认管理员用户（幂等）"""
    from app.models import User
    from app.core.security import get_password_hash

    result = await session.execute(
        select(User).where(User.username == "admin")
    )
    user = result.scalar_one_or_none()

    if user:
        logger.info("默认管理员用户已存在")
        return

    user = User(
        username="admin",
        hashed_password=get_password_hash("admin123"),
        role="admin",
        is_active=True
    )
    session.add(user)
    logger.info("创建默认管理员用户: admin")
```

### 创建五级电价配置（修订版）
```python
async def _create_default_pricing(session: AsyncSession):
    """创建默认五级电价配置（幂等）"""
    result = await session.execute(
        select(PricingScheme).where(PricingScheme.name == "默认五级分时电价")
    )
    pricing = result.scalar_one_or_none()

    if pricing:
        logger.info("默认电价配置已存在")
        return

    pricing = PricingScheme(
        name="默认五级分时电价",
        scheme_type="time_of_use",
        data={
            "sharp_peak": {
                "price": settings.default_sharp_peak_price,
                "hours": [10, 11, 18, 19, 20]
            },
            "peak": {
                "price": settings.default_peak_price,
                "hours": [8, 9, 14, 15, 16, 17]
            },
            "flat": {
                "price": settings.default_flat_price,
                "hours": [7, 12, 13, 21, 22]
            },
            "valley": {
                "price": settings.default_valley_price,
                "hours": [6, 23]
            },
            "deep_valley": {
                "price": settings.default_deep_valley_price,
                "hours": [0, 1, 2, 3, 4, 5]
            }
        },
        data_source="seed"
    )
    session.add(pricing)
    logger.info("创建默认五级电价配置")
```

### 机房命名修复（修订版）
```python
async def _create_default_floors_and_rooms(session: AsyncSession, site_id: int):
    """创建基础空间结构（幂等）"""
    for floor_num in range(1, settings.default_floor_count + 1):
        # ... 楼层创建逻辑 ...

        # 创建机房（使用 ROOM_001 格式）
        for room_num in range(1, settings.default_room_count + 1):
            room_code = f"ROOM_{room_num:03d}"  # 修复：使用 001, 002, ... 格式
            result = await session.execute(
                select(Room).where(
                    Room.site_id == site_id,
                    Room.floor_id == floor.id,
                    Room.code == room_code
                )
            )
            room = result.scalar_one_or_none()

            if not room:
                room = Room(
                    site_id=site_id,
                    floor_id=floor.id,
                    name=f"机房{room_num:03d}",
                    code=room_code,
                    data_source="seed"
                )
                session.add(room)
                logger.info(f"创建机房: {room.name}")
```

---

## 需要的数据库迁移

### Alembic 迁移脚本
```python
"""add data_source field to models

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 为多个表添加 data_source 字段
    op.add_column('sites', sa.Column('data_source', sa.String(20), nullable=True))
    op.add_column('floors', sa.Column('data_source', sa.String(20), nullable=True))
    op.add_column('rooms', sa.Column('data_source', sa.String(20), nullable=True))
    op.add_column('pricing_schemes', sa.Column('data_source', sa.String(20), nullable=True))
    op.add_column('devices', sa.Column('data_source', sa.String(20), nullable=True))
    op.add_column('points', sa.Column('data_source', sa.String(20), nullable=True))

def downgrade():
    op.drop_column('points', 'data_source')
    op.drop_column('devices', 'data_source')
    op.drop_column('pricing_schemes', 'data_source')
    op.drop_column('rooms', 'data_source')
    op.drop_column('floors', 'data_source')
    op.drop_column('sites', 'data_source')
```

---

**修复完成时间:** 2026-03-05
**修复工具:** BMAD Method v6.0.4 - Adversarial Review Round 1
**Co-Authored-By:** Claude Opus 4.6 <noreply@anthropic.com>
