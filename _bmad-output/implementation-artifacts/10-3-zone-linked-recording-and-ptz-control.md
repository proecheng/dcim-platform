# Story 10-3: 区域联动录像与云台控制

## Story

**As a** 运维工程师,
**I want** 在特定事件时自动触发录像并远程控制云台,
**So that** 关键事件有视频记录且可以远程定位到具体设备。

## Status: Draft

## Acceptance Criteria

- Given 消防联动/资产变更/现场调试等事件触发
- When 联动引擎发送 VIDEO_RECORD 动作
- Then 通过 ONVIF 命令触发 NVR 开始区域录像并标记时间戳
- And 运维工程师可远程控制摄像头云台（方向、聚焦），后端转发 PTZ 命令并记录操作日志
- And DCIM 记录 VideoEvent（事件时间、关联告警、摄像头 ID）

## FR 追溯

FR41, FR42

## Architecture Reference

Architecture 8.2, 8.6

### 核心原则
- DCIM 只管"触发"和"元数据"
- 联动引擎通过 ONVIF 命令触发 NVR 开始/停止录像
- 录像文件存储和回放完全由 NVR 负责
- DCIM 记录 VideoEvent（事件时间、关联告警、摄像头 ID）

## Technical Design

### Task 1: VideoEvent 模型 — `backend/app/models/video.py`

新增 VideoEvent 表:
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| camera_id | Integer FK → cameras.id | 关联摄像头 |
| event_type | String(30) | 事件类型: recording_start/recording_stop/ptz_control/preset_call |
| trigger_source | String(50) | 触发来源: linkage/manual |
| alarm_id | Integer | 关联告警 ID (可选) |
| linkage_execution_id | Integer | 关联联动执行 ID (可选) |
| detail | Text | 事件详情 JSON |
| operator | String(50) | 操作人 (PTZ 控制时) |
| created_at | DateTime | 事件时间 |

### Task 2: VideoEvent Schema — `backend/app/schemas/video.py`

新增:
- `VideoEventResponse`: 全字段 + camera_name
- `PTZControlRequest`: camera_id, action (up/down/left/right/zoom_in/zoom_out/stop), speed?
- `PresetCallRequest`: camera_id, preset_index
- `RecordingRequest`: camera_id, action (start/stop), alarm_id?, linkage_execution_id?

### Task 3: 视频事件服务 — `backend/app/services/video_service.py`

新增函数:
- `create_video_event(db, camera_id, event_type, trigger_source, alarm_id?, linkage_execution_id?, detail?, operator?)` → VideoEvent
- `list_video_events(db, camera_id?, event_type?, page, page_size)` → {total, items}
- `ptz_control(db, camera_id, action, speed, operator)` → VideoEvent (记录 PTZ 操作，实际 ONVIF 命令模拟)
- `call_preset(db, camera_id, preset_index, operator)` → VideoEvent (记录预置位调用)
- `start_recording(db, camera_id, trigger_source, alarm_id?, linkage_execution_id?)` → VideoEvent
- `stop_recording(db, camera_id)` → VideoEvent

### Task 4: API 端点 — `backend/app/api/v1/video.py`

新增端点:
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /ptz/control | require_operator | 云台控制 |
| POST | /ptz/preset | require_operator | 调用预置位 |
| POST | /recording/start | require_operator | 开始录像 |
| POST | /recording/stop | require_operator | 停止录像 |
| GET | /events | require_viewer | 视频事件列表 |

### Task 5: 实现 VIDEO_RECORD 动作处理器 — `backend/app/engines/action_handlers.py`

修改 `VideoRecordHandler.execute()`:
- 从 event.payload 提取 area_code/device_id
- 查找关联摄像头
- 调用 video_service.start_recording() 记录事件
- 通过 ws_manager 广播录像开始通知

### Task 6: 注册模型 — `backend/app/models/__init__.py`

添加 VideoEvent 导入和 __all__ 导出。

### Task 7: 前端 API 补充 — `frontend/src/api/modules/video.ts`

新增类型和函数:
- PTZControlParams, PresetCallParams, RecordingParams, VideoEventItem
- ptzControl, callPreset, startRecording, stopRecording, getVideoEvents

### Task 8: 前端视频控制面板 — `frontend/src/views/video/control.vue`

视频控制页面:
- 摄像头选择下拉
- PTZ 控制面板（方向键 + 缩放）
- 预置位快捷按钮
- 录像控制（开始/停止）
- 视频事件日志列表

### Task 9: 前端路由 — `frontend/src/router/index.ts`

在 video children 下添加 control 路由。

### Task 10: 后端测试 — `backend/tests/test_video.py`

追加测试:
- test_ptz_control — POST /ptz/control
- test_call_preset — POST /ptz/preset
- test_start_recording — POST /recording/start
- test_stop_recording — POST /recording/stop
- test_list_video_events — GET /events
- test_list_video_events_filter — 按 camera_id/event_type 筛选

## Implementation Notes

- ONVIF 命令实际执行需要 onvif-zeep 库，本 story 模拟执行（记录事件但不发送真实 ONVIF 命令）
- PTZ 控制和录像操作都记录到 VideoEvent 表作为审计日志
- VIDEO_RECORD handler 使用与 VIDEO_POPUP handler 相同的 async_session 模式
