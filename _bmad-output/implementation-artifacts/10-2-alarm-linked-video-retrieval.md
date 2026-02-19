# Story 10-2: 告警联动视频调取

## Story

**As a** 运维工程师,
**I want** 告警触发时自动弹出关联摄像头画面,
**So that** 我可以远程查看现场情况。

## Status: Done

## Acceptance Criteria

- Given 告警触发且关联设备有对应摄像头
- When 系统通过 设备-区域-摄像头 关联链找到最近摄像头
- Then 前端自动弹出摄像头实时画面
- And 支持分屏布局（1/4/9 分屏，CSS Grid 实现）
- And 联动触发时自动切换到关联摄像头的 4 分屏布局

## FR 追溯

FR40

## Architecture Reference

Architecture 8.2, 8.4, 8.5

### 数据流
- 告警触发 → 联动引擎 VIDEO_POPUP 动作 → WebSocket 广播摄像头信息 → 前端弹出视频窗口
- 视频流: 前端直连 NVR (HLS/RTSP)，不经过后端

### 摄像头查找链
告警触发时通过 设备→区域→摄像头 关联链自动找到最近摄像头

## Technical Design

### Task 1: 实现 VIDEO_POPUP 动作处理器 — `backend/app/engines/action_handlers.py`

修改 `VideoPopupHandler.execute()`:
- 从 event.payload 提取 device_id 和 area_code
- 通过 video_service.get_cameras_by_device(db, device_id) 查找关联摄像头
- 如果没找到，通过 video_service.get_cameras_by_area(db, area_code) 查找区域摄像头
- 通过 ws_manager.broadcast_alarm() 广播 VIDEO_POPUP 消息，包含摄像头列表
- 消息格式: `{ action: "video_popup", cameras: [{id, name, rtsp_url, hls_url, preset_index?}], alarm_id, area_code }`

注意: action_handlers 中没有 db session，需要通过 async_session 获取。参考 AlarmNotifyHandler 的 import 模式。

### Task 2: 视频弹窗查询 API — `backend/app/api/v1/video.py`

新增端点:
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /cameras/by-alarm/{alarm_id} | require_viewer | 根据告警查找关联摄像头 |

逻辑:
1. 查询 Alarm 获取 device_id 和 area_code
2. 先按 device_id 查摄像头，再按 area_code 查
3. 返回去重后的摄像头列表（含 presets）

### Task 3: 前端视频弹窗组件 — `frontend/src/components/video/VideoPopup.vue`

全局视频弹窗组件:
- 响应 WebSocket alarm 通道的 `video_popup` action
- 弹出可拖拽的浮动窗口
- 支持 1/4/9 分屏布局切换（CSS Grid）
- 每个格子显示摄像头名称 + 视频占位区域（实际视频流需要 hls.js，本 story 先用占位图+流地址展示）
- 联动触发时默认 4 分屏
- 关闭按钮

### Task 4: 前端 API 补充 — `frontend/src/api/modules/video.ts`

新增:
- `getCamerasByAlarm(alarmId: number): Promise<CameraItem[]>` — GET /cameras/by-alarm/{alarmId}

### Task 5: WebSocket 消息处理 — `frontend/src/api/websocket.ts` 或 alarm store

在 alarm WebSocket 消息处理中增加对 `video_popup` action 的处理，触发视频弹窗组件显示。

### Task 6: 视频弹窗集成到主布局 — `frontend/src/layouts/MainLayout.vue`

在主布局中引入 VideoPopup 组件，使其全局可用。

### Task 7: 后端测试 — `backend/tests/test_video.py`

追加测试:
- test_get_cameras_by_alarm_with_device — 告警有 device_id，找到关联摄像头
- test_get_cameras_by_alarm_with_area — 告警无 device_id 但有 area_code，找到区域摄像头
- test_get_cameras_by_alarm_not_found — 告警不存在返回 404
- test_get_cameras_by_alarm_no_cameras — 告警存在但无关联摄像头，返回空列表
- test_video_popup_handler — 测试 VideoPopupHandler 执行

## Implementation Notes

- VIDEO_POPUP handler 需要数据库访问，使用 `from ..core.database import async_session` 获取 session
- 视频流播放需要 hls.js 库，本 story 先展示摄像头信息和流地址，实际播放可后续增强
- 分屏布局用 CSS Grid: `grid-template-columns: repeat(N, 1fr)` 其中 N=1/2/3
- 静态路由 `/cameras/by-alarm/{alarm_id}` 必须在 `/cameras/{camera_id}` 之前注册
