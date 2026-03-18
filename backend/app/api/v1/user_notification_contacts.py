"""
用户通知联系方式 API
Story 34.1 — 多渠道告警通知
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User
from app.models.user_notification_contact import UserNotificationContact
from app.schemas.user_notification_contact import (
    ImportFromProfileResponse,
    NotificationContactCreate,
    NotificationContactInfo,
    NotificationContactUpdate,
    validate_contact_value,
)

router = APIRouter()

require_admin = require_role(["admin"])


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return user


async def _get_contact_or_404(db: AsyncSession, user_id: int, contact_id: int) -> UserNotificationContact:
    result = await db.execute(
        select(UserNotificationContact).where(
            UserNotificationContact.id == contact_id,
            UserNotificationContact.user_id == user_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail=f"通知联系方式 {contact_id} 不存在或不属于用户 {user_id}")
    return contact


@router.get(
    "/{user_id}/notification-contacts",
    response_model=list[NotificationContactInfo],
    summary="获取用户所有通知联系方式",
)
async def get_notification_contacts(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    await _get_user_or_404(db, user_id)
    result = await db.execute(
        select(UserNotificationContact)
        .where(UserNotificationContact.user_id == user_id)
        .order_by(UserNotificationContact.channel_type, UserNotificationContact.id)
    )
    contacts = result.scalars().all()
    return [NotificationContactInfo.model_validate(c) for c in contacts]


@router.post(
    "/{user_id}/notification-contacts",
    response_model=NotificationContactInfo,
    status_code=201,
    summary="新增通知联系方式",
)
async def create_notification_contact(
    user_id: int,
    data: NotificationContactCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    await _get_user_or_404(db, user_id)
    contact = UserNotificationContact(
        user_id=user_id,
        channel_type=data.channel_type,
        platform=data.platform,
        contact_value=data.contact_value,
        is_enabled=data.is_enabled,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return NotificationContactInfo.model_validate(contact)


@router.put(
    "/{user_id}/notification-contacts/{contact_id}",
    response_model=NotificationContactInfo,
    summary="更新通知联系方式",
)
async def update_notification_contact(
    user_id: int,
    contact_id: int,
    data: NotificationContactUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    contact = await _get_contact_or_404(db, user_id, contact_id)

    if data.contact_value is not None:
        try:
            validate_contact_value(contact.channel_type, data.contact_value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        contact.contact_value = data.contact_value
    if data.is_enabled is not None:
        contact.is_enabled = data.is_enabled

    await db.commit()
    await db.refresh(contact)
    return NotificationContactInfo.model_validate(contact)


@router.delete(
    "/{user_id}/notification-contacts/{contact_id}",
    status_code=204,
    summary="删除通知联系方式",
)
async def delete_notification_contact(
    user_id: int,
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    contact = await _get_contact_or_404(db, user_id, contact_id)
    await db.delete(contact)
    await db.commit()


@router.post(
    "/{user_id}/notification-contacts/import-from-profile",
    response_model=ImportFromProfileResponse,
    summary="从账户信息导入通知联系方式",
)
async def import_from_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    user = await _get_user_or_404(db, user_id)

    # 查询现有联系方式
    result = await db.execute(
        select(UserNotificationContact).where(UserNotificationContact.user_id == user_id)
    )
    existing = result.scalars().all()
    existing_set = {(c.channel_type, c.contact_value) for c in existing}

    created = []
    skipped = 0

    # 从 User.phone 导入 sms + voice
    if user.phone:
        for ch in ("sms", "voice"):
            if (ch, user.phone) in existing_set:
                skipped += 1
                continue
            contact = UserNotificationContact(
                user_id=user_id,
                channel_type=ch,
                contact_value=user.phone,
                is_enabled=True,
            )
            db.add(contact)
            created.append(contact)

    # 从 User.email 导入 email
    if user.email:
        if ("email", user.email) in existing_set:
            skipped += 1
        else:
            contact = UserNotificationContact(
                user_id=user_id,
                channel_type="email",
                contact_value=user.email,
                is_enabled=True,
            )
            db.add(contact)
            created.append(contact)

    if created:
        await db.commit()
        for c in created:
            await db.refresh(c)

    return ImportFromProfileResponse(
        created=[NotificationContactInfo.model_validate(c) for c in created],
        skipped=skipped,
    )
