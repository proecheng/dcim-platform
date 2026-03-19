# Story 35.1: BACnet MS/TP 转换网关设备模板与数据源创建

Status: ready-for-dev

## Story

As a 集成工程师,
I want 在设备模板中创建 BACnet MS/TP 转换网关模板，并从模板批量创建网关及下挂设备的数据源,
So that 我能快速配置协议转换网关并一次性接入所有下挂 MS/TP 设备。

## Acceptance Criteria

1. **Given** 集成工程师创建设备模板 **When** protocol_type="bacnet_ip" 且 extra_config 包含 `gateway_type: "bacnet_mstp_to_ip"` **Then** 模板保存成功，extra_config 包含 mstp_config 和 downstream_devices
2. **Given** 模板 extra_config 中 mstp_config.baud_rate 不在 [9600, 19200, 38400, 76800, 115200] **When** 保存模板 **Then** 返回 422 验证错误；mac_address 不在 1-127 范围内时同样返回 422；device_instance 不在 0-4194302 范围内时同样返回 422
3. **Given** 集成工程师调用批量创建端点 **When** 提供网关 IP、端口（可选，默认47808）和站点信息 **Then** 创建 1 个网关 DataSource + N 个设备 DataSource（N=downstream_devices 数量），设备 DataSource 的 parent_datasource_id 指向网关 DataSource；网关 DataSource 的 name 包含 IP 以区分（格式："{模板名}-网关-{gateway_ip}"）
4. **Given** 网关 DataSource 已创建 **When** 查看数据源列表 **Then** 网关和下挂设备以父子关系展示（DataSourceResponse 包含 parent_datasource_id）
5. **Given** extra_config 不含 gateway_type 或 gateway_type 值不是 "bacnet_mstp_to_ip" **When** 保存模板 **Then** extra_config 原样存储，不做 MS/TP 特定验证（透传模式）
6. **Given** 批量创建端点返回成功 **When** 查看响应 **Then** 返回包含网关 DataSource 和所有子 DataSource 的列表

## Tasks / Subtasks

