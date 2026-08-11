"""
Story 24.8: 诊断结果标注与RBAC 集成测试
"""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.diagnosis import DiagnosisSession, DiagnosisAnnotation
from app.models.spatial import Site
from app.models.user import UserSite


@pytest.fixture(autouse=True)
async def authorized_diagnosis_device(async_db: AsyncSession, operator_user):
    operator, _ = operator_user
    site = Site(site_code="ANNOTATION-SITE", site_name="标注测试站点")
    async_db.add(site)
    await async_db.flush()
    async_db.add_all(
        [
            UserSite(user_id=operator.id, site_id=site.id),
            Device(
                id=1,
                device_code="ANNOTATION-DEVICE",
                device_name="标注测试设备",
                device_type="UPS",
                area_code="A",
                site_id=site.id,
            ),
        ]
    )
    await async_db.flush()


@pytest.mark.asyncio
async def test_create_annotation_success(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
):
    """测试创建标注 - 成功"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注
    response = await client.post(
        "/api/v1/diagnosis/annotations",
        json={
            "session_id": session.id,
            "annotation": "accurate",
            "notes": "测试标注",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.id
    assert data["annotation"] == "accurate"
    assert data["notes"] == "测试标注"


@pytest.mark.asyncio
async def test_create_annotation_inaccurate_without_root_cause(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
):
    """测试创建标注 - 标注为inaccurate但未提供actual_root_cause"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注（缺少 actual_root_cause）
    response = await client.post(
        "/api/v1/diagnosis/annotations",
        json={
            "session_id": session.id,
            "annotation": "inaccurate",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 400
    assert "actual_root_cause is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_annotation_inaccurate_with_root_cause(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
):
    """测试创建标注 - 标注为inaccurate且提供actual_root_cause"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注
    response = await client.post(
        "/api/v1/diagnosis/annotations",
        json={
            "session_id": session.id,
            "annotation": "inaccurate",
            "actual_root_cause": "实际是电源故障",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["annotation"] == "inaccurate"
    assert data["actual_root_cause"] == "实际是电源故障"


@pytest.mark.asyncio
async def test_create_annotation_session_not_found(
    client: AsyncClient,
    operator_token: str,
):
    """测试创建标注 - 会话不存在"""
    response = await client.post(
        "/api/v1/diagnosis/annotations",
        json={
            "session_id": 99999,
            "annotation": "accurate",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "诊断会话不存在"


@pytest.mark.asyncio
async def test_get_annotations_operator_only_own(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
    operator_user,
):
    """测试获取标注列表 - operator只能查看自己的"""
    user, _ = operator_user

    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注（当前用户）
    annotation1 = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=user.id,
        annotation="accurate",
        annotated_at=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(annotation1)

    # 创建标注（其他用户）
    annotation2 = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=999,  # 其他用户
        annotation="inaccurate",
        actual_root_cause="测试",
        annotated_at=datetime(2026, 3, 6, 10, 1, 0),
    )
    async_db.add(annotation2)
    await async_db.commit()

    # 查询标注列表
    response = await client.get(
        "/api/v1/diagnosis/annotations",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # operator 只能看到自己的标注
    assert data["total"] == 1
    assert data["items"][0]["annotator_id"] == user.id


@pytest.mark.asyncio
async def test_get_annotations_operator_query_other_user_forbidden(
    client: AsyncClient,
    operator_token: str,
):
    """测试获取标注列表 - operator查询其他用户ID返回403"""
    response = await client.get(
        "/api/v1/diagnosis/annotations?annotator_id=999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_annotations_admin_can_view_all(
    client: AsyncClient,
    async_db: AsyncSession,
    admin_token: str,
):
    """测试获取标注列表 - admin可以查看所有"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建多个用户的标注
    annotation1 = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=1,
        annotation="accurate",
        annotated_at=datetime(2026, 3, 6, 10, 0, 0),
    )
    annotation2 = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=2,
        annotation="inaccurate",
        actual_root_cause="测试",
        annotated_at=datetime(2026, 3, 6, 10, 1, 0),
    )
    async_db.add_all([annotation1, annotation2])
    await async_db.commit()

    # 查询标注列表
    response = await client.get(
        "/api/v1/diagnosis/annotations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # admin 可以看到所有标注
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_delete_annotation_operator_own(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
    operator_user,
):
    """测试删除标注 - operator删除自己的"""
    user, _ = operator_user

    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注
    annotation = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=user.id,
        annotation="accurate",
        annotated_at=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(annotation)
    await async_db.commit()
    await async_db.refresh(annotation)

    # 删除标注
    response = await client.delete(
        f"/api/v1/diagnosis/annotations/{annotation.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_annotation_operator_other_forbidden(
    client: AsyncClient,
    async_db: AsyncSession,
    operator_token: str,
):
    """测试删除标注 - operator删除其他用户的返回403"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注（其他用户）
    annotation = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=999,
        annotation="accurate",
        annotated_at=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(annotation)
    await async_db.commit()
    await async_db.refresh(annotation)

    # 删除标注
    response = await client.delete(
        f"/api/v1/diagnosis/annotations/{annotation.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_annotation_admin_can_delete_any(
    client: AsyncClient,
    async_db: AsyncSession,
    admin_token: str,
):
    """测试删除标注 - admin可以删除任何用户的"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建标注（其他用户）
    annotation = DiagnosisAnnotation(
        session_id=session.id,
        annotator_id=999,
        annotation="accurate",
        annotated_at=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(annotation)
    await async_db.commit()
    await async_db.refresh(annotation)

    # 删除标注
    response = await client.delete(
        f"/api/v1/diagnosis/annotations/{annotation.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_annotation_stats(
    client: AsyncClient,
    async_db: AsyncSession,
    admin_token: str,
):
    """测试获取标注统计"""
    # 创建测试会话
    session = DiagnosisSession(
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime(2026, 3, 6, 10, 0, 0),
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    # 创建多个标注
    annotations = [
        DiagnosisAnnotation(
            session_id=session.id,
            annotator_id=1,
            annotation="accurate",
            annotated_at=datetime(2026, 3, 6, 10, 0, 0),
        ),
        DiagnosisAnnotation(
            session_id=session.id,
            annotator_id=1,
            annotation="accurate",
            annotated_at=datetime(2026, 3, 6, 10, 1, 0),
        ),
        DiagnosisAnnotation(
            session_id=session.id,
            annotator_id=2,
            annotation="inaccurate",
            actual_root_cause="测试",
            annotated_at=datetime(2026, 3, 6, 10, 2, 0),
        ),
        DiagnosisAnnotation(
            session_id=session.id,
            annotator_id=2,
            annotation="unknown",
            annotated_at=datetime(2026, 3, 6, 10, 3, 0),
        ),
    ]
    async_db.add_all(annotations)
    await async_db.commit()

    # 获取统计
    response = await client.get(
        "/api/v1/diagnosis/annotations/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_annotations"] == 4
    assert data["accurate_count"] == 2
    assert data["inaccurate_count"] == 1
    assert data["unknown_count"] == 1
    assert data["accurate_rate"] == 50.0
    assert len(data["user_stats"]) == 2
    assert len(data["top_annotators"]) <= 10
