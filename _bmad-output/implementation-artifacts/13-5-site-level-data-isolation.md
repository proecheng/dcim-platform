# Story 13-5: 站点级数据隔离

## Status: Ready for Implementation

## Story
As a 运维主管,
I want 在统一视图中查看多站点数据,
So that 我可以跨站点对比分析，而运维人员只能看到自己负责的站点。

## Acceptance Criteria (AC)

### AC1: 用户-站点关联
- Given 系统已有 Site 模型（models/spatial.py）
- When 管理员为用户分配站点权限
- Then 用户与站点通过 UserSite 关联表建立多对多关系
- And admin 角色自动拥有所有站点访问权限（不受 UserSite 限制）

### AC2: 设备站点归属
- Given Device 模型已存在
- When 添加 site_id 字段到 Device 表
- Then 设备可关联到具体站点
- And site_id 为可选字段（nullable），兼容已有数据

### AC3: 站点数据过滤依赖注入
- Given 用户已登录
- When 调用需要站点过滤的 API
- Then 系统通过依赖注入函数 `get_user_site_ids` 返回用户可访问的站点 ID 列表
- And admin 角色返回 None（表示不过滤，可见所有数据）
- And operator/viewer 角色返回其关联的站点 ID 列表

### AC4: 用户站点管理 API
- Given 管理员已登录
- When 调用站点分配 API
- Then 可以为用户分配/取消站点权限
- And 可以查询用户的站点列表
- And 可以查询站点下的用户列表

### AC5: 设备按站点过滤
- Given 用户已登录且有站点权限
- When 查询设备列表
- Then 仅返回用户有权限的站点下的设备
- And admin 可见所有设备

## Technical Design

### 1. 新增模型: UserSite（用户-站点关联表）

文件: `backend/app/models/user.py`

```python
class UserSite(Base):
    """用户-站点关联表"""
    __tablename__ = "user_sites"
    __table_args__ = (
        UniqueConstraint("user_id", "site_id", name="uq_user_site"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, comment="站点ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
```

### 2. Device 模型添加 site_id

文件: `backend/app/models/device.py`

```python
site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, comment="所属站点ID")
```

### 3. 依赖注入函数

文件: `backend/app/api/deps.py`

```python
async def get_user_site_ids(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Optional[list[int]]:
    """获取用户可访问的站点ID列表。admin 返回 None（不过滤）"""
    if current_user.role == "admin":
        return None
    result = await db.execute(
        select(UserSite.site_id).where(UserSite.user_id == current_user.id)
    )
    return [row[0] for row in result.fetchall()]
```

### 4. 用户站点管理 API

文件: `backend/app/api/v1/user.py` 新增端点

- `GET /users/{user_id}/sites` — 查询用户的站点列表
- `PUT /users/{user_id}/sites` — 设置用户的站点权限（全量替换）
- `GET /sites/{site_id}/users` — 查询站点下的用户列表

### 5. 设备列表站点过滤

文件: `backend/app/api/v1/device.py` — 修改现有设备列表查询，注入 site_ids 过滤

## Schema 设计

```python
# schemas/user.py 新增
class UserSiteUpdate(BaseModel):
    site_ids: list[int]

class UserSiteInfo(BaseModel):
    site_id: int
    site_code: str
    site_name: str

    class Config:
        from_attributes = True
```

## 测试计划

1. 创建 UserSite 关联 — 为用户分配站点
2. 查询用户站点列表 — 返回正确站点
3. 更新用户站点 — 全量替换
4. admin 不受站点限制 — get_user_site_ids 返回 None
5. operator 仅见授权站点设备 — 设备列表过滤
6. 站点下用户列表 — 返回正确用户

## 依赖

- Site 模型已存在（models/spatial.py）
- User 模型已存在（models/user.py）
- Device 模型已存在（models/device.py）
- 站点 CRUD API 已存在（api/v1/spatial.py）