- [ ] Task 1: 数据库模型扩展 + Alembic 迁移 (AC: #1, #3, #4)
  - [ ] 1.1 DeviceTemplate 模型新增 `extra_config = Column(JSON, nullable=True)` 字段
  - [ ] 1.2 DataSource 模型新增 `parent_datasource_id = Column(Integer, ForeignKey("datasources.id", ondelete="SET NULL"), nullable=True, index=True)` 字段
  - [ ] 1.2b DataSource 模型新增自引用 relationship：`children = relationship("DataSource", backref=backref("parent", remote_side=[id]), lazy="noload")`（避免列表查询 N+1，需要时显式 joinedload/selectinload）
  - [ ] 1.3 创建 Alembic 迁移脚本（幂等性检查，Inspector 模式）
  - [ ] 1.4 运行 `alembic upgrade head` 验证迁移

- [ ] Task 2: Pydantic Schema 扩展 (AC: #1, #2, #4)
  - [ ] 2.1 在 `backend/app/schemas/gateway.py` 中新增 MS/TP 相关 Schema：MstpDownstreamDevice（mac_address: Field(ge=1, le=127)、device_instance: Field(ge=0, le=4194302)）、MstpConfig（baud_rate: Literal[9600,19200,38400,76800,115200]）、BbmdConfig、MstpGatewayExtraConfig（含 model_validator 检查 downstream_devices 内 mac_address 和 device_instance 不重复）、CreateMstpDatasourcesRequest（gateway_ip: str 需 IPv4 格式验证、port: int = 47808）、CreateMstpDatasourcesResponse（gateway: DataSourceResponse、devices: list[DataSourceResponse]、total_devices: int）
  - [ ] 2.2 DeviceTemplateBase / DeviceTemplateCreate / DeviceTemplateUpdate 新增 `extra_config: Optional[dict] = None`
  - [ ] 2.3 DeviceTemplateResponse 新增 `extra_config: Optional[dict] = None`
  - [ ] 2.4 DataSourceResponse 新增 `parent_datasource_id: Optional[int] = None`

- [ ] Task 3: 新增 API 端点 — 批量创建 MS/TP 数据源 (AC: #3)
  - [ ] 3.1 在 `backend/app/api/v1/device_templates.py` 新增 `POST /{template_id}/create-mstp-datasources` 端点
  - [ ] 3.2 端点逻辑：验证模板 extra_config.gateway_type → 验证 downstream_devices 非空 → 创建网关 DataSource (is_enabled=False) → flush → 创建子 DataSource (parent_datasource_id) → 填充点位 → commit
  - [ ] 3.3 整个操作在单个数据库事务中执行（flush + 最终 commit）

- [ ] Task 4: extra_config 验证逻辑 (AC: #1, #2, #5)
  - [ ] 4.1 在 create/update 模板端点中，检查 extra_config 是否为 dict 且包含 gateway_type 字段
  - [ ] 4.2 如果 gateway_type == "bacnet_mstp_to_ip"，用 MstpGatewayExtraConfig 解析并验证（baud_rate、mac_address 范围、device_instance 范围）
  - [ ] 4.3 如果 extra_config 不含 gateway_type 或 gateway_type 值不是已知类型，原样存储不验证（透传模式，支持未来扩展）
  - [ ] 4.4 如果 extra_config 为 None，跳过验证

- [ ] Task 5: 种子数据 (AC: #1)
  - [ ] 5.1 在数据库初始化或种子数据中预置"大金VRV转换网关(Intesis MAPS)"模板，含 extra_config 和 point_config

- [ ] Task 6: 测试 (AC: #1-#4)
  - [ ] 6.1 模型字段存在性测试（extra_config, parent_datasource_id）
  - [ ] 6.2 Schema 验证测试（MstpGatewayExtraConfig、baud_rate 校验、downstream_devices 校验）
  - [ ] 6.3 API 测试：创建/更新/查询带 extra_config 的模板
  - [ ] 6.4 API 测试：create-mstp-datasources 完整流程（网关+子设备+点位）
  - [ ] 6.5 API 测试：create-mstp-datasources 错误场景（模板无 extra_config、gateway_type 不匹配、downstream_devices 为空、模板不存在）
  - [ ] 6.6 API 测试：DataSourceResponse 包含 parent_datasource_id
  - [ ] 6.7 事务回滚测试（模拟中途失败，确认无残留数据）
  - [ ] 6.8 权限测试（viewer 无法创建、operator 可以创建）
  - [ ] 6.9 Schema 验证测试：mac_address 范围（0 和 128 应失败）、device_instance 范围（负数和 4194303 应失败）
  - [ ] 6.10 API 测试：create-mstp-datasources 响应包含网关和所有子 DataSource 列表
  - [ ] 6.11 回归测试：确认现有 test_device_templates.py 中不传 extra_config 的测试仍通过（extra_config 默认 None）
  - [ ] 6.12 API 测试：extra_config 透传模式（不含 gateway_type 的 dict 原样保存）
  - [ ] 6.13 Schema 验证测试：gateway_ip 非法格式（如 "abc"、空字符串）应返回 422
  - [ ] 6.14 Schema 验证测试：downstream_devices 内 mac_address 重复应返回 422
  - [ ] 6.15 API 测试：子设备 DataSource 的 name 使用 device_name、collection_interval=10

## Dev Notes

### 架构约束

- **不修改现有端点**：现有 `POST /device-templates/{id}/create-datasource` 保持不变，新增独立的 `create-mstp-datasources` 端点
- **事务原子性**：批量创建使用 `flush()` + 最终 `commit()`，不使用逐步 commit
- **网关 DataSource 特殊处理**：`is_enabled=False`，不参与采集调度，仅作为父节点和心跳目标
- **point_config 语义不变**：网关配置存放在 extra_config 中，point_config 仍然是点位数组

### 现有代码模式（必须遵循）

**DeviceTemplate 模型** — `backend/app/models/gateway.py:179-193`
```python
class DeviceTemplate(Base):
    __tablename__ = "device_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    manufacturer = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    protocol_type = Column(String(30), nullable=False)
    description = Column(String(500))
    point_config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

**DataSource 模型** — `backend/app/models/gateway.py:31-54`
```python
class DataSource(Base):
    __tablename__ = "datasources"
    id, name, protocol_type, gateway_id, connection_config(JSON),
    collection_interval(default=5), write_enabled(default=False),
    status(default="disconnected"), last_communication,
    consecutive_failures(default=0), retry_base_delay(1.0),
    retry_max_delay(60.0), retry_max_failures(5),
    site_id(FK→sites.id), is_enabled(default=True),
    created_at, updated_at
```

**现有 create-datasource 端点逻辑** — `backend/app/api/v1/device_templates.py:130-163`
```python
# 关键模式：从模板创建 DataSource + DataSourcePoint
for pt_cfg in template.point_config or []:
    point = DataSourcePoint(
        datasource_id=ds.id,
        address=str(pt_cfg.get("address", "")),
        data_type=pt_cfg.get("data_type"),
        scale=float(pt_cfg.get("scale", 1.0)),
        offset=float(pt_cfg.get("offset", 0.0)),
        enum_mapping=pt_cfg.get("enum_mapping"),
        is_dry_contact=pt_cfg.get("is_dry_contact", False),
    )
    session.add(point)
```

**Schema 模式** — `backend/app/schemas/gateway.py`
- DeviceTemplateBase → DeviceTemplateCreate / DeviceTemplateUpdate / DeviceTemplateResponse
- DataSourceBase → DataSourceCreate / DataSourceUpdate / DataSourceResponse
- 使用 `ConfigDict(from_attributes=True)` 进行 ORM 映射

**权限模式**：
- GET → `require_viewer`
- POST/PUT → `require_operator`
- DELETE → `require_admin`

**迁移模式**（参考 `d20698c35b80`）：
- 幂等性检查：`inspector = Inspector.from_engine(conn)` 检查列是否存在
- `op.add_column()` 添加字段
- 升级与降级对称

**测试模式**（参考 `tests/api/test_device_templates.py`）：
- 使用 `client`, `async_db`, `operator_token`, `admin_token` 等 conftest fixtures
- 辅助函数 `_create_template(async_db, ...)` 直接插入数据库
- `auth_headers(token)` 构造认证头
- 验证 status_code + 响应体内容

### extra_config JSON 结构（MS/TP 网关模板）

注意：extra_config 不含 `bacnet_ip` 子对象。网关自身的 device_instance 存放在 `gateway_device_instance` 顶层字段中，BACnet/IP 端口在批量创建时通过 API 请求传入（默认 47808）。

```json
{
    "gateway_type": "bacnet_mstp_to_ip",
    "gateway_device_instance": 100,
    "mstp_config": {
        "network_number": 1,
        "mac_range": [1, 127],
        "baud_rate": 9600,
        "parity": "none"
    },
    "bbmd_config": {
        "enabled": false,
        "bdt_entries": []
    },
    "downstream_devices": [
        {
            "mac_address": 1,
            "device_instance": 201,
            "device_name": "大金VRV-B区-1",
            "model": "RXYQ16TAY1"
        }
    ]
}
```

**MstpGatewayExtraConfig Schema 完整定义：**
```python
class MstpGatewayExtraConfig(BaseModel):
    gateway_type: Literal["bacnet_mstp_to_ip"]
    gateway_device_instance: int = Field(ge=0, le=4194302, description="网关自身 BACnet 设备实例号")
    mstp_config: MstpConfig
    bbmd_config: Optional[BbmdConfig] = None
    downstream_devices: list[MstpDownstreamDevice] = []  # 模板允许空，批量创建时校验非空
```

### connection_config 构造规则

- **网关 DataSource**：`{"host": "{gateway_ip}", "port": {port}, "device_id": {extra_config.gateway_device_instance}, "is_mstp_gateway": true}`
  - name = `"{模板名}-网关-{gateway_ip}"`
  - is_enabled = False（不参与采集，仅供心跳探测）
- **子设备 DataSource**：`{"host": "{gateway_ip}", "port": {port}, "device_id": {设备 device_instance}}`
  - name = downstream_devices 中的 device_name（直接使用）
  - is_enabled = True，collection_interval = 10（BACnet MS/TP 较慢，默认 10 秒而非 5 秒）
- port 来自 CreateMstpDatasourcesRequest.port（默认 47808）
- 所有子设备共享网关 IP 和端口，用不同的 device_instance 区分
- `is_mstp_gateway: true` 标记供 Story 35.2 的 `check_mstp_gateway_health` 识别网关 DataSource

### API 响应格式

`POST /{template_id}/create-mstp-datasources` 成功返回：
```json
{
    "gateway": { DataSourceResponse },
    "devices": [ DataSourceResponse, ... ],
    "total_devices": N
}
```
需定义 `CreateMstpDatasourcesResponse` Schema。

### 种子数据模板

```python
DeviceTemplate(
    name="大金VRV转换网关(Intesis MAPS)",
    manufacturer="大金/Intesis",
    model="MAPS-VRV-BACNET",
    protocol_type="bacnet_ip",
    description="大金VRV空调通过Intesis MAPS网关转BACnet/IP接入，需根据实际设备手册调整对象实例号",
    point_config=[
        {"address": "MI:1", "data_type": "uint16", "scale": 1.0, "offset": 0.0, "description": "运行模式"},
        {"address": "AV:1", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "设定温度"},
        {"address": "AI:1", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "回风温度"},
        {"address": "MI:2", "data_type": "uint16", "scale": 1.0, "offset": 0.0, "description": "故障码"},
    ],
    extra_config={
        "gateway_type": "bacnet_mstp_to_ip",
        "gateway_device_instance": 100,
        "mstp_config": {"network_number": 1, "mac_range": [1, 127], "baud_rate": 9600, "parity": "none"},
        "bbmd_config": {"enabled": False, "bdt_entries": []},
        "downstream_devices": []  # 种子模板不含具体设备，使用前需编辑填入 downstream_devices
    }
)
```

### Project Structure Notes

- 模型扩展：`backend/app/models/gateway.py` — 在现有 DeviceTemplate 和 DataSource 类中各加一个字段
- Schema 扩展：`backend/app/schemas/gateway.py` — 新增 MS/TP 相关 Schema + 扩展现有 Base/Response
- API 扩展：`backend/app/api/v1/device_templates.py` — 新增一个端点，不修改现有端点
- 迁移脚本：`backend/alembic/versions/` — 新增迁移文件
- 测试文件：`backend/tests/api/test_mstp_datasources.py` — 新测试文件
- 种子数据：在 `backend/app/core/init_db.py` 或 `backend/app/demo/service.py` 中追加 MS/TP 模板（需先查明现有 DeviceTemplate 种子数据位置，按 name 做幂等检查避免重复插入）

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 35, Story 35.1 行 4724-4837]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 24 BACnet MS/TP 设备接入架构]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 6 协议适配器插件化架构]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 3 核心数据模型]
- [Source: backend/app/models/gateway.py — DeviceTemplate(179-193), DataSource(31-54)]
- [Source: backend/app/schemas/gateway.py — Schema 定义]
- [Source: backend/app/api/v1/device_templates.py — 现有端点模式]
- [Source: backend/tests/api/test_device_templates.py — 测试模式]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
