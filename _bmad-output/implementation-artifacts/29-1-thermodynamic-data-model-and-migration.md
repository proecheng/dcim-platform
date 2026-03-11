# Story 29.1: 热动力学数据模型与数据库迁移

Status: ready-for-dev

## Story

As a 系统管理员,
I want 系统建立制冷区域热参数和温度预测的数据存储基础,
So that 后续的热模型计算和预测记录有持久化支撑。

## Acceptance Criteria

1. Given 架构文档 Section 21 定义的数据模型扩展
   When 执行数据库迁移
   Then `thermal_parameters` 表创建成功，包含以下字段（所有字段必须添加 comment）：
   - id (Integer, 主键, autoincrement)
   - cooling_zone_id (Integer, FK → cooling_zones.id, nullable=False, ondelete='CASCADE')
   - thermal_R (Float, °C/kW, nullable=True, comment="热阻标定值")
   - thermal_C (Float, kWh/°C, nullable=True, comment="热容标定值（总热容，非单位面积）")
   - fitting_r_squared (Float, nullable=True, comment="拟合 R² 值")
   - fitting_method (String(20), nullable=True, default='manual', comment="标定方法: auto_fit/manual/default")
   - sample_count (Integer, nullable=True, comment="样本数")
   - calibrated_at (DateTime, nullable=True, comment="标定时间")
   - is_active (Boolean, default=True, comment="是否为当前生效参数")
   - is_demo (Boolean, default=False, comment="是否为 demo 数据")
   - created_at (DateTime, default=datetime.now, comment="创建时间")
   - updated_at (DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
   - 索引: ix_thermal_params_zone_active (cooling_zone_id, is_active) BTREE
   - 唯一约束: uq_thermal_params_zone_active UNIQUE(cooling_zone_id, is_active) WHERE is_active=True（确保每个 zone 只有一个活跃版本）

2. And `temperature_prediction_logs` 表创建成功，包含以下字段（所有字段必须添加 comment）：
   - id (Integer, 主键, autoincrement)
   - cooling_zone_id (Integer, FK → cooling_zones.id, nullable=False, ondelete='CASCADE')
   - predicted_temp (Float, °C, nullable=False, comment="预测温度")
   - actual_temp (Float, °C, nullable=True, comment="实际温度")
   - prediction_horizon_min (Integer, 分钟, nullable=False, comment="预测时长")
   - deviation (Float, °C, nullable=True, comment="偏差 = actual - predicted")
   - model_version (String(50), nullable=False, comment="模型参数版本")
   - created_at (DateTime, default=datetime.now, nullable=False, comment="记录时间")
   - 索引: ix_temp_pred_zone_time (cooling_zone_id ASC, created_at DESC) BTREE — 时序查询优化
   - TimescaleDB: 仅在 PostgreSQL 环境下转换为 hypertable，分区键 created_at，chunk_time_interval='7 days'（SQLite 环境跳过）

3. And **`cooling_zones` 表处理**（位于 `models/topology_config.py`）：
   - 如果表不存在，创建 `cooling_zones` 表，包含基础字段：
     - id (Integer, 主键)
     - zone_code (String(50), unique, nullable=False)
     - zone_name (String(100), nullable=False)
     - room_id (Integer, FK → rooms.id, nullable=True, ondelete='SET NULL')
     - site_id (Integer, FK → sites.id, nullable=True, ondelete='SET NULL', comment="所属站点")
     - design_capacity_kw (Float, nullable=True)
     - description (Text, nullable=True)
     - created_at, updated_at (DateTime)
   - 添加/扩展字段（所有字段必须添加 comment）：
     - area_m2 (Float, nullable=True, comment="冷通道面积 m²，用于计算热容")
     - height_m (Float, default=3.0, comment="冷通道层高 m")
     - thermal_R (Float, nullable=True, comment="热阻标定值 °C/kW，NULL=未标定")
     - thermal_C (Float, nullable=True, comment="热容标定值 kWh/°C（总热容），NULL=未标定")
     - bypass_beta (Float, default=0.1, comment="气流短路系数 0~0.3，应用层验证范围")
     - r_calibrated_at (DateTime, nullable=True, comment="R/C 最近标定时间")

4. And **`cooling_linkage_configs` 表处理**（位于 `models/load_shift.py`）：
   - 如果表不存在，创建 `cooling_linkage_configs` 表，包含基础字段：
     - id (Integer, 主键)
     - cooling_zone_id (Integer, FK → cooling_zones.id, nullable=False, ondelete='CASCADE', comment="关联制冷区域")
     - enabled (Boolean, default=True)
     - created_at, updated_at (DateTime)
   - 添加/扩展字段（所有字段必须添加 comment）：
     - precool_target_temp (Float, nullable=True, comment="预冷目标温度 °C")
     - precool_enabled (Boolean, default=False, comment="是否启用预冷功能")

5. And **Alembic 迁移脚本要求**（P1-20 修复）：
   - 迁移文件命名：`20260311_0000_story_29_1_thermal_data_model.py`（使用日期前缀）
   - revision ID: 自动生成，down_revision: 当前 HEAD（通过 `alembic current` 获取）
   - 使用 `sqlalchemy.inspect(bind)` 检查表和列是否存在（统一方法）
   - 数据库类型检测：使用 `bind.dialect.name` 判断是 'postgresql' 还是 'sqlite'
   - 所有迁移必须实现完整的 `downgrade()` 回滚逻辑
   - 回滚脚本必须通过测试：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
   - 迁移脚本必须包含数据清理逻辑：upgrade() 中删除孤立的 cooling_zone_id 引用（如果有）
   - 回滚时需正确处理外键约束和索引（先删除子表/索引，再删除父表/列）
   - downgrade() 中添加警告注释："WARNING: 回滚将丢失 thermal_parameters 和 temperature_prediction_logs 数据"
   - TimescaleDB hypertable 创建：仅在 PostgreSQL 环境下执行 `SELECT create_hypertable('temperature_prediction_logs', 'created_at', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)`
   - TimescaleDB hypertable 回滚：仅在 PostgreSQL 环境下执行 `SELECT drop_chunks('temperature_prediction_logs', older_than => INTERVAL '0 seconds'); DROP TABLE IF EXISTS temperature_prediction_logs CASCADE`（先清理 chunks，再删除表）

6. And demo 种子数据为现有制冷区域生成默认热参数，标记 is_demo=True：
   - 热参数默认值：R=0.03°C/kW, C=总热容（计算方式见下）, β=0.1, fitting_method='default'
   - C 计算逻辑：
     - 如果 zone.area_m2 存在且 > 0：C = 0.04 kWh/°C/m² × area_m2（总热容）
     - 如果 zone.area_m2 为 NULL 或 ≤ 0：C = 50.0 kWh/°C（假设典型 1250m² 机房，即 0.04 × 1250）
   - 去重逻辑：种子脚本执行前检查 `ThermalParameter.filter_by(cooling_zone_id=zone.id, is_demo=True).first()`，如果已存在则跳过
   - 参照架构典型值范围：R=0.01-0.05, C=0.03-0.06 kWh/°C/m²

## Tasks / Subtasks

- [ ] 创建 ThermalParameter 和 TemperaturePredictionLog 模型 (AC: #1, #2)
  - [ ] 新建 `backend/app/models/thermal.py`
  - [ ] 定义 ThermalParameter 模型（12个字段，包含 id, is_demo, created_at, updated_at）
  - [ ] 定义 TemperaturePredictionLog 模型（8个字段，包含 id）
  - [ ] 添加复合索引：ThermalParameter.ix_thermal_params_zone_active (BTREE)
  - [ ] 添加唯一约束：ThermalParameter.uq_thermal_params_zone_active (部分唯一索引)
  - [ ] 添加复合索引：TemperaturePredictionLog.ix_temp_pred_zone_time (BTREE, created_at DESC)
  - [ ] 在 `models/__init__.py` 中导入新模型

- [ ] 扩展 CoolingZone 模型 (AC: #3)
  - [ ] 修改 `backend/app/models/topology_config.py`
  - [ ] 添加 site_id 外键（如果不存在），ondelete='SET NULL'
  - [ ] 添加 room_id ondelete='SET NULL'（如果缺失）
  - [ ] 添加 area_m2, height_m, thermal_R, thermal_C, bypass_beta, r_calibrated_at 字段
  - [ ] 确保字段默认值和约束正确（height_m=3.0, bypass_beta=0.1）
  - [ ] 所有新字段添加 comment

- [ ] 扩展 CoolingLinkageConfig 模型 (AC: #4)
  - [ ] 修改 `backend/app/models/load_shift.py`
  - [ ] 修改 cooling_zone_id 为 nullable=False, ondelete='CASCADE'（如果当前为 nullable=True）
  - [ ] 添加 precool_target_temp, precool_enabled 字段
  - [ ] 所有新字段添加 comment

- [ ] 创建 Alembic 迁移脚本 (AC: #5)
  - [ ] 获取当前 HEAD：`cd backend && alembic current`
  - [ ] 手动创建迁移文件：`backend/alembic/versions/20260311_0000_story_29_1_thermal_data_model.py`
  - [ ] 设置 revision ID（自动生成）和 down_revision（当前 HEAD）
  - [ ] 实现完整的 upgrade() 逻辑：
    - [ ] 使用 `sqlalchemy.inspect(bind)` 检查表和列是否存在
    - [ ] 使用 `bind.dialect.name` 检测数据库类型
    - [ ] 清理孤立数据（如果 cooling_zones 表已存在）
    - [ ] 创建/扩展表和字段
    - [ ] 创建索引和唯一约束
    - [ ] 仅在 PostgreSQL 环境下执行 TimescaleDB hypertable 转换
  - [ ] 实现完整的 downgrade() 回滚逻辑：
    - [ ] 添加警告注释
    - [ ] 先删除索引和唯一约束
    - [ ] 仅在 PostgreSQL 环境下处理 TimescaleDB hypertable 删除
    - [ ] 先删除子表（thermal_parameters, temperature_prediction_logs）
    - [ ] 再删除父表新增列（cooling_zones, cooling_linkage_configs）

- [ ] 更新 demo 种子数据 (AC: #6)
  - [ ] 修改 `backend/app/demo/seeds/cooling_seed.py`
  - [ ] 为现有 CoolingZone 生成默认热参数
  - [ ] 实现 C 计算逻辑（基于 area_m2，处理 NULL 和 ≤0 情况）
  - [ ] 设置 fitting_method='default'
  - [ ] 实现去重逻辑（检查 is_demo=True 是否已存在）
  - [ ] 标记 is_demo=True

- [ ] 测试迁移脚本 (AC: #5)
  - [ ] 测试 upgrade: `alembic upgrade head`
  - [ ] 验证表结构和索引创建成功
  - [ ] 验证唯一约束创建成功
  - [ ] 验证 TimescaleDB hypertable 创建成功（仅 PostgreSQL）
  - [ ] 测试 downgrade: `alembic downgrade -1`
  - [ ] 验证表和列删除成功
  - [ ] 测试重新 upgrade: `alembic upgrade head`
  - [ ] 验证数据完整性（外键约束、demo 数据）
  - [ ] 性能测试（仅 PostgreSQL + TimescaleDB）：插入 10000 条 temperature_prediction_logs，查询最近 24 小时数据（< 100ms）
  - [ ] 性能测试（SQLite）：插入 1000 条 temperature_prediction_logs，查询最近 24 小时数据（< 500ms）

## Dev Notes

### 架构约束

**数据模型设计** [Source: architecture.md#21.3]:
- ThermalParameter 表记录 R/C 参数标定历史，支持多版本管理
- TemperaturePredictionLog 表采用单条记录模式（非 JSON 批量），便于 TimescaleDB 时序查询
- CoolingZone 扩展字段支持热模型计算：area_m2 × height_m 计算体积，thermal_R/C 为标定参数
- bypass_beta 气流短路系数范围 0~0.3，典型值 0.1

**迁移脚本规范** [Source: epics.md#Story 29.1 AC#5]:
- 必须实现完整 downgrade() 回滚逻辑（P1-20 修复要求）
- 使用 `op.get_bind().execute()` 检查表是否存在
- 外键约束删除顺序：先删除子表，再删除父表
- 索引删除顺序：先删除索引，再删除列

**Demo 数据规范** [Source: architecture.md#21.3, epics.md#Story 28.2]:
- 所有 demo 数据必须标记 `is_demo=True`
- 热参数默认值：R=0.03°C/kW, C=总热容（非单位面积）, β=0.1
- C 计算：如果 area_m2 存在，C = 0.04 × area_m2；否则 C = 50.0（假设 1250m² 机房）
- 参照架构典型值范围：R=0.01-0.05, C=0.03-0.06 kWh/°C/m²
- 去重逻辑：检查 is_demo=True 是否已存在，避免重复创建

### 现有代码模式

**模型定义模式** [Source: models/topology_config.py, models/load_shift.py]:
```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from ..core.database import Base

class ModelName(Base):
    __tablename__ = "table_name"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 字段定义
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

**Alembic 迁移模式** [Source: alembic/versions/*.py]:
```python
from sqlalchemy import inspect

def upgrade() -> None:
    # 检查表是否存在（统一使用 inspect 方法）
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'table_name' not in inspector.get_table_names():
        op.create_table('table_name', ...)
    else:
        # 检查列是否存在
        existing_columns = [col['name'] for col in inspector.get_columns('table_name')]
        if 'new_column' not in existing_columns:
            op.add_column('table_name', sa.Column(...))

    # 清理孤立数据（如果需要）
    bind.execute(sa.text("DELETE FROM child_table WHERE parent_id NOT IN (SELECT id FROM parent_table)"))

    # TimescaleDB hypertable 创建
    bind.execute(sa.text("SELECT create_hypertable('table_name', 'created_at', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"))

def downgrade() -> None:
    # WARNING: 回滚将丢失数据
    # 先删除索引
    op.drop_index('idx_name', table_name='table_name')
    # 先删除子表
    op.drop_table('child_table')
    # 再删除父表列
    op.drop_column('parent_table', 'column_name')
```

**Demo 种子数据模式** [Source: demo/seeds/cooling_seed.py]:
```python
def seed_cooling_data(session):
    # 查询现有数据
    zones = session.query(CoolingZone).all()

    for zone in zones:
        # 去重检查
        existing = session.query(ThermalParameter).filter_by(
            cooling_zone_id=zone.id,
            is_demo=True
        ).first()
        if existing:
            continue  # 跳过已存在的 demo 数据

        # 计算总热容 C
        if zone.area_m2:
            thermal_C = 0.04 * zone.area_m2  # kWh/°C
        else:
            thermal_C = 50.0  # 假设 1250m² 机房

        # 创建 demo 数据
        param = ThermalParameter(
            cooling_zone_id=zone.id,
            thermal_R=0.03,
            thermal_C=thermal_C,
            is_demo=True
        )
        session.add(param)
```

### 文件结构

**新建文件**:
- `backend/app/models/thermal.py` — ThermalParameter, TemperaturePredictionLog 模型

**修改文件**:
- `backend/app/models/topology_config.py` — CoolingZone 扩展字段（6个新字段）
- `backend/app/models/load_shift.py` — CoolingLinkageConfig 扩展字段（2个新字段）
- `backend/app/models/__init__.py` — 导入新模型
- `backend/app/demo/seeds/cooling_seed.py` — 热参数种子数据（含去重逻辑）
- `backend/alembic/versions/20260311_0000_story_29_1_thermal_data_model.py` — 迁移脚本

### 测试要求

**迁移测试**:
```bash
# 1. 升级测试
cd backend
alembic upgrade head

# 2. 验证表结构
.venv/Scripts/python.exe -c "from app.core.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); print(inspector.get_columns('thermal_parameters'))"

# 3. 验证索引
.venv/Scripts/python.exe -c "from app.core.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); print(inspector.get_indexes('thermal_parameters'))"

# 4. 验证唯一约束
.venv/Scripts/python.exe -c "from app.core.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); print(inspector.get_unique_constraints('thermal_parameters'))"

# 5. 验证 TimescaleDB hypertable（仅 PostgreSQL）
.venv/Scripts/python.exe -c "from app.core.database import engine; from sqlalchemy import text; result = engine.execute(text('SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = \\'temperature_prediction_logs\\'')); print(list(result))"

# 6. 回滚测试
alembic downgrade -1

# 6. 重新升级测试
alembic upgrade head
```

**数据完整性测试**:
```python
# 验证外键约束
from app.models.thermal import ThermalParameter
from app.models.topology_config import CoolingZone

# 验证 demo 数据
zones = session.query(CoolingZone).all()
for zone in zones:
    params = session.query(ThermalParameter).filter_by(cooling_zone_id=zone.id, is_demo=True).all()
    assert len(params) > 0, f"Zone {zone.id} missing demo thermal parameters"
```

### 关键技术细节

**SQLAlchemy 字段类型映射**:
- Float → REAL (SQLite) / FLOAT (PostgreSQL)
- DateTime → TIMESTAMP
- Boolean → INTEGER (SQLite) / BOOLEAN (PostgreSQL)

**Alembic 表存在性检查**:
```python
from sqlalchemy import inspect

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'thermal_parameters' not in inspector.get_table_names():
        op.create_table('thermal_parameters', ...)
    else:
        # 表已存在，仅添加缺失列
        existing_columns = [col['name'] for col in inspector.get_columns('thermal_parameters')]
        if 'new_column' not in existing_columns:
            op.add_column('thermal_parameters', sa.Column('new_column', ...))
```

**外键约束处理**:
```python
# 创建时：先创建父表，再创建子表
op.create_table('cooling_zones', ...)
op.create_table('thermal_parameters',
    sa.Column('cooling_zone_id', sa.Integer, sa.ForeignKey('cooling_zones.id')),
    ...
)

# 删除时：先删除子表，再删除父表
op.drop_table('thermal_parameters')
op.drop_table('cooling_zones')
```

### 潜在风险

1. **表已存在冲突**: 如果 `cooling_zones` 或 `cooling_linkage_configs` 表已存在，需要使用 `op.add_column()` 而非 `op.create_table()`
   - **缓解**: 使用 inspector 检查表和列是否存在

2. **外键约束冲突**: 如果现有数据中存在孤立的 cooling_zone_id，外键约束会失败
   - **缓解**: 迁移前清理孤立数据

3. **回滚数据丢失**: downgrade() 删除列时会丢失数据
   - **缓解**: 在 downgrade() 中添加警告注释，生产环境谨慎回滚

4. **Demo 数据重复**: 多次运行种子脚本可能创建重复数据
   - **缓解**: 种子脚本中添加去重逻辑（检查 is_demo=True 是否已存在）

### References

- [Source: architecture.md#21.3] 数据模型扩展定义
- [Source: epics.md#Story 29.1] 完整 AC 和涉及文件
- [Source: models/topology_config.py] CoolingZone 现有模型
- [Source: models/load_shift.py] CoolingLinkageConfig 现有模型
- [Source: alembic/versions/1e866a5d60a6_update_phase_2_models.py] 迁移脚本参考

## Dev Agent Record

### Agent Model Used

(待填写)

### Debug Log References

(待填写)

### Completion Notes List

(待填写)

### File List

(待填写)
