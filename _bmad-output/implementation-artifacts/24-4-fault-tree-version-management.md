# Story 24.4: 故障树版本管理与 HMAC 签名

**Epic**: 24 - 智能诊断核心引擎
**Story ID**: 24.4
**创建日期**: 2026-03-06
**状态**: ready-for-dev

---

## User Story

As a 管理员,
I want 对故障树进行版本管理和完整性保护,
So that 故障树变更有迹可循，配置不会被未授权篡改。

---

## 验收标准（Acceptance Criteria）

### 1. 版本创建

- **Given** 管理员编辑了一棵故障树
- **When** 创建新版本时
- **Then** 系统在 `fault_tree_versions` 表创建记录：
  - tree_id: 关联的故障树 ID
  - version_number: 自增版本号（从 1 开始）
  - status: 初始状态为 draft
  - snapshot: 完整的节点+边结构的 JSON 快照（`json.dumps(config, sort_keys=True)` 确保一致性）
  - hmac_signature: 初始为 NULL（激活时生成）
  - created_by: 创建者用户 ID
  - created_at: 创建时间
- **And** snapshot 包含完整的故障树结构（节点列表、边列表、设备映射）
- **And** 同一故障树可以有多个版本，但只能有一个 active 版本

### 2. 版本审批

- **Given** 管理员需要将版本从 draft 改为 reviewed
- **When** 调用审批 API
- **Then** 系统验证审批者与创建者不同（`reviewed_by != created_by`）
- **And** 验证通过后将状态改为 reviewed，记录 reviewed_by 和 reviewed_at
- **And** 验证失败时返回 403 错误："不能审批自己创建的版本"

### 3. 版本激活与 HMAC 签名

- **Given** 管理员需要激活一个 reviewed 状态的版本
- **When** 调用激活 API
- **Then** 系统执行以下步骤：
  1. 从环境变量读取 `FAULT_TREE_HMAC_KEY`（必需，最短 32 字节）
  2. 验证快照中的故障树结构是否为有效的 DAG（调用 DAGValidator）
  3. 如果版本已有签名（重新激活场景），验证签名（使用当前密钥或 `FAULT_TREE_HMAC_KEY_PREVIOUS`，支持密钥轮换）
  4. 使用 HMAC-SHA-256 对 snapshot 生成新签名：`hmac.new(key, snapshot.encode(), hashlib.sha256).hexdigest()`
  5. 使用数据库锁（SELECT FOR UPDATE）获取同一 tree_id 的所有 active 版本，防止并发激活
  6. 在单个事务中：将其他 active 版本改为 archived，将当前版本状态改为 active，更新 hmac_signature 和 activated_at
  7. 通过 Redis Pub/Sub 发布 `diagnosis:tree_version_change` 事件
- **And** DAG 验证失败时拒绝激活，返回具体错误信息
- **And** 签名验证失败时拒绝激活，记录安全告警日志
- **And** 诊断引擎订阅版本切换事件，热加载新版本故障树到内存
- **And** 并发激活时，后提交的请求会因为数据库锁而等待，确保只有一个版本最终为 active

### 4. 密钥管理

- **Given** 系统启动时
- **When** 检查环境变量 `FAULT_TREE_HMAC_KEY`
- **Then** 如果未设置或长度 < 32 字节，应用拒绝启动并记录错误日志
- **And** 支持密钥轮换：
  - 签名时使用 `FAULT_TREE_HMAC_KEY`（当前密钥）
  - 验证时同时尝试 `FAULT_TREE_HMAC_KEY` 和 `FAULT_TREE_HMAC_KEY_PREVIOUS`（可选）
  - 允许平滑过渡：先设置 PREVIOUS 为旧密钥，再更新当前密钥，最后移除 PREVIOUS

### 5. 版本回滚

