# Story 16-1: 站点管理

## 概述

增强现有站点管理功能，补充联系人、网络配置字段，强化 site_id 行级数据隔离（Gateway/DataSource 加 FK 约束），并实现 EMQX ACL 按 site_id 隔离 Topic 权限。

## 现状分析

### 已有基础设施（Story 13-5）
- **Site 模型**: `backend/app/models/spatial.py` — `sites` 表，含 site_code, site_name, address, description
- **Site CRUD API**: `backend/app/api/v1/spatial.py` — GET/POST/PUT/DELETE `/v1/spatial/sites`
- **Site Schema**: `backend/app/schemas/spatial.py` — SiteCreate, SiteUpdate, SiteResponse
- **UserSite 关联**: `backend/app/models/user.py` — 用户-站点权限关联表
- **get_user_site_ids**: `backend/app/api/deps.py` — admin 不过滤，其他角色按 UserSite 过滤
- **Device.site_id**: FK 到 sites.id
- **Floor.site_id**: FK 到 sites.id
- **Gateway.site_id**: `default=1`，无 FK 约束
- **DataSource.site_id**: `default=1`，无 FK 约束
- **MQTT Topic**: `dcim/{site_id}/gw/{gw_id}/...` 已在 client.py 中解析

### 需要补充
1. Site 模型增加 `contact_person`, `contact_phone`, `contact_email`, `network_config` 字段
2. Gateway.site_id 和 DataSource.site_id 加 ForeignKey 约束
3. 更多业务表的 site_id 过滤（告警、工单等关键查询）
4. EMQX ACL 配置服务 — 按 site_id 隔离 MQTT Topic 权限
5. 站点删除前检查关联的 Gateway/DataSource/Device

## 实施计划

### 1. 模型层变更

#### 1.1 Site 模型扩展 (`backend/app/models/spatial.py`)
```python
# 新增字段
contact_person = Column(String(50), comment="联系人")
contact_phone = Column(String(20), comment="联系电话")
contact_email = Column(String(100), comment="联系邮箱")
network_config = Column(JSON, comment="网络配置(VPN/专线信息)")
status = Column(String(20), default="active", comment="状态: active/inactive/maintenance")
```

#### 1.2 Gateway/DataSource FK 约束 (`backend/app/models/gateway.py`)
```python
# Gateway
site_id = Column(Integer, ForeignKey("sites.id"), default=1, comment="站点 ID")

# DataSource
site_id = Column(Integer, ForeignKey("sites.id"), default=1, comment="站点 ID")
```

#### 1.3 Alembic 迁移
- 生成迁移脚本添加新字段和 FK 约束

### 2. Schema 层变更 (`backend/app/schemas/spatial.py`)

```python
class SiteCreate(BaseModel):
    site_code: str
    site_name: str
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    network_config: Optional[dict] = None
    description: Optional[str] = None

class SiteUpdate(BaseModel):
    # 同上，全部 Optional

class SiteResponse(BaseModel):
    # 增加新字段 + status
    # 增加统计字段
    gateway_count: Optional[int] = 0
    device_count: Optional[int] = 0
```

### 3. API 层增强 (`backend/app/api/v1/spatial.py`)

#### 3.1 站点列表增加统计
- GET `/v1/spatial/sites` 返回每个站点的 gateway_count, device_count
- 支持 status 过滤

#### 3.2 站点删除增强
- 删除前检查关联的 Gateway, DataSource, Device（不仅仅是 Floor）
- 有关联数据时返回 400 + 详细信息

#### 3.3 站点状态管理
- PUT `/v1/spatial/sites/{site_id}/status` — 启用/停用/维护

### 4. EMQX ACL 服务 (`backend/app/services/emqx_acl.py`)

```python
class EmqxAclService:
    """EMQX ACL 管理 — 按 site_id 隔离 Topic 权限"""

    async def generate_acl_rules(self, site_id: int) -> list[dict]:
        """为站点生成 ACL 规则"""
        # 允许: dcim/{site_id}/gw/+/# (该站点的网关 topic)
        # 拒绝: dcim/其他站点/# (其他站点的 topic)

    async def sync_acl_to_emqx(self, site_id: int):
        """同步 ACL 规则到 EMQX (通过 HTTP API)"""
        # EMQX 提供 REST API 管理 ACL
        # POST /api/v5/authorization/sources/built_in_database/rules/...

    async def on_site_created(self, site_id: int, site_code: str):
        """站点创建后自动配置 ACL"""

    async def on_site_deleted(self, site_id: int):
        """站点删除后清理 ACL"""
```

#### 4.1 ACL 规则模型 (`backend/app/models/gateway.py`)
```python
class MqttAclRule(Base):
    """MQTT ACL 规则表"""
    __tablename__ = "mqtt_acl_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    client_id_pattern = Column(String(200), comment="客户端ID匹配模式")
    topic_pattern = Column(String(200), nullable=False, comment="Topic 匹配模式")
    action = Column(String(10), default="all", comment="动作: publish/subscribe/all")
    permission = Column(String(10), default="allow", comment="权限: allow/deny")
    description = Column(String(200), comment="描述")
    created_at = Column(DateTime, default=datetime.now)
```

### 5. site_id 行级隔离增强

#### 5.1 新增 `require_site_access` 依赖 (`backend/app/api/deps.py`)
```python
async def require_site_access(
    site_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> int:
    """验证用户对指定站点的访问权限"""
    if current_user.role == "admin":
        return site_id
    result = await db.execute(
        select(UserSite).where(
            UserSite.user_id == current_user.id,
            UserSite.site_id == site_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "无权访问该站点")
    return site_id
```

#### 5.2 Gateway/DataSource API 增加 site_id 过滤
- 在 gateway 列表 API 中使用 `get_user_site_ids` 过滤
- 在 datasource 列表 API 中使用 `get_user_site_ids` 过滤

### 6. 测试计划

#### 6.1 模型测试
- Site 新字段 CRUD
- Gateway/DataSource FK 约束验证
- MqttAclRule CRUD

#### 6.2 API 测试
- 站点 CRUD（含新字段）
- 站点删除关联检查（有 Gateway/Device 时拒绝删除）
- 站点状态管理
- site_id 权限过滤（admin vs operator/viewer）
- Gateway/DataSource 按 site_id 过滤

#### 6.3 EMQX ACL 测试
- ACL 规则生成
- 站点创建/删除时 ACL 同步
- Topic 权限匹配验证

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/app/models/spatial.py` | 修改 | Site 增加联系人/网络配置/状态字段 |
| `backend/app/models/gateway.py` | 修改 | Gateway/DataSource site_id 加 FK; 新增 MqttAclRule |
| `backend/app/schemas/spatial.py` | 修改 | SiteCreate/Update/Response 增加新字段 |
| `backend/app/api/v1/spatial.py` | 修改 | 站点列表增加统计、删除增强、状态管理 |
| `backend/app/api/deps.py` | 修改 | 新增 require_site_access 依赖 |
| `backend/app/services/emqx_acl.py` | 新增 | EMQX ACL 管理服务 |
| `backend/app/api/v1/gateways.py` | 修改 | 增加 site_id 过滤 |
| `backend/tests/test_site_management.py` | 新增 | 站点管理测试 |

## 验收标准对照

- [x] 可配置站点名称、地址、联系人、网络配置 → Site 模型扩展 + Schema + API
- [x] 所有业务表通过 site_id 字段实现行级数据隔离 → Gateway/DataSource FK + require_site_access + get_user_site_ids
- [x] EMQX ACL 按 site_id 隔离 Topic 权限 → EmqxAclService + MqttAclRule
