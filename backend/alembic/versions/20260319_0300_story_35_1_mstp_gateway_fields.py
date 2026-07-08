"""story_35_1_mstp_gateway_fields

Revision ID: 20260319_0300
Revises: 20260319_0200
Create Date: 2026-03-19

Story 35.1: BACnet MS/TP 网关 — DeviceTemplate 新增 extra_config, DataSource 新增 parent_datasource_id
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260319_0300"
down_revision: Union[str, None] = "20260319_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    dialect_name = conn.dialect.name

    # DeviceTemplate: 新增 extra_config
    dt_columns = [c["name"] for c in inspector.get_columns("device_templates")]
    if "extra_config" not in dt_columns:
        op.add_column(
            "device_templates",
            sa.Column("extra_config", sa.JSON(), nullable=True, comment="扩展配置（网关参数等）"),
        )

    # DataSource: 新增 parent_datasource_id
    ds_columns = [c["name"] for c in inspector.get_columns("datasources")]
    if "parent_datasource_id" not in ds_columns:
        op.add_column(
            "datasources",
            sa.Column(
                "parent_datasource_id",
                sa.Integer(),
                nullable=True,
                comment="父数据源ID（MS/TP设备指向其网关DataSource）",
            ),
        )
        op.create_index("ix_datasources_parent_id", "datasources", ["parent_datasource_id"])
        if dialect_name != "sqlite":
            op.create_foreign_key(
                "fk_datasources_parent_datasource_id",
                "datasources",
                "datasources",
                ["parent_datasource_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # 种子数据: 预置大金VRV转换网关模板（幂等）
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM device_templates WHERE name = :name"),
        {"name": "大金VRV转换网关(Intesis MAPS)"},
    ).scalar()

    if count == 0:
        import json
        conn.execute(
            sa.text(
                "INSERT INTO device_templates "
                "(name, manufacturer, model, protocol_type, description, point_config, extra_config, "
                "created_at, updated_at) "
                "VALUES (:name, :manufacturer, :model, :protocol_type, :description, "
                ":point_config, :extra_config, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "name": "大金VRV转换网关(Intesis MAPS)",
                "manufacturer": "大金/Intesis",
                "model": "MAPS-VRV-BACNET",
                "protocol_type": "bacnet_ip",
                "description": "大金VRV空调通过Intesis MAPS网关转BACnet/IP接入，需根据实际设备手册调整对象实例号",
                "point_config": json.dumps([
                    {"address": "MI:1", "data_type": "uint16", "scale": 1.0, "offset": 0.0, "description": "运行模式"},
                    {"address": "AV:1", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "设定温度"},
                    {"address": "AI:1", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "回风温度"},
                    {"address": "MI:2", "data_type": "uint16", "scale": 1.0, "offset": 0.0, "description": "故障码"},
                ]),
                "extra_config": json.dumps({
                    "gateway_type": "bacnet_mstp_to_ip",
                    "gateway_device_instance": 100,
                    "mstp_config": {"network_number": 1, "mac_range": [1, 127], "baud_rate": 9600, "parity": "none"},
                    "bbmd_config": {"enabled": False, "bdt_entries": []},
                    "downstream_devices": [],
                }),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    dialect_name = conn.dialect.name

    # 删除种子数据
    conn.execute(
        sa.text("DELETE FROM device_templates WHERE name = :name"),
        {"name": "大金VRV转换网关(Intesis MAPS)"},
    )

    ds_columns = [c["name"] for c in inspector.get_columns("datasources")]
    if "parent_datasource_id" in ds_columns:
        if dialect_name != "sqlite":
            op.drop_constraint(
                "fk_datasources_parent_datasource_id",
                "datasources",
                type_="foreignkey",
            )
        op.drop_index("ix_datasources_parent_id", table_name="datasources")
        op.drop_column("datasources", "parent_datasource_id")

    dt_columns = [c["name"] for c in inspector.get_columns("device_templates")]
    if "extra_config" in dt_columns:
        op.drop_column("device_templates", "extra_config")