- **Given** 管理员需要回滚到上一个版本
- **When** 调用回滚 API
- **Then** 系统找到同一 tree_id 的最近一个 archived 版本
- **And** 验证该版本的签名（如果签名验证失败，拒绝回滚并返回错误："版本签名验证失败，可能使用了已删除的旧密钥，请联系管理员"）
- **And** 签名验证通过后，重新激活该版本（执行 DAG 验证、状态切换、生成新签名）
- **And** 如果没有可回滚的版本，返回 404 错误："没有可回滚的版本"

### 6. 版本列表查询

- **Given** 管理员需要查看故障树的版本历史
- **When** 调用版本列表 API
- **Then** 返回该故障树的所有版本，包含：
  - version_number: 版本号
  - status: 状态（draft, reviewed, active, archived）
  - created_by: 创建者
  - created_at: 创建时间
  - reviewed_by: 审批者
  - reviewed_at: 审批时间
  - activated_at: 激活时间
- **And** 按 version_number DESC 排序（最新版本在前）
- **And** 支持按 status 过滤

---

## 技术实现要点

### 1. 数据库表结构

```sql
-- 故障树版本表
CREATE TABLE fault_tree_versions (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES fault_trees(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'active', 'archived')),
    snapshot TEXT NOT NULL,  -- JSON 快照
    hmac_signature VARCHAR(64),  -- HMAC-SHA-256 签名（64 字符十六进制）
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    activated_at TIMESTAMP,
    UNIQUE(tree_id, version_number)
);

CREATE INDEX idx_fault_tree_versions_tree_id ON fault_tree_versions(tree_id);
CREATE INDEX idx_fault_tree_versions_status ON fault_tree_versions(status);
CREATE INDEX idx_fault_tree_versions_tree_status ON fault_tree_versions(tree_id, status);
```

**ORM 模型**:

```python
# backend/app/models/fault_tree.py (添加到现有文件)
from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class FaultTreeVersion(Base):
    """故障树版本"""
    __tablename__ = "fault_tree_versions"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    snapshot = Column(Text, nullable=False)
    hmac_signature = Column(String(64))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(TIMESTAMP)
    activated_at = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'reviewed', 'active', 'archived')", name="check_status"),
    )

    tree = relationship("FaultTree", back_populates="versions")
```

**Alembic 迁移脚本**:

```python
# backend/alembic/versions/xxxx_add_fault_tree_versions_table.py
"""add_fault_tree_versions_table

Revision ID: xxxx
Revises: 4cbe2c1df9bb
Create Date: 2026-03-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'xxxx'
down_revision: Union[str, None] = '4cbe2c1df9bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'fault_tree_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('snapshot', sa.Text(), nullable=False),
        sa.Column('hmac_signature', sa.String(length=64), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('activated_at', sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'reviewed', 'active', 'archived')", name='check_status'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'version_number', name='uq_tree_version')
    )
    op.create_index(op.f('ix_fault_tree_versions_id'), 'fault_tree_versions', ['id'], unique=False)
    op.create_index(op.f('ix_fault_tree_versions_tree_id'), 'fault_tree_versions', ['tree_id'], unique=False)
    op.create_index(op.f('ix_fault_tree_versions_status'), 'fault_tree_versions', ['status'], unique=False)
    op.create_index(op.f('ix_fault_tree_versions_tree_status'), 'fault_tree_versions', ['tree_id', 'status'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_fault_tree_versions_tree_status'), table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_status'), table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_tree_id'), table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_id'), table_name='fault_tree_versions')
    op.drop_table('fault_tree_versions')
```


### 2. HMAC 签名实现

