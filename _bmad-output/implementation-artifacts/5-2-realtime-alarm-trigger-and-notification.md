# Story 5.2: 实时告警触发与通知

Status: done

## Story

As a 运维工程师,
I want 在点位数据超过阈值时立即收到告警通知,
So that 我可以及时响应异常情况。

## Acceptance Criteria (验收标准)

1. **AC-1: 告警引擎内存缓存** — 告警引擎在启动时从数据库批量加载所有启用的阈值配置到内存，按 point_id 分组缓存。每 30 秒检查阈值版本号（Story 5.1 的 `GET /api/v1/thresholds/version`），版本变化时自动重新加载
2. **AC-2: 阈值检测与告警触发** — 模拟器（或 MQTT 客户端）接收到点位数据后，调用告警引擎 `evaluate()` 方法进行阈值比对。支持所有阈值类型（high_high/high/low/low_low/equal/change），支持死区（dead_band）和延迟触发（delay_seconds）。越限后在 1 秒内触发告警
3. **AC-3: WebSocket 告警推送** — 告警触发后，通过 `ws_manager.broadcast_alarm()` 将告警数据推送到前端 alarms 通道
4. **AC-4: 前端声光报警提示** — 前端收到 WebSocket 告警消息后，显示 ElNotification 通知（紧急/重要告警持续显示直到关闭，次要/提示告警 10 秒后自动消失），播放告警声音（可通过 localStorage 配置开关）
5. **AC-5: 告警记录写入数据库** — 告警触发后创建 Alarm 记录写入数据库，包含 alarm_no、point_id、threshold_id、alarm_level、trigger_value、threshold_value 等完整信息
6. **AC-6: 告警风暴防护** — 同一点位在 60 秒内重复越限不重复产生告警（抑制重复告警），通过内存中记录每个点位最后告警时间实现
7. **AC-7: 大面积告警检测** — 同一设备类型（device_type）下 >50% 点位同时越限时，自动将这批告警标记为“疑似通信异常”（alarm_type 设为 communication），优先检查数据源状态
8. **AC-8: 后端测试** — 测试告警引擎 evaluate() 所有阈值类型、风暴防护、死区逻辑、延迟触发、大面积告警检测

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 告警引擎核心 (AC: #1, #2, #6, #7)
  - [ ] 1.1 创建 `backend/app/engines/__init__.py` 引擎包初始化文件
  - [ ] 1.2 创建 `backend/app/engines/alarm_engine.py`，实现 AlarmEngine 类
  - [ ] 1.3 实现 `load_thresholds()` — 从数据库批量加载所有启用的阈值，按 point_id 分组存入内存字典
  - [ ] 1.4 实现 `check_version()` — 调用阈值版本 API 比对版本号，版本变化时调用 `load_thresholds()` 重新加载
  - [ ] 1.5 实现 `evaluate(point_id, value, point_type)` — 遍历该点位的缓存阈值，逐一检测是否越限
  - [ ] 1.6 支持所有阈值类型检测：high_high、high、low、low_low、equal、change
  - [ ] 1.7 实现死区（dead_band）逻辑：触发后需要回到 threshold +/- dead_band 范围内才能再次触发
  - [ ] 1.8 实现延迟触发（delay_seconds）逻辑：首次越限记录时间戳，持续越限超过 delay_seconds 后才触发
  - [ ] 1.9 实现 `_check_storm(point_id)` — 同一点位 60 秒内不重复产生告警
  - [ ] 1.10 实现 `_check_mass_alarm(device_type)` — 统计同一 device_type 下越限点位占比，>50% 标记为通信异常
  - [ ] 1.11 创建全局单例 `alarm_engine = AlarmEngine()`

- [ ] Task 2: 后端 — 集成告警引擎到模拟器 (AC: #2, #3, #5)
  - [ ] 2.1 在 `backend/app/services/simulator.py` 中导入 alarm_engine
  - [ ] 2.2 替换 `_simulate_point()` 中的内联阈值检测逻辑（第 119-161 行）为 `alarm_engine.evaluate()` 调用
  - [ ] 2.3 根据 evaluate 返回的触发结果创建 Alarm 记录（含 threshold_id）
  - [ ] 2.4 告警创建后调用 `ws_manager.broadcast_alarm()` 推送到前端，消息必须包含 `action: "new"` 字段
  - [ ] 2.5 修改 `backend/app/services/websocket.py` 的 `broadcast_alarm()` 方法，从 alarm_data 中提取 `action` 字段放入消息顶层（兼容前端 `useAlarm.ts` 的 `handleAlarmMessage` 路由逻辑）
  - [ ] 2.6 告警创建后写入 Redis 告警统计：`alarm:stats:{level}` 计数递增

- [ ] Task 3: 后端 — 告警自动恢复 (AC: #9)
  - [ ] 3.1 在 `collect_and_save()` 中，当点位值回到安全范围时，查询该点位的活动告警
  - [ ] 3.2 将活动告警状态更新为 resolved（resolve_type="auto"），计算 duration_seconds
  - [ ] 3.3 通过 `ws_manager.broadcast_alarm()` 广播 `action: "resolve"` 消息
  - [ ] 3.4 更新 Redis 告警统计：对应级别计数递减

- [ ] Task 4: 后端 — 告警引擎启动与定时刷新 (AC: #1)
  - [ ] 4.1 在 `backend/app/main.py` 的 `lifespan()` 中，启动模拟器前调用 `await alarm_engine.load_thresholds()`
  - [ ] 4.2 创建后台定时任务，每 30 秒调用 `alarm_engine.check_version()` 检查阈值版本并按需重新加载
  - [ ] 4.3 在应用关闭时清理定时任务

- [ ] Task 5: 前端 — 适配现有 useAlarm.ts 组合式函数 (AC: #4)
  - [ ] 5.1 确认 `frontend/src/composables/useAlarm.ts` 已有 WebSocket 告警监听、ElNotification 和声音播放逻辑（无需新建组合式函数）
  - [ ] 5.2 在 `frontend/public/sounds/` 目录下创建告警声音文件（alarm_critical.mp3、alarm_major.mp3、alarm_minor.mp3、alarm_info.mp3），或修改 `useAlarm.ts` 的 `handleNewAlarm` 方法添加 Web Audio API 兜底
  - [ ] 5.3 修改 `useAlarm.ts:122-124` 的 `handleAlarmResolve` 方法，添加计数下限保护：`Math.max(0, count - 1)`
  - [ ] 5.4 确认 `useWebSocket` 组合式函数在连接时附带 JWT token（检查 `useWebSocket.ts` 实现）

- [ ] Task 6: 前端 — 告警声音配置组件 (AC: #4)
  - [ ] 5.1 创建 `frontend/src/components/common/AlarmSoundToggle.vue` 声音开关组件
  - [ ] 5.2 使用铃当图标（el-icon Bell），点击切换声音开/关状态
  - [ ] 5.3 状态持久化到 localStorage `alarm_sound_enabled`
  - [ ] 5.4 在 `frontend/src/stores/alarm.ts` 中新增 `soundEnabled` 状态和 `toggleSound()` 方法

- [ ] Task 6: 前端 — 告警声音配置组件 (AC: #4)
  - [ ] 6.1 创建 `frontend/src/components/common/AlarmSoundToggle.vue` 声音开关组件
  - [ ] 6.2 使用铃铛图标（el-icon Bell），点击切换声音开/关状态
  - [ ] 6.3 状态持久化到 localStorage `alarm_sound_enabled`
  - [ ] 6.4 在 `frontend/src/stores/alarm.ts` 中新增 `soundEnabled` 状态和 `toggleSound()` 方法

- [ ] Task 7: 后端测试 (AC: #8)
  - [ ] 7.1 创建 `backend/tests/test_alarm_engine.py`
  - [ ] 7.2 测试 evaluate() — high/high_high 阈值类型触发
  - [ ] 7.3 测试 evaluate() — low/low_low 阈值类型触发
  - [ ] 7.4 测试 evaluate() — equal 阈值类型触发
  - [ ] 7.5 测试风暴防护 — 同一点位 60 秒内第二次越限被抑制
  - [ ] 7.6 测试死区逻辑 — 值在死区范围内不重复触发
  - [ ] 7.7 测试延迟触发 — 首次越限不触发，持续越限超过 delay_seconds 后触发
  - [ ] 7.8 测试大面积告警 — 同一 device_type >50% 点位越限标记为通信异常
  - [ ] 7.9 测试自动恢复 — 值回到安全范围后活动告警自动 resolved

- [ ] Task 8: 前端构建验证
  - [ ] 8.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/engines/__init__.py                    # 新建 — 引擎包
backend/app/engines/alarm_engine.py                # 新建 — 告警引擎核心
backend/app/services/simulator.py                  # 修改 — 替换内联阈值检测为告警引擎调用 + 自动恢复
backend/app/services/websocket.py                  # 修改 — broadcast_alarm 增加 action 字段
backend/app/main.py                                # 修改 — 启动时加载阈值缓存 + 定时刷新
backend/tests/test_alarm_engine.py                 # 新建 — 告警引擎测试
frontend/src/composables/useAlarm.ts               # 修改 — 修复计数下限保护 + 确认声音文件
frontend/src/stores/alarm.ts                       # 修改 — 增加声音开关状态
frontend/src/components/common/AlarmSoundToggle.vue # 新建 — 声音开关组件
frontend/public/sounds/                            # 新建 — 告警声音文件目录
```

### 2. 告警引擎核心实现

创建 `backend/app/engines/__init__.py`：

```python
"""引擎模块 — 告警引擎、联动引擎、数据质量检测"""
```

创建 `backend/app/engines/alarm_engine.py`：

```python
"""
告警引擎 — 内存阈值缓存 + 实时越限检测
Story 5.2: 实时告警触发与通知
"""
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from ..core.database import async_session
from ..models.alarm import AlarmThreshold
from ..models.point import Point

logger = logging.getLogger(__name__)


@dataclass
class ThresholdCache:
    """单条阈值缓存"""
    id: int
    point_id: int
    threshold_type: str       # high_high/high/low/low_low/equal/change
    threshold_value: float
    alarm_level: str          # critical/major/minor/info
    alarm_message: str
    delay_seconds: int
    dead_band: float
    priority: int


@dataclass
class EvaluateResult:
    """单次越限检测结果"""
    threshold_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str
    alarm_message: str
    is_communication_suspect: bool = False  # 疑似通信异常标记


class AlarmEngine:
    """告警引擎 — 核心类"""

    STORM_WINDOW = 60       # 告警风暴抑制窗口（秒）
    MASS_ALARM_RATIO = 0.5  # 大面积告警阈值比例

    def __init__(self):
        # 阈值缓存: {point_id: [ThresholdCache, ...]}
        self._thresholds: Dict[int, List[ThresholdCache]] = defaultdict(list)
        # 当前已知的阈值版本号
        self._known_version: int = -1
        # 风暴防护: {point_id: 上次告警时间戳}
        self._last_alarm_time: Dict[int, float] = {}
        # 延迟触发: {(point_id, threshold_id): 首次越限时间戳}
        self._delay_first_exceed: Dict[Tuple[int, int], float] = {}
        # 死区状态: {(point_id, threshold_id): 是否处于已触发状态}
        self._dead_band_triggered: Dict[Tuple[int, int], bool] = {}
        # 上一次值缓存（用于 change 类型检测）
        self._prev_values: Dict[int, float] = {}
        # 点位 -> device_type 映射
        self._point_device_type: Dict[int, str] = {}
        # device_type -> 点位 ID 集合
        self._device_type_points: Dict[str, set] = defaultdict(set)
        # 本轮越限点位（用于大面积告警检测）
        self._current_cycle_triggered: Dict[str, set] = defaultdict(set)
        self._loaded = False

    async def load_thresholds(self) -> int:
        """从数据库批量加载所有启用的阈值配置到内存"""
        async with async_session() as session:
            result = await session.execute(
                select(AlarmThreshold).where(AlarmThreshold.is_enabled == True)
            )
            thresholds = result.scalars().all()

            points_result = await session.execute(
                select(Point.id, Point.device_type).where(Point.is_enabled == True)
            )
            points = points_result.all()

            # 重建缓存
            new_cache: Dict[int, List[ThresholdCache]] = defaultdict(list)
            for t in thresholds:
                cache_item = ThresholdCache(
                    id=t.id, point_id=t.point_id,
                    threshold_type=t.threshold_type,
                    threshold_value=t.threshold_value or 0,
                    alarm_level=t.alarm_level or "minor",
                    alarm_message=t.alarm_message or "",
                    delay_seconds=t.delay_seconds or 0,
                    dead_band=t.dead_band or 0,
                    priority=t.priority or 0,
                )
                new_cache[t.point_id].append(cache_item)

            # 按 priority 降序排列
            for point_id in new_cache:
                new_cache[point_id].sort(key=lambda x: x.priority, reverse=True)

            self._thresholds = new_cache

            # 重建点位 -> device_type 映射
            self._point_device_type.clear()
            self._device_type_points.clear()
            for point_id, device_type in points:
                if device_type:
                    self._point_device_type[point_id] = device_type
                    self._device_type_points[device_type].add(point_id)

            self._loaded = True
            count = sum(len(v) for v in new_cache.values())
            logger.info("告警引擎: 已加载 %d 条阈值配置（覆盖 %d 个点位）", count, len(new_cache))
            return count

    async def check_version(self) -> bool:
        """检查阈值版本号，版本变化时重新加载"""
        try:
            from ..api.v1.threshold import _threshold_version
            if _threshold_version != self._known_version:
                old_ver = self._known_version
                await self.load_thresholds()
                self._known_version = _threshold_version
                logger.info("告警引擎: 阈值版本 %d -> %d，已重新加载", old_ver, _threshold_version)
                return True
        except Exception as e:
            logger.warning("告警引擎: 检查版本失败: %s", e)
        return False

    def evaluate(self, point_id: int, value: float, point_type: str = "AI") -> List[EvaluateResult]:
        """检测点位值是否越限，返回触发的告警列表"""
        if not self._loaded:
            return []

        cached = self._thresholds.get(point_id)
        if not cached:
            self._prev_values[point_id] = value
            return []

        # 风暴防护检查
        if self._check_storm(point_id):
            self._prev_values[point_id] = value
            return []

        results: List[EvaluateResult] = []
        now = time.time()

        for tc in cached:
            triggered = self._check_threshold(point_id, value, tc, now)
            if triggered:
                results.append(EvaluateResult(
                    threshold_id=tc.id,
                    threshold_type=tc.threshold_type,
                    threshold_value=tc.threshold_value,
                    alarm_level=tc.alarm_level,
                    alarm_message=tc.alarm_message or f"点位 {point_id} {tc.threshold_type} 告警",
                ))

        # 更新风暴防护时间戳
        if results:
            self._last_alarm_time[point_id] = now
            device_type = self._point_device_type.get(point_id)
            if device_type:
                self._current_cycle_triggered[device_type].add(point_id)

        self._prev_values[point_id] = value
        return results

    def _check_threshold(self, point_id: int, value: float, tc: ThresholdCache, now: float) -> bool:
        """检测单条阈值是否越限（含死区和延迟逻辑）"""
        key = (point_id, tc.id)
        exceeded = False

        # 1. 判断是否越限
        if tc.threshold_type in ("high_high", "high"):
            exceeded = value > tc.threshold_value
        elif tc.threshold_type in ("low", "low_low"):
            exceeded = value < tc.threshold_value
        elif tc.threshold_type == "equal":
            exceeded = abs(value - tc.threshold_value) < 0.001
        elif tc.threshold_type == "change":
            prev = self._prev_values.get(point_id)
            if prev is not None:
                exceeded = abs(value - prev) > tc.threshold_value
        else:
            return False

        # 2. 死区逻辑
        if tc.dead_band > 0:
            was_triggered = self._dead_band_triggered.get(key, False)
            if was_triggered:
                if tc.threshold_type in ("high_high", "high"):
                    recovered = value < (tc.threshold_value - tc.dead_band)
                elif tc.threshold_type in ("low", "low_low"):
                    recovered = value > (tc.threshold_value + tc.dead_band)
                else:
                    recovered = not exceeded
                if recovered:
                    self._dead_band_triggered[key] = False
                return False  # 已触发状态下不重复触发
            elif exceeded:
                self._dead_band_triggered[key] = True
            else:
                return False

        if not exceeded:
            self._delay_first_exceed.pop(key, None)
            return False

        # 3. 延迟触发逻辑
        if tc.delay_seconds > 0:
            first_time = self._delay_first_exceed.get(key)
            if first_time is None:
                self._delay_first_exceed[key] = now
                return False
            elif (now - first_time) < tc.delay_seconds:
                return False
            else:
                self._delay_first_exceed.pop(key, None)
                return True
        return True

    def _check_storm(self, point_id: int) -> bool:
        """告警风暴防护：同一点位 60 秒内不重复产生告警"""
        last_time = self._last_alarm_time.get(point_id)
        if last_time is None:
            return False
        return (time.time() - last_time) < self.STORM_WINDOW

    def check_mass_alarm(self, device_type: str) -> bool:
        """大面积告警检测：同一 device_type 下 >50% 点位同时越限"""
        total_points = self._device_type_points.get(device_type, set())
        triggered_points = self._current_cycle_triggered.get(device_type, set())
        if not total_points:
            return False
        ratio = len(triggered_points) / len(total_points)
        if ratio > self.MASS_ALARM_RATIO:
            logger.warning(
                "大面积告警: device_type=%s, 越限 %d/%d (%.1f%%), 疑似通信异常",
                device_type, len(triggered_points), len(total_points), ratio * 100
            )
            return True
        return False

    def reset_cycle_stats(self):
        """重置本轮统计（每个采集周期结束后调用）"""
        self._current_cycle_triggered.clear()


# 全局单例
alarm_engine = AlarmEngine()
```

### 3. 集成告警引擎到模拟器

在 `backend/app/services/simulator.py` 中，替换第 119-161 行的内联阈值检测逻辑：

**新增导入**（文件顶部）：

```python
from ..engines.alarm_engine import alarm_engine
```

**替换 `_simulate_point()` 中的告警检测段**（原第 119-161 行）：

```python
        # 检查告警（使用告警引擎替代内联检测）
        status = "normal"
        alarms_to_create = []

        if point.point_type in ["AI", "DI"]:
            triggered_list = alarm_engine.evaluate(point.id, new_value, point.point_type)

            if triggered_list:
                status = "alarm"
                # 大面积告警检测
                device_type = point.device_type
                is_comm_suspect = alarm_engine.check_mass_alarm(device_type) if device_type else False

                for triggered in triggered_list:
                    # 检查是否已有活动告警（同一点位+同一阈值）
                    existing = await session.execute(
                        select(Alarm).where(
                            Alarm.point_id == point.id,
                            Alarm.threshold_id == triggered.threshold_id,
                            Alarm.status == "active"
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # 已有活动告警，跳过

                    alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                    alarm_msg = triggered.alarm_message or f"{point.point_name} 告警"
                    if is_comm_suspect:
                        alarm_msg = f"[疑似通信异常] {alarm_msg}"

                    alarm = Alarm(
                        alarm_no=alarm_no,
                        point_id=point.id,
                        threshold_id=triggered.threshold_id,
                        alarm_level=triggered.alarm_level,
                        alarm_type="communication" if is_comm_suspect else "threshold",
                        alarm_message=alarm_msg,
                        trigger_value=new_value,
                        threshold_value=triggered.threshold_value,
                    )
                    alarms_to_create.append(alarm)
```

**在告警创建后添加 WebSocket 推送和 Redis 统计**（在 `session.add(alarm)` 之后）：

```python
        # 创建告警记录并广播
        for alarm in alarms_to_create:
            session.add(alarm)

        if alarms_to_create:
            await session.flush()  # flush 获取告警 ID

            for alarm in alarms_to_create:
                # WebSocket 广播告警到前端
                try:
                    await ws_manager.broadcast_alarm({
                        "id": alarm.id,
                        "alarm_no": alarm.alarm_no,
                        "point_id": alarm.point_id,
                        "point_code": point.point_code,
                        "point_name": point.point_name,
                        "alarm_level": alarm.alarm_level,
                        "alarm_type": alarm.alarm_type,
                        "alarm_message": alarm.alarm_message,
                        "trigger_value": alarm.trigger_value,
                        "threshold_value": alarm.threshold_value,
                        "status": "active",
                        "created_at": datetime.now().isoformat(),
                    })
                except Exception as e:
                    logger.warning("WebSocket 告警推送失败: %s", e)

                # Redis 告警统计递增
                try:
                    if redis_service.is_available:
                        key = f"alarm:stats:{alarm.alarm_level}"
                        current = await redis_service.get(key)
                        count = int(current or 0) + 1
                        await redis_service.set(key, str(count), ttl=86400)
                except Exception:
                    pass  # Redis 不可用时静默失败
```

**在采集周期结束后重置统计**（`start()` 方法的循环末尾）：

```python
            # 本轮采集结束，重置大面积告警统计
            alarm_engine.reset_cycle_stats()
```

### 4. 告警引擎启动与定时刷新

修改 `backend/app/main.py` 的 `lifespan()` 函数：

```python
from .engines.alarm_engine import alarm_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await init_db()
    await init_default_data()
    await init_default_configs()
    await seed_power_devices()
    await seed_cooling_devices()

    # 连接 Redis 缓存
    if settings.redis_enabled:
        await redis_service.connect(settings.redis_url)

    # 加载告警引擎阈值缓存
    await alarm_engine.load_thresholds()

    # 启动数据模拟器
    simulator_task = asyncio.create_task(simulator.start(interval=5))

    # 启动告警引擎定时刷新（每 30 秒检查阈值版本）
    async def _alarm_engine_refresh_loop():
        while True:
            await asyncio.sleep(30)
            try:
                await alarm_engine.check_version()
            except Exception as e:
                logger.warning("告警引擎刷新失败: %s", e)

    refresh_task = asyncio.create_task(_alarm_engine_refresh_loop())

    print(f"{'='*50}")
    print(f"{settings.app_name} v{settings.app_version} 启动成功")
    print(f"{'='*50}")
    print("数据模拟器已启动，每5秒采集一次")
    print("告警引擎已加载阈值缓存")

    yield

    # 停止模拟器和刷新任务
    simulator.stop()
    simulator_task.cancel()
    refresh_task.cancel()
    await redis_service.close()
    print("应用关闭")
```

### 5. 告警通知组合式函数

创建 `frontend/src/composables/useAlarmNotification.ts`：

```typescript
/**
 * 告警通知组合式函数 — WebSocket 监听 + ElNotification + 声音提示
 * Story 5.2: 实时告警触发与通知
 */
import { ElNotification } from 'element-plus'
import { useAlarmStore } from '@/stores/alarm'

// 告警级别中文映射
const levelLabelMap: Record<string, string> = {
  critical: '紧急',
  major: '重要',
  minor: '次要',
  info: '提示',
}

// 告警级别对应 ElNotification type
const levelTypeMap: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
  critical: 'error',
  major: 'warning',
  minor: 'warning',
  info: 'info',
}

let audioContext: AudioContext | null = null

function playAlarmSound(level: string) {
  const soundEnabled = localStorage.getItem('alarm_sound_enabled') !== 'false'
  if (!soundEnabled) return

  try {
    if (!audioContext) {
      audioContext = new AudioContext()
    }
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)

    // 紧急告警：高频急促，其他：中频短促
    if (level === 'critical') {
      oscillator.frequency.value = 880
      gainNode.gain.value = 0.3
      oscillator.start()
      oscillator.stop(audioContext.currentTime + 0.5)
    } else {
      oscillator.frequency.value = 660
      gainNode.gain.value = 0.2
      oscillator.start()
      oscillator.stop(audioContext.currentTime + 0.3)
    }
  } catch (e) {
    console.warn('告警提示音播放失败:', e)
  }
}

export function useAlarmNotification() {
  const alarmStore = useAlarmStore()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0

  function connect() {
    const token = localStorage.getItem('token') || ''
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const wsUrl = `${protocol}//${host}:8080/ws/alarms?token=${token}`

    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[告警通道] WebSocket 已连接')
        reconnectAttempts = 0
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'alarm' && msg.data) {
            handleAlarm(msg.data)
          }
        } catch (e) {
          console.warn('[告警通道] 消息解析失败:', e)
        }
      }

      ws.onclose = () => {
        console.log('[告警通道] WebSocket 断开，准备重连...')
        scheduleReconnect()
      }

      ws.onerror = (err) => {
        console.error('[告警通道] WebSocket 错误:', err)
      }
    } catch (e) {
      console.error('[告警通道] WebSocket 连接失败:', e)
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function handleAlarm(data: any) {
    // 添加到 store
    alarmStore.addAlarm({
      id: data.id,
      point_code: data.point_code || '',
      point_name: data.point_name || '',
      alarm_level: data.alarm_level,
      alarm_message: data.alarm_message,
      status: data.status || 'active',
      created_at: data.created_at || new Date().toISOString(),
    })

    // 显示通知
    const level = data.alarm_level || 'info'
    const label = levelLabelMap[level] || level
    const duration = (level === 'critical' || level === 'major') ? 0 : 10000

    ElNotification({
      title: `${label}告警`,
      message: `${data.point_name || ''}: ${data.alarm_message || ''}`,
      type: levelTypeMap[level] || 'info',
      duration,
      position: 'top-right',
    })

    // 播放提示音
    playAlarmSound(level)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  return { connect, disconnect }
}
```

### 6. 告警声音配置组件

创建 `frontend/src/components/common/AlarmSoundToggle.vue`：

```vue
<template>
  <el-tooltip :content="soundEnabled ? '告警声音：开' : '告警声音：关'" placement="bottom">
    <el-button :icon="soundEnabled ? Bell : MuteFilled" circle size="small"
      @click="toggleSound" :type="soundEnabled ? '' : 'info'" />
  </el-tooltip>
</template>

<script setup lang="ts">
import { Bell, MuteFilled } from '@element-plus/icons-vue'
import { useAlarmStore } from '@/stores/alarm'

const alarmStore = useAlarmStore()
const soundEnabled = computed(() => alarmStore.soundEnabled)

function toggleSound() {
  alarmStore.toggleSound()
}
</script>
```

### 7. 告警 Store 增强

修改 `frontend/src/stores/alarm.ts`，新增声音控制状态：

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Alarm {
  id: number
  point_code: string
  point_name: string
  alarm_level: string
  alarm_message: string
  status: string
  created_at: string
}

export const useAlarmStore = defineStore('alarm', () => {
  const activeAlarms = ref<Alarm[]>([])
  const alarmCount = ref({
    critical: 0, major: 0, minor: 0, info: 0, total: 0
  })
  // 声音开关（从 localStorage 读取，默认开启）
  const soundEnabled = ref(localStorage.getItem('alarm_sound_enabled') !== 'false')

  function addAlarm(alarm: Alarm) {
    // 去重：相同 id 不重复添加
    if (alarm.id && activeAlarms.value.some(a => a.id === alarm.id)) return
    activeAlarms.value.unshift(alarm)
    // 限制列表长度，防止内存溢出
    if (activeAlarms.value.length > 200) {
      activeAlarms.value = activeAlarms.value.slice(0, 200)
    }
    updateCount()
  }

  function removeAlarm(id: number) {
    activeAlarms.value = activeAlarms.value.filter(a => a.id !== id)
    updateCount()
  }

  function updateCount() {
    alarmCount.value = {
      critical: activeAlarms.value.filter(a => a.alarm_level === 'critical').length,
      major: activeAlarms.value.filter(a => a.alarm_level === 'major').length,
      minor: activeAlarms.value.filter(a => a.alarm_level === 'minor').length,
      info: activeAlarms.value.filter(a => a.alarm_level === 'info').length,
      total: activeAlarms.value.length
    }
  }

  function toggleSound() {
    soundEnabled.value = !soundEnabled.value
    localStorage.setItem('alarm_sound_enabled', String(soundEnabled.value))
  }

  return {
    activeAlarms, alarmCount, soundEnabled,
    addAlarm, removeAlarm, toggleSound,
  }
})
```

### 8. 后端测试

创建 `backend/tests/test_alarm_engine.py`：

```python
"""告警引擎单元测试 — Story 5.2"""
import time
import pytest
from app.engines.alarm_engine import AlarmEngine, ThresholdCache, EvaluateResult


@pytest.fixture
def engine():
    """创建测试用告警引擎"""
    e = AlarmEngine()
    e._loaded = True
    return e


@pytest.fixture
def sample_thresholds():
    """示例 4 级阈值配置（点位 100）"""
    return [
        ThresholdCache(id=1, point_id=100, threshold_type="high_high",
                       threshold_value=50.0, alarm_level="critical",
                       alarm_message="温度超高", delay_seconds=0, dead_band=0, priority=4),
        ThresholdCache(id=2, point_id=100, threshold_type="high",
                       threshold_value=40.0, alarm_level="major",
                       alarm_message="温度偏高", delay_seconds=0, dead_band=0, priority=3),
        ThresholdCache(id=3, point_id=100, threshold_type="low",
                       threshold_value=10.0, alarm_level="minor",
                       alarm_message="温度偏低", delay_seconds=0, dead_band=0, priority=2),
        ThresholdCache(id=4, point_id=100, threshold_type="low_low",
                       threshold_value=5.0, alarm_level="info",
                       alarm_message="温度超低", delay_seconds=0, dead_band=0, priority=1),
    ]


class TestEvaluate:
    """测试阈值检测"""

    def test_high_high_trigger(self, engine, sample_thresholds):
        """值超过 high_high 阈值应触发 critical 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 55.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "critical" in levels

    def test_high_trigger(self, engine, sample_thresholds):
        """值超过 high 阈值应触发 major 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 42.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "major" in levels

    def test_low_trigger(self, engine, sample_thresholds):
        """值低于 low 阈值应触发 minor 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 8.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "minor" in levels

    def test_low_low_trigger(self, engine, sample_thresholds):
        """值低于 low_low 阈值应触发 info 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 3.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "info" in levels

    def test_normal_no_trigger(self, engine, sample_thresholds):
        """正常值不应触发告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 25.0, "AI")
        assert len(results) == 0

    def test_equal_trigger(self, engine):
        """equal 类型阈值检测"""
        engine._thresholds = {200: [
            ThresholdCache(id=10, point_id=200, threshold_type="equal",
                           threshold_value=1.0, alarm_level="major",
                           alarm_message="状态异常", delay_seconds=0, dead_band=0, priority=3),
        ]}
        results = engine.evaluate(200, 1.0, "DI")
        assert len(results) == 1
        assert results[0].alarm_level == "major"


class TestStormProtection:
    """测试风暴防护"""

    def test_suppress_within_60s(self, engine, sample_thresholds):
        """同一点位 60 秒内第二次越限应被抑制"""
        engine._thresholds = {100: sample_thresholds}
        results1 = engine.evaluate(100, 55.0, "AI")
        assert len(results1) > 0
        # 立即再次检测 — 应被抑制
        results2 = engine.evaluate(100, 56.0, "AI")
        assert len(results2) == 0

    def test_allow_after_60s(self, engine, sample_thresholds):
        """60 秒后应允许再次触发"""
        engine._thresholds = {100: sample_thresholds}
        results1 = engine.evaluate(100, 55.0, "AI")
        assert len(results1) > 0
        # 模拟 61 秒后
        engine._last_alarm_time[100] = time.time() - 61
        results2 = engine.evaluate(100, 55.0, "AI")
        assert len(results2) > 0


class TestDeadBand:
    """测试死区回差"""

    def test_dead_band_no_retrigger(self, engine):
        """触发后值仍在死区范围内不应重复触发"""
        engine._thresholds = {300: [
            ThresholdCache(id=20, point_id=300, threshold_type="high",
                           threshold_value=40.0, alarm_level="major",
                           alarm_message="温度偏高", delay_seconds=0, dead_band=2.0, priority=3),
        ]}
        # 首次越限触发
        results1 = engine.evaluate(300, 45.0, "AI")
        assert len(results1) == 1
        # 清除风暴防护以测试死区
        engine._last_alarm_time.clear()
        # 值仍高于阈值但在死区内 — 不应触发
        results2 = engine.evaluate(300, 41.0, "AI")
        assert len(results2) == 0

    def test_dead_band_recovery_retrigger(self, engine):
        """值回到安全区域后再次越限应触发"""
        engine._thresholds = {300: [
            ThresholdCache(id=20, point_id=300, threshold_type="high",
                           threshold_value=40.0, alarm_level="major",
                           alarm_message="温度偏高", delay_seconds=0, dead_band=2.0, priority=3),
        ]}
        engine.evaluate(300, 45.0, "AI")
        engine._last_alarm_time.clear()
        # 值回到安全区域（< 40 - 2 = 38）
        engine.evaluate(300, 37.0, "AI")
        engine._last_alarm_time.clear()
        # 再次越限 — 应触发
        results = engine.evaluate(300, 45.0, "AI")
        assert len(results) == 1


class TestDelaySeconds:
    """测试延迟触发"""

    def test_delay_not_trigger_immediately(self, engine):
        """首次越限不应立即触发（开始计时）"""
        engine._thresholds = {400: [
            ThresholdCache(id=30, point_id=400, threshold_type="high",
                           threshold_value=40.0, alarm_level="major",
                           alarm_message="温度偏高", delay_seconds=10, dead_band=0, priority=3),
        ]}
        results = engine.evaluate(400, 45.0, "AI")
        assert len(results) == 0
        assert (400, 30) in engine._delay_first_exceed

    def test_delay_trigger_after_elapsed(self, engine):
        """持续越限超过 delay_seconds 后应触发"""
        engine._thresholds = {400: [
            ThresholdCache(id=30, point_id=400, threshold_type="high",
                           threshold_value=40.0, alarm_level="major",
                           alarm_message="温度偏高", delay_seconds=10, dead_band=0, priority=3),
        ]}
        engine.evaluate(400, 45.0, "AI")
        # 模拟 11 秒后
        engine._delay_first_exceed[(400, 30)] = time.time() - 11
        results = engine.evaluate(400, 45.0, "AI")
        assert len(results) == 1


class TestMassAlarm:
    """测试大面积告警检测"""

    def test_mass_alarm_detected(self, engine):
        """超过 50% 点位越限应检测为大面积告警"""
        engine._device_type_points = {"TH": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        engine._current_cycle_triggered = {"TH": {1, 2, 3, 4, 5, 6}}
        assert engine.check_mass_alarm("TH") is True

    def test_mass_alarm_not_detected(self, engine):
        """低于 50% 点位越限不应检测为大面积告警"""
        engine._device_type_points = {"TH": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        engine._current_cycle_triggered = {"TH": {1, 2, 3}}
        assert engine.check_mass_alarm("TH") is False

    def test_mass_alarm_zero_total(self, engine):
        """无点位时不应检测为大面积告警"""
        assert engine.check_mass_alarm("UNKNOWN") is False
```

### 9. 关键约束

- **不新增数据库表**: 复用现有 Alarm 和 AlarmThreshold 表
- **不破坏现有 API**: 所有告警 CRUD API 保持不变，告警引擎仅影响告警创建流程
- **内存缓存一致性**: 通过 Story 5.1 的版本号机制保证阈值缓存与数据库同步，30 秒检查间隔
- **风暴防护窗口**: 60 秒，硬编码常量（后续可改为配置）
- **大面积告警阈值**: 50%，硬编码常量
- **WebSocket 广播**: 复用现有 `ws_manager.broadcast_alarm()` 方法，消息格式 `{type: "alarm", data: {...}}`
- **Redis 降级**: Redis 不可用时告警统计更新静默失败，不影响告警创建和 WebSocket 推送
- **自动导入**: 前端项目使用 unplugin-auto-import，Vue API（ref, reactive, computed, onMounted）无需手动 import
- **声音播放**: 使用 Web Audio API 生成提示音，无需额外音频文件。首次播放需要用户交互（浏览器策略），通过点击铃铛按钮触发
- **测试模式**: 告警引擎测试为纯内存测试，不依赖数据库，直接操作 `_thresholds` 字典

### References

- [Source: models/alarm.py] Alarm、AlarmThreshold 模型定义（alarm_no, point_id, threshold_id, alarm_level, alarm_type, trigger_value）
- [Source: services/simulator.py] 数据模拟器（当前内联告警检测逻辑第 119-161 行，需替换）
- [Source: services/websocket.py] WebSocket 连接管理器（broadcast_alarm 方法，alarms 通道）
- [Source: api/v1/threshold.py] 阈值版本号机制（_threshold_version, _increment_version, GET /version）
- [Source: api/v1/alarm.py] 告警 CRUD API（列表、确认、解决、统计、趋势）
- [Source: core/redis.py] Redis 缓存服务（优雅降级模式，get/set/is_available）
- [Source: stores/alarm.ts] 前端告警 Pinia Store（activeAlarms, alarmCount, addAlarm, removeAlarm）
- [Source: composables/useAlarm.ts] 现有告警组合式函数（handleNewAlarm, WebSocket 监听逻辑参考）
- [Source: composables/useSound.ts] 现有声音播放组合式函数（playAlarm, toggleMute 参考）
- [Source: composables/useWebSocket.ts] WebSocket 组合式函数（连接管理、消息订阅参考）
- [Source: api/modules/alarm.ts] 前端告警 API（AlarmInfo, AlarmCount 类型定义）
- [Architecture: 10.2] 数据流性能路径（MQTT -> Redis -> 告警引擎 -> WebSocket）

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

