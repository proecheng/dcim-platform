# Story 10-1: 摄像头元数据管理

## Story

**As a** 系统管理员,
**I want** 管理摄像头和 NVR 的元数据,
**So that** 系统知道每个摄像头的位置和关联区域。

## Status: Done

## Acceptance Criteria

- Given 系统管理员在视频管理页面
- When 录入摄像头信息
- Then 可配置：名称、RTSP URL、ONVIF URL、关联 NVR、位置描述、关联区域/机柜/设备
- And 支持预置位列表配置（联动快速定位）
- And 视频流由前端直接从 NVR 拉取（RTSP/HLS），不经过后端

## FR 追溯

FR44

## Architecture Reference

Architecture 8.1-8.6 视频监控集成架构

### 核心原则
视频流前端直连 NVR，DCIM 只负责元数据管理和联动触发。

### 摄像头关联模型
```
Camera
├── id, name, rtsp_url, onvif_url
├── nvr_id → NVR
├── site_id → Site
├── location_description
├── 多对多关联: 区域、机柜、设备
└── presets[] (预置位列表，联动快速定位)
```

### 数据模型（架构定义）
- Camera, NVR, VideoEvent — 摄像头元数据、NVR 连接、联动录像事件
- API 路径: `/api/v1/video`

## Technical Design

### Task 1: 数据模型 — `backend/app/models/video.py`

创建 NVR、Camera、CameraPreset 三个模型。

**NVR 表:**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| name | String(100) | NVR 名称 |
| ip_address | String(50) | NVR IP 地址 |
| port | Integer | NVR 端口 (默认 554) |
| username | String(100) | 登录用户名 |
| password | String(200) | 登录密码 |
| manufacturer | String(50) | 厂商 (hikvision/dahua/other) |
| model | String(100) | 型号 |
| max_channels | Integer | 最大通道数 |
| status | String(20) | 状态: online/offline |
| description | Text | 备注 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

**Camera 表:**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| name | String(100) | 摄像头名称 |
| code | String(50) unique | 摄像头编码 |
| rtsp_url | String(500) | RTSP 流地址 |
| onvif_url | String(500) | ONVIF 控制地址 |
| hls_url | String(500) | HLS 流地址 (可选) |
| nvr_id | Integer FK → nvrs.id | 关联 NVR |
| channel_no | Integer | NVR 通道号 |
| area_code | String(10) | 关联区域代码 |
| cabinet_id | Integer FK → cabinets.id | 关联机柜 (可选) |
| device_id | Integer FK → devices.id | 关联设备 (可选) |
| location_description | String(200) | 位置描述 |
| camera_type | String(20) | 类型: dome/bullet/ptz |
| status | String(20) | 状态: online/offline/unknown |
| is_enabled | Boolean | 是否启用 (默认 true) |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

**CameraPreset 表:**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| camera_id | Integer FK → cameras.id | 关联摄像头 |
| preset_index | Integer | 预置位编号 |
| name | String(100) | 预置位名称 |
| description | String(200) | 描述 |

### Task 2: Schema — `backend/app/schemas/video.py`

**NVR Schemas:**
- `NVRCreate`: name, ip_address, port?, username?, password?, manufacturer?, model?, max_channels?, description?
- `NVRUpdate`: 所有字段可选
- `NVRResponse`: 全字段 + model_config = ConfigDict(from_attributes=True)

**Camera Schemas:**
- `CameraCreate`: name, code, rtsp_url, onvif_url?, hls_url?, nvr_id?, channel_no?, area_code?, cabinet_id?, device_id?, location_description?, camera_type?, presets?[]
- `CameraUpdate`: 所有字段可选
- `CameraResponse`: 全字段 + nvr_name(可选) + presets 列表
- `CameraListResponse`: 分页包装

**CameraPreset Schemas:**
- `CameraPresetCreate`: preset_index, name, description?
- `CameraPresetResponse`: 全字段

### Task 3: Service — `backend/app/services/video_service.py`

**NVR 服务函数:**
- `create_nvr(db, data)` → NVR
- `update_nvr(db, nvr_id, data)` → NVR
- `delete_nvr(db, nvr_id)` → bool (检查是否有关联摄像头)
- `get_nvr(db, nvr_id)` → NVR
- `list_nvrs(db, page, page_size)` → {total, items}