```python
# backend/app/services/diagnosis/hmac_manager.py
import hmac
import hashlib
from typing import Optional
from app.core.config import get_settings

class HMACManager:
    """HMAC 签名管理器"""

    @staticmethod
    def generate_signature(data: str) -> str:
        """生成 HMAC-SHA-256 签名"""
        settings = get_settings()
        key = settings.FAULT_TREE_HMAC_KEY.encode()
        signature = hmac.new(key, data.encode(), hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    def verify_signature(data: str, signature: str) -> bool:
        """验证 HMAC 签名（支持密钥轮换）"""
        # 输入验证
        if not signature or len(signature) != 64:
            return False

        # 验证是否为有效的十六进制字符串
        try:
            int(signature, 16)
        except ValueError:
            return False

        settings = get_settings()

        # 尝试当前密钥
        current_key = settings.FAULT_TREE_HMAC_KEY.encode()
        expected_sig = hmac.new(current_key, data.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, signature):
            return True

        # 尝试旧密钥（如果配置了）
        if settings.FAULT_TREE_HMAC_KEY_PREVIOUS:
            previous_key = settings.FAULT_TREE_HMAC_KEY_PREVIOUS.encode()
            expected_sig = hmac.new(previous_key, data.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected_sig, signature):
                return True

        return False
```

### 3. 版本管理服务

