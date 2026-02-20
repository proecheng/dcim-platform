# Epic 10 回顾：视频监控集成

## 完成情况

全部 4 个 Story 完成。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 10-1 | 摄像头元数据管理 | ✅ | ✅ |
| 10-2 | 告警联动视频调取 | ✅ | ✅ |
| 10-3 | 区域联动录像与云台控制 | ✅ | ✅ |
| 10-4 | 告警回放 | ✅ | ✅ |

## 关键经验教训

### 架构决策验证

1. **DCIM 只管元数据，视频流前端直连 NVR** — 这个核心原则贯穿整个 Epic，避免了后端成为视频流瓶颈。DCIM 负责 Camera/NVR 元数据管理和联动触发，录像存储和回放完全由 NVR 承担。

2. **VIDEO_POPUP 动作处理器复用 Epic 9 框架** — 联动引擎的 ActionHandlerRegistry 在 10-2 中直接扩展，通过 WebSocket 广播摄像头信息到前端，验证了 Epic 9 动作处理器的扩展性设计。

3. **摄像头查找链设计** — 告警 → 设备 → 区域 → 摄像头的关联链，device_id 优先匹配、area_code 兜底，覆盖了设备级和区域级两种监控场景。

### 技术模式沉淀

- **VideoEvent 事件记录**：recording_start/recording_stop/ptz_control/preset_call 四种事件类型，trigger_source 区分 linkage/manual
- **PTZ 控制通过 ONVIF 转发**：后端只做命令转发和操作日志记录，不缓存云台状态
- **回放定位**：通过告警时间戳 + 摄像头关联定位到 NVR 录像片段，DCIM 提供 playback_url_template

### 注意事项

- NVR 连接状态检测依赖网络可达性，离线 NVR 的摄像头在前端需明确标记不可用
- 分屏布局（1/4/9）使用 CSS Grid 实现，联动触发时自动切换到 4 分屏

## 下一步

Epic 11: 运维管理（Phase 2）— 5 个 Stories
