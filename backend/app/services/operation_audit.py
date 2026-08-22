"""Helpers for recording management operations in the shared audit log."""

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.log import OperationLog
from ..models.user import User


def add_operation_audit(
    db: AsyncSession,
    actor: User,
    *,
    module: str,
    action: str,
    target_type: str,
    target_id: int | None,
    target_name: str | None,
    old_value: Mapping[str, Any] | None = None,
    new_value: Mapping[str, Any] | None = None,
    remark: str | None = None,
) -> None:
    """Add an audit record to the caller's transaction."""
    db.add(
        OperationLog(
            user_id=actor.id,
            username=actor.username,
            module=module,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name[:100] if target_name is not None else None,
            old_value=json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
            new_value=json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None,
            remark=remark,
        )
    )