```python
# backend/app/services/diagnosis/version_manager.py
import json
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.fault_tree import FaultTree, FaultTreeNode, FaultTreeEdge, FaultTreeDeviceMapping, FaultTreeVersion
from app.services.diagnosis.hmac_manager import HMACManager
from app.services.diagnosis.dag_validator import DAGValidator
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

class VersionManager:
    """故障树版本管理器"""

    @staticmethod
    async def create_version(
        session: AsyncSession,
        tree_id: int,
        created_by: int
    ) -> FaultTreeVersion:
        """创建新版本"""
        # 查询故障树及其节点和边
        tree = await session.get(FaultTree, tree_id)
        if not tree:
            raise ValueError(f"Fault tree {tree_id} not found")

        nodes = await session.execute(
            select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
        )
        edges = await session.execute(
            select(FaultTreeEdge).where(FaultTreeEdge.tree_id == tree_id)
        )
        device_mappings = await session.execute(
            select(FaultTreeDeviceMapping).where(FaultTreeDeviceMapping.tree_id == tree_id)
        )

        # 构建完整快照（包含设备映射）
        snapshot = {
            "tree": {"id": tree.id, "name": tree.name, "description": tree.description},
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "gate_type": n.gate_type,
                    "name": n.name,
                    "description": n.description,
                    "prior_probability": n.prior_probability,
                    "evidence_point_id": n.evidence_point_id,
                    "config": n.config
                }
                for n in nodes.scalars()
            ],
            "edges": [
                {"parent_node_id": e.parent_node_id, "child_node_id": e.child_node_id}
                for e in edges.scalars()
            ],
            "device_mappings": [
                {
                    "device_type": dm.device_type,
                    "alarm_type": dm.alarm_type,
                    "priority": dm.priority
                }
                for dm in device_mappings.scalars()
            ]
        }
        snapshot_json = json.dumps(snapshot, sort_keys=True)

        # 使用 SELECT FOR UPDATE 获取下一个版本号（防止并发冲突）
        result = await session.execute(
            select(FaultTreeVersion.version_number)
            .where(FaultTreeVersion.tree_id == tree_id)
            .order_by(FaultTreeVersion.version_number.desc())
            .limit(1)
            .with_for_update()
        )
        last_version = result.scalar_one_or_none()
        next_version = (last_version or 0) + 1

        # 创建版本记录
        version = FaultTreeVersion(
            tree_id=tree_id,
            version_number=next_version,
            status="draft",
            snapshot=snapshot_json,
            created_by=created_by
        )
        session.add(version)
        await session.commit()
        return version

    @staticmethod
    async def activate_version(
        session: AsyncSession,
        version_id: int
    ) -> FaultTreeVersion:
        """激活版本"""
        version = await session.get(FaultTreeVersion, version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        if version.status != "reviewed":
            raise ValueError(f"Only reviewed versions can be activated, current status: {version.status}")

        # 解析快照并验证 DAG
        try:
            snapshot_data = json.loads(version.snapshot)
            nodes = snapshot_data.get("nodes", [])
            edges = snapshot_data.get("edges", [])

            is_valid, error_msg = DAGValidator.validate(nodes, edges)
            if not is_valid:
                raise ValueError(f"DAG validation failed: {error_msg}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid snapshot JSON: {e}")

        # 如果版本已有签名（重新激活场景），先验证旧签名
        if version.hmac_signature:
            if not HMACManager.verify_signature(version.snapshot, version.hmac_signature):
                logger.error(f"HMAC signature verification failed for version {version_id}")
                raise ValueError("HMAC signature verification failed")

        # 生成新签名
        new_signature = HMACManager.generate_signature(version.snapshot)

        # 使用 SELECT FOR UPDATE 锁定同一 tree 的所有 active 版本（防止并发激活）
        await session.execute(
            select(FaultTreeVersion.id)
            .where(FaultTreeVersion.tree_id == version.tree_id)
            .where(FaultTreeVersion.status == "active")
            .with_for_update()
        )

        # 在单个事务中完成状态切换
        # 1. 归档同一 tree 的其他 active 版本
        await session.execute(
            update(FaultTreeVersion)
            .where(FaultTreeVersion.tree_id == version.tree_id)
            .where(FaultTreeVersion.status == "active")
            .values(status="archived")
        )

        # 2. 激活当前版本
        version.status = "active"
        version.hmac_signature = new_signature
        version.activated_at = func.now()
        await session.commit()

        # 发布版本切换事件（失败不影响激活）
        try:
            redis = await get_redis()
            await redis.publish("diagnosis:tree_version_change", json.dumps({
                "tree_id": version.tree_id,
                "version_id": version.id,
                "version_number": version.version_number
            }))
        except Exception as e:
            logger.warning(f"Failed to publish version change event: {e}")

        return version

    @staticmethod
    async def rollback_version(
        session: AsyncSession,
        tree_id: int
    ) -> FaultTreeVersion:
        """回滚到上一个版本"""
        # 查找最近一个 archived 版本
        result = await session.execute(
            select(FaultTreeVersion)
            .where(FaultTreeVersion.tree_id == tree_id)
            .where(FaultTreeVersion.status == "archived")
            .order_by(FaultTreeVersion.activated_at.desc())
            .limit(1)
        )
        archived_version = result.scalar_one_or_none()

        if not archived_version:
            raise ValueError("没有可回滚的版本")

        # 验证签名
        if archived_version.hmac_signature:
            if not HMACManager.verify_signature(archived_version.snapshot, archived_version.hmac_signature):
                raise ValueError("版本签名验证失败，可能使用了已删除的旧密钥，请联系管理员")

        # 将状态改为 reviewed，然后激活
        archived_version.status = "reviewed"
        await session.flush()

        # 调用 activate_version 完成激活
        return await VersionManager.activate_version(session, archived_version.id)
```

### 4. 配置更新

```python
# backend/app/core/config.py
from pydantic import field_validator

class Settings(BaseSettings):
    # ... 现有配置 ...

    # 故障树 HMAC 密钥
    FAULT_TREE_HMAC_KEY: str
    FAULT_TREE_HMAC_KEY_PREVIOUS: Optional[str] = None

    @field_validator("FAULT_TREE_HMAC_KEY")
    @classmethod
    def validate_hmac_key(cls, v):
        if not v:
            raise ValueError("FAULT_TREE_HMAC_KEY is required")
        if len(v) < 32:
            raise ValueError("FAULT_TREE_HMAC_KEY must be at least 32 characters")
        return v
```

```bash
# .env.example
# 故障树 HMAC 密钥（至少 32 字符）
FAULT_TREE_HMAC_KEY=your-secret-key-at-least-32-chars-long
# 旧密钥（密钥轮换时使用）
# FAULT_TREE_HMAC_KEY_PREVIOUS=old-secret-key
```