**Camera 服务函数:**
- `create_camera(db, data)` → Camera (含 presets 批量创建)
- `update_camera(db, camera_id, data)` → Camera (含 presets 更新)
- `delete_camera(db, camera_id)` → bool
- `get_camera(db, camera_id)` → Camera + presets + nvr_name
- `list_cameras(db, nvr_id?, area_code?, status?, page, page_size)` → {total, items}
- `get_cameras_by_area(db, area_code)` → Camera[] (联动查询用)
- `get_cameras_by_device(db, device_id)` → Camera[] (联动查询用)

### Task 4: API 路由 — `backend/app/api/v1/video.py`

路由前缀: `/api/v1/video`

**NVR 端点:**
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /nvrs | require_admin | 创建 NVR |
| GET | /nvrs | require_viewer | NVR 列表 |
| GET | /nvrs/{nvr_id} | require_viewer | NVR 详情 |
| PUT | /nvrs/{nvr_id} | require_admin | 更新 NVR |
| DELETE | /nvrs/{nvr_id} | require_admin | 删除 NVR |

**Camera 端点:**
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /cameras | require_admin | 创建摄像头 |
| GET | /cameras | require_viewer | 摄像头列表 (支持 nvr_id/area_code/status 筛选) |
| GET | /cameras/{camera_id} | require_viewer | 摄像头详情 (含 presets) |
| PUT | /cameras/{camera_id} | require_admin | 更新摄像头 (含 presets) |
| DELETE | /cameras/{camera_id} | require_admin | 删除摄像头 |
| GET | /cameras/by-area/{area_code} | require_viewer | 按区域查询摄像头 |
| GET | /cameras/by-device/{device_id} | require_viewer | 按设备查询摄像头 |

### Task 5: 注册路由 — `backend/app/api/v1/__init__.py`

添加 video_router 注册:
```python
from .video import router as video_router
api_router.include_router(video_router, prefix="/video", tags=["视频监控"])
```

### Task 6: 注册模型 — `backend/app/models/__init__.py`

添加 NVR, Camera, CameraPreset 导入和 __all__ 导出。

### Task 7: 前端 API 模块 — `frontend/src/api/modules/video.ts`

TypeScript 接口 + 请求函数，覆盖所有后端端点。

### Task 8: 前端页面 — `frontend/src/views/video/index.vue`

视频管理页面，包含:
- NVR 管理 Tab: NVR 列表 + 新增/编辑/删除对话框
- 摄像头管理 Tab: 摄像头列表 + 新增/编辑/删除对话框 (含预置位配置)
- 筛选: 按 NVR、区域、状态筛选
- 使用 `@use '@/styles/_mixins-25d' as *;` + `@include page-list;`

### Task 9: 前端路由 — `frontend/src/router/index.ts`

添加视频管理路由:
```typescript
{
  path: '/video',
  name: 'VideoManagement',
  component: () => import('@/views/video/index.vue'),
  meta: { title: '视频监控', icon: 'VideoCamera', roles: ['admin', 'operator', 'viewer'] }
}
```

### Task 10: 后端测试 — `backend/tests/test_video.py`

测试用例覆盖:
- NVR CRUD (5 tests)
- Camera CRUD (5 tests)
- Camera 筛选 (按 NVR/区域/状态) (3 tests)
- Camera 预置位管理 (2 tests)
- NVR 删除保护 (有关联摄像头时拒绝) (1 test)
- 权限验证 (viewer 不能创建/删除) (2 tests)
- 预计 18 个测试

## Implementation Notes

- 遵循现有 Epic 9 模式: model → schema → service → API → register → frontend
- Camera 的 presets 使用 JSON 字段或独立表 (选择独立表 CameraPreset，更规范)
- NVR 密码字段存储但 API 响应中不返回明文 (返回 "***" 掩码)
- 静态路由 `/cameras/by-area/{area_code}` 和 `/cameras/by-device/{device_id}` 必须在 `/cameras/{camera_id}` 之前注册
- 视频流不经过后端，前端直连 NVR 的 RTSP/HLS 地址
