# Story 10-4: 告警回放

## Story

**As a** 运维工程师,
**I want** 通过告警时间快速定位历史录像,
**So that** 我可以回放告警发生时的现场画面进行复盘。

## Status: Done

## Acceptance Criteria

- Given 运维工程师在告警详情页面
- When 点击"查看录像"
- Then 通过告警时间戳定位到 NVR 录像片段
- And 录像回放由 NVR 负责，DCIM 只提供时间定位
- And 支持前进/后退/倍速播放

## FR 追溯

FR43

## Architecture Reference

Architecture 8.6

### 核心原则
- DCIM 只管"触发"和"元数据"
- 录像文件存储和回放完全由 NVR 负责
- 回放时通过时间戳定位到 NVR 录像片段
- DCIM 提供回放入口（告警→摄像头→时间戳→NVR 回放 URL）

## Technical Design

### Task 1: 回放查询服务 — `backend/app/services/video_service.py`

新增函数:
- `get_playback_info(db, alarm_id)` → Dict
  - 查询 Alarm 获取 alarm_time、point_id
  - 通过 Point 获取 device_id/area_code
  - 查找关联摄像头（device_id 优先，area_code 兜底）
  - 查找该告警关联的 VideoEvent（recording_start/recording_stop）
  - 返回: alarm_info（id, level, message, alarm_time）, cameras（含 rtsp_url/hls_url）, recording_events, playback_url_template

- `list_recording_segments(db, camera_id, start_time, end_time)` → List[Dict]
  - 查询 VideoEvent 中 recording_start/recording_stop 事件
  - 按时间范围筛选
  - 返回录像片段列表: [{start_time, end_time, camera_id, camera_name, alarm_id}]

### Task 2: 回放 Schema — `backend/app/schemas/video.py`

新增:
- `PlaybackInfoResponse`: alarm_info, cameras(List), recording_events(List), playback_url_template(str)
- `RecordingSegmentResponse`: id, camera_id, camera_name, start_time, end_time, alarm_id, duration_seconds

### Task 3: 回放 API 端点 — `backend/app/api/v1/video.py`

新增端点:
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /playback/alarm/{alarm_id} | require_viewer | 获取告警回放信息（摄像头+时间定位） |
| GET | /playback/segments | require_viewer | 查询录像片段列表（camera_id + 时间范围） |

### Task 4: 前端 API 补充 — `frontend/src/api/modules/video.ts`

新增类型和函数:
- PlaybackInfo, RecordingSegment 类型
- getPlaybackInfo(alarmId) → PlaybackInfoResponse
- getRecordingSegments(params) → RecordingSegmentResponse[]

### Task 5: 前端回放页面 — `frontend/src/views/video/playback.vue`

告警回放页面:
- 路由: /video/playback?alarm_id=xxx
- 顶部: 告警信息卡片（告警级别、消息、时间）
- 左侧: 摄像头列表（关联摄像头，点击切换）
- 中间: 视频播放区域
  - 模拟播放器（因 NVR 实际不可用，显示摄像头信息 + 时间定位信息）
  - 播放控制栏: 播放/暂停、倍速选择（0.5x/1x/2x/4x）、进度条、时间显示
- 右侧: 录像片段时间轴（显示该摄像头的录像事件列表）

### Task 6: 前端路由 — `frontend/src/router/index.ts`

在 video children 下添加 playback 路由。

### Task 7: 告警详情集成 — 告警页面添加"查看录像"按钮

在告警相关页面（如果存在告警详情弹窗/页面），添加"查看录像"按钮:
- 点击后跳转到 /video/playback?alarm_id=xxx
- 如果告警详情页面不存在独立组件，则在回放页面支持手动输入告警 ID 查询

### Task 8: 后端测试 — `backend/tests/test_video.py`

追加测试:
- test_get_playback_info — GET /playback/alarm/{id}，验证返回 alarm_info + cameras
- test_get_playback_info_not_found — 告警不存在返回 404
- test_list_recording_segments — GET /playback/segments，验证按时间范围筛选
- test_list_recording_segments_empty — 无录像片段返回空列表

## Implementation Notes

- 视频回放实际由 NVR 提供 RTSP/HLS 流，DCIM 只构造带时间戳参数的 URL
- playback_url_template 格式: `{hls_url}?starttime={start}&endtime={end}`，前端替换参数
- 因为没有真实 NVR，前端播放器区域显示模拟界面（摄像头信息 + 时间定位 + 播放控制）
- 倍速播放等控制在前端模拟实现，实际生产中由 NVR 流控制
- 录像片段通过 VideoEvent 的 recording_start/recording_stop 配对计算