### 5. Pydantic Schema

```python
# backend/app/schemas/fault_tree_version.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FaultTreeVersionCreate(BaseModel):
    """创建版本请求"""
    pass  # 所有参数从路径和当前用户获取

class FaultTreeVersionResponse(BaseModel):
    """版本响应"""
    id: int
    tree_id: int
    version_number: int
    status: str
    snapshot: str
    hmac_signature: Optional[str] = None
    created_by: int
    created_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FaultTreeVersionListResponse(BaseModel):
    """版本列表响应"""
    id: int
    version_number: int
    status: str
    created_by: int
    created_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

### 6. API 路由

```python
# backend/app/api/v1/fault_tree_versions.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import Optional, List
from app.core.database import get_db
from app.core.security import require_role, get_current_user
from app.services.diagnosis.version_manager import VersionManager
from app.services.diagnosis.hmac_manager import HMACManager
from app.models.fault_tree import FaultTreeVersion
from app.schemas.fault_tree_version import (
    FaultTreeVersionCreate,
    FaultTreeVersionResponse,
    FaultTreeVersionListResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fault-trees/{tree_id}/versions", tags=["fault-tree-versions"])

@router.post("/", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def create_version(
    tree_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新版本"""
    try:
        version = await VersionManager.create_version(db, tree_id, current_user.id)
        return version
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{version_id}/review", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def review_version(
    tree_id: int,
    version_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """审批版本"""
    version = await db.get(FaultTreeVersion, version_id)
    if not version or version.tree_id != tree_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    if version.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only draft versions can be reviewed, current status: {version.status}"
        )

    # 验证审批者与创建者不同
    if version.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能审批自己创建的版本"
        )

    version.status = "reviewed"
    version.reviewed_by = current_user.id
    version.reviewed_at = func.now()
    await db.commit()
    await db.refresh(version)
    return version

@router.post("/{version_id}/activate", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def activate_version(
    tree_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """激活版本"""
    try:
        version = await VersionManager.activate_version(db, version_id)
        if version.tree_id != tree_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        return version
    except ValueError as e:
        logger.error(f"Failed to activate version {version_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/rollback", response_model=FaultTreeVersionResponse, dependencies=[Depends(require_role("admin"))])
async def rollback_version(
    tree_id: int,
    db: AsyncSession = Depends(get_db)
):
    """回滚到上一个版本"""
    try:
        version = await VersionManager.rollback_version(db, tree_id)
        return version
    except ValueError as e:
        logger.error(f"Failed to rollback tree {tree_id}: {e}")
        if "没有可回滚的版本" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[FaultTreeVersionListResponse])
async def list_versions(
    tree_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """版本列表"""
    query = select(FaultTreeVersion).where(FaultTreeVersion.tree_id == tree_id)

    if status:
        query = query.where(FaultTreeVersion.status == status)

    query = query.order_by(FaultTreeVersion.version_number.desc())

    result = await db.execute(query)
    versions = result.scalars().all()
    return versions
```

---

## 测试策略

### 1. 单元测试

**文件**: `backend/tests/services/test_hmac_manager.py`

**测试用例**:
- `test_generate_signature`: 生成签名
- `test_verify_signature_with_current_key`: 使用当前密钥验证
- `test_verify_signature_with_previous_key`: 使用旧密钥验证（密钥轮换）
- `test_verify_signature_failure`: 签名验证失败
- `test_timing_attack_resistance`: 时序攻击防护（使用 hmac.compare_digest）

### 2. 集成测试

**文件**: `backend/tests/api/test_fault_tree_versions.py`

**测试用例**:
- `test_create_version`: 创建版本，验证快照包含完整结构（节点、边、设备映射）
- `test_review_version_by_different_user`: 不同用户审批
- `test_review_version_by_same_user_forbidden`: 同一用户审批失败
- `test_activate_version`: 激活版本
- `test_activate_first_time`: 第一次激活（无旧签名）
- `test_activate_reactivation`: 重新激活（有旧签名，需验证）
- `test_activate_invalid_dag`: DAG 验证失败时拒绝激活
- `test_activate_archives_other_active_versions`: 激活时归档其他版本
- `test_activate_concurrent`: 并发激活时只有一个成功
- `test_activate_publishes_redis_event`: 激活时发布 Redis 事件
- `test_rollback_version`: 回滚版本
- `test_rollback_signature_verification_failed`: 回滚时签名验证失败
- `test_list_versions`: 版本列表查询
- `test_hmac_key_rotation`: 密钥轮换场景

### 3. 安全测试

- 测试未设置 HMAC_KEY 时应用启动失败
- 测试 HMAC_KEY 长度不足时应用启动失败
- 测试签名篡改检测
- 测试密钥轮换平滑过渡

---

## 依赖关系

### 前置依赖
- Story 24.3: 故障树数据模型与 CRUD（已完成）
- Epic 14: PostgreSQL 迁移完成

### 后续依赖
- Story 24.5: L2 故障树推理引擎（需要加载 active 版本的故障树）

---

## 验收检查清单

- [ ] Alembic 迁移脚本创建 fault_tree_versions 表
- [ ] HMACManager 实现签名生成和验证
- [ ] VersionManager 实现版本创建、审批、激活、回滚
- [ ] 配置文件添加 HMAC_KEY 验证
- [ ] .env.example 添加 HMAC_KEY 示例
- [ ] API 路由实现版本管理接口
- [ ] 单元测试全部通过
- [ ] 集成测试全部通过
- [ ] 安全测试全部通过
- [ ] Redis Pub/Sub 事件发布和订阅
- [ ] 诊断引擎热加载新版本故障树

---

## 工作量估算

- 数据库迁移脚本: 0.5 小时
- ORM 模型: 0.5 小时
- HMACManager: 1 小时
- VersionManager: 2 小时
- 配置更新: 0.5 小时
- API 路由: 1.5 小时
- 单元测试: 1.5 小时
- 集成测试: 1.5 小时
- 文档更新: 0.5 小时

**总计**: 约 9.5 小时（1.2 个工作日）

---

## FR 追溯

- FR34-6: 故障树版本管理
- FR34-16: 配置完整性保护（HMAC 签名）

---

## 备注

1. **密钥安全**: HMAC_KEY 必须通过环境变量注入，不能硬编码在代码中。生产环境建议使用密钥管理服务（如 AWS Secrets Manager）。

2. **密钥轮换**: 支持平滑过渡，避免服务中断。步骤：(1) 设置 PREVIOUS 为旧密钥；(2) 更新当前密钥；(3) 等待所有版本重新激活（触发重新签名）；(4) 移除 PREVIOUS。

3. **签名验证**: 使用 `hmac.compare_digest` 防止时序攻击。

4. **版本快照**: 使用 `json.dumps(sort_keys=True)` 确保 JSON 序列化的一致性，避免字段顺序不同导致签名不匹配。

5. **Redis 事件**: 诊断引擎订阅 `diagnosis:tree_version_change` 事件，热加载新版本故障树，无需重启服务。

6. **审批流程**: 要求不同用户审批，防止自我审批绕过审查。

7. **回滚机制**: 只能回滚到 archived 状态的版本，不能回滚到 draft 或 reviewed 状态。回滚时需验证签名，如果签名验证失败（旧密钥已删除），拒绝回滚。

8. **并发控制**: 使用 SELECT FOR UPDATE 锁定版本记录，防止并发激活导致多个 active 版本。

9. **DAG 验证**: 激活前验证快照中的故障树结构是否为有效的 DAG，防止加载损坏的配置。

10. **事务保护**: create_version 和 activate_version 都在单个事务中完成，确保数据一致性。
