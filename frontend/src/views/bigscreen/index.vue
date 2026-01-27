<!-- frontend/src/views/bigscreen/index.vue -->
<template>
  <div class="bigscreen-container">
    <!-- Three.js 3D场景 (仅在3D模式下显示) -->
    <ThreeScene v-if="viewMode === '3d'" ref="threeSceneRef" @vue:mounted="onSceneReady">
      <template v-if="isSceneReady">
        <DataCenterModel />
        <HeatmapOverlay />
        <CabinetLabels />
        <AlarmBubbles />
      </template>
    </ThreeScene>

    <!-- 2D平面图 (仅在2D模式下显示) -->
    <Floor2DView
      v-if="viewMode === '2d'"
      :mapData="floorMapData2D"
      @elementClick="handleFloorElementClick"
    />

    <!-- 悬浮面板层 -->
    <div class="overlay-panels">
      <!-- 顶部状态栏 -->
      <div class="top-bar">
        <div class="back-btn" @click="goBack">
          <el-icon><Back /></el-icon>
        </div>
        <div class="time">{{ currentTime }}</div>
        <div class="title">XX数据中心机房</div>
        <div class="mode-selector">
          <el-dropdown @command="handleModeChange">
            <span class="mode-label">
              {{ modeLabels[store.mode] }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="command">指挥中心</el-dropdown-item>
                <el-dropdown-item command="operation">运维模式</el-dropdown-item>
                <el-dropdown-item command="showcase">展示模式</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="fullscreen-btn" @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </div>
        <ThemeSelector :showLabel="false" />
        <div class="kpi pue">
          <span class="label">PUE</span>
          <span class="value">{{ store.energy.pue.toFixed(2) }}</span>
        </div>
        <div class="kpi alarm" :class="{ 'has-alarm': store.alarmCount > 0 }">
          <el-icon><Bell /></el-icon>
          <span class="value">{{ store.alarmCount }}</span>
        </div>
      </div>

      <!-- 设备详情面板 -->
      <DeviceDetailPanel
        @locate="handleLocateDevice"
        @viewHistory="handleViewHistory"
      />

      <!-- 左侧环境面板 -->
      <LeftPanel
        v-if="store.modeConfig.showAllPanels && store.panelStates.leftPanel?.visible !== false"
        @locateAlarm="handleLocateAlarm"
        @viewAllAlarms="handleViewAllAlarms"
        @navigate="handleNavigate"
      />

      <!-- 右侧能耗面板 -->
      <RightPanel
        v-if="store.modeConfig.showAllPanels && store.panelStates.rightPanel?.visible !== false"
        @navigate="handleNavigate"
      />

      <!-- 楼层选择器 -->
      <FloorSelector
        v-if="store.panelStates.floorSelector?.visible !== false"
        v-model="currentFloor"
        :mode="viewMode"
        @update:mode="viewMode = $event"
        @floorChange="handleFloorChange"
      />

      <!-- 底部控制栏 -->
      <div class="bottom-bar">
        <div class="layer-toggles">
          <span class="label">图层:</span>
          <el-checkbox v-model="store.layers.heatmap" @change="() => store.toggleLayer('heatmap')">
            温度
          </el-checkbox>
          <el-checkbox v-model="store.layers.status" @change="() => store.toggleLayer('status')">
            状态
          </el-checkbox>
          <el-checkbox v-model="store.layers.power" @change="() => store.toggleLayer('power')">
            功率
          </el-checkbox>
          <el-checkbox v-model="store.layers.airflow" @change="() => store.toggleLayer('airflow')">
            气流
          </el-checkbox>
        </div>
        <div class="panel-toggles">
          <span class="label">面板:</span>
          <el-checkbox
            :model-value="store.panelStates.leftPanel?.visible !== false"
            @change="store.togglePanelVisible('leftPanel')"
          >
            环境
          </el-checkbox>
          <el-checkbox
            :model-value="store.panelStates.rightPanel?.visible !== false"
            @change="store.togglePanelVisible('rightPanel')"
          >
            能耗
          </el-checkbox>
          <el-checkbox
            :model-value="store.panelStates.floorSelector?.visible !== false"
            @change="store.togglePanelVisible('floorSelector')"
          >
            楼层
          </el-checkbox>
          <el-button size="small" @click="store.resetPanelStates()">重置</el-button>
        </div>
        <div class="view-presets">
          <span class="label">视角:</span>
          <el-button size="small" @click="setCamera('overview')">全景</el-button>
          <el-button size="small" @click="setCamera('topDown')">俯视</el-button>
        </div>
        <div class="tour-control" v-if="store.mode === 'showcase'">
          <el-button
            size="small"
            :type="autoTour?.isTouring.value ? 'primary' : 'default'"
            @click="handleToggleTour"
          >
            <el-icon>
              <VideoPause v-if="autoTour?.isTouring.value && !autoTour?.isPaused.value" />
              <VideoPlay v-else />
            </el-icon>
            {{ autoTour?.isTouring.value ? (autoTour?.isPaused.value ? '继续' : '暂停') : '巡航' }}
          </el-button>
          <span class="tour-label" v-if="autoTour?.currentLabel.value">
            {{ autoTour?.currentLabel.value }}
          </span>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="store.loading" class="loading-overlay">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <!-- 右键菜单 -->
      <ContextMenu
        :visible="contextMenuVisible"
        :x="contextMenuX"
        :y="contextMenuY"
        :items="contextMenuItems"
        @close="contextMenuVisible = false"
        @select="handleContextMenuSelect"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, type ShallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, FullScreen, Bell, Loading, VideoPlay, VideoPause, Back } from '@element-plus/icons-vue'
import * as THREE from 'three'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  ThreeScene,
  DataCenterModel,
  CabinetLabels,
  HeatmapOverlay,
  AlarmBubbles,
  DeviceDetailPanel
} from '@/components/bigscreen'
import { LeftPanel, RightPanel } from '@/components/bigscreen/panels'
import FloorSelector from '@/components/bigscreen/FloorSelector.vue'
import Floor2DView from '@/components/bigscreen/Floor2DView.vue'
import type { MapData2D } from '@/api/modules/floorMap'
import type { BigscreenAlarm } from '@/types/bigscreen'
import { useBigscreenStore } from '@/stores/bigscreen'
import { getDefaultLayout } from '@/api/modules/bigscreen'
import { setupBasicScene } from '@/utils/three/sceneSetup'
import { useRaycaster } from '@/composables/bigscreen/useRaycaster'
import { useCameraAnimation } from '@/composables/bigscreen/useCameraAnimation'
import { useSceneMode } from '@/composables/bigscreen/useSceneMode'
import { useAutoTour } from '@/composables/bigscreen/useAutoTour'
import { useBigscreenData } from '@/composables/bigscreen/useBigscreenData'
import { useScreenAdapt } from '@/composables/bigscreen/useScreenAdapt'
import { useEntranceAnimation } from '@/composables/bigscreen/useEntranceAnimation'
import { useKeyboardShortcuts } from '@/composables/bigscreen/useKeyboardShortcuts'
import { useTheme } from '@/composables/bigscreen/useTheme'
import { ContextMenu, ThemeSelector, type ContextMenuItem } from '@/components/bigscreen/ui'
import type { SceneMode } from '@/types/bigscreen'

const store = useBigscreenStore()
const router = useRouter()
const threeSceneRef = ref<InstanceType<typeof ThreeScene> | null>(null)
const isSceneReady = ref(false)

// 楼层选择状态
const currentFloor = ref('F1')
const viewMode = ref<'2d' | '3d'>('3d')
const floorMapData2D = ref<MapData2D | null>(null)

// 屏幕自适应
const screenAdapt = useScreenAdapt({
  designWidth: 1920,
  designHeight: 1080
})

// 入场动画
const entranceAnimation = useEntranceAnimation({
  duration: 0.6,
  staggerDelay: 0.1
})

// 主题管理
const { currentThemeName, setTheme } = useTheme()

// 右键菜单状态
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuItems = computed(() => [
  { key: 'overview', label: '全景视角', icon: 'View' },
  { key: 'topDown', label: '俯视视角', icon: 'TopRight' },
  { key: 'divider1', divider: true },
  { key: 'heatmap', label: store.layers.heatmap ? '关闭热力图' : '开启热力图', icon: 'Sunny' },
  { key: 'fullscreen', label: document.fullscreenElement ? '退出全屏' : '全屏显示', icon: 'FullScreen' }
])

// 当前时间
const currentTime = ref('')
let timeTimer: number | null = null

// 模式标签
const modeLabels: Record<SceneMode, string> = {
  command: '指挥中心',
  operation: '运维模式',
  showcase: '展示模式'
}

// Raycaster (点击检测)
const containerRef = ref<HTMLElement | null>(null)

// 相机动画
let cameraAnimation: ReturnType<typeof useCameraAnimation> | null = null

// 场景模式
let sceneMode: ReturnType<typeof useSceneMode> | null = null

// 自动巡航
let autoTour: ReturnType<typeof useAutoTour> | null = null

// 数据刷新
const bigscreenData = useBigscreenData({
  refreshInterval: 5000,
  enableRealtime: true
})

// 最后更新时间
const lastUpdateTime = computed(() => {
  if (!bigscreenData.lastUpdate.value) return '--'
  return bigscreenData.lastUpdate.value.toLocaleTimeString('zh-CN')
})

// 更新时间
function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 场景就绪回调
async function onSceneReady() {
  const sceneComponent = threeSceneRef.value
  if (sceneComponent?.scene) {
    // 加载布局配置
    try {
      const layout = await getDefaultLayout()
      store.setLayout(layout)
    } catch (e) {
      console.error('Failed to load layout:', e)
    }

    // 设置基础场景
    setupBasicScene(sceneComponent.scene, {
      showGrid: true,
      showAxes: false,
      floorSize: 100
    })
    isSceneReady.value = true

    // 初始化相机动画
    cameraAnimation = useCameraAnimation(
      sceneComponent.camera as unknown as ShallowRef<THREE.PerspectiveCamera | null>,
      sceneComponent.controls as unknown as ShallowRef<OrbitControls | null>
    )

    // 初始化场景模式
    sceneMode = useSceneMode(
      sceneComponent.controls as unknown as ShallowRef<OrbitControls | null>,
      sceneComponent.camera as unknown as ShallowRef<THREE.PerspectiveCamera | null>
    )
    sceneMode.initCameraAnimation()
    sceneMode.applyModeToControls(store.mode)

    // 初始化自动巡航
    autoTour = useAutoTour(
      sceneComponent.camera as unknown as ShallowRef<THREE.PerspectiveCamera | null>,
      sceneComponent.controls as unknown as ShallowRef<OrbitControls | null>
    )

    // 获取容器引用用于 raycaster
    const canvas = sceneComponent.renderer?.domElement
    if (canvas?.parentElement) {
      containerRef.value = canvas.parentElement
    }

    // 数据现在由 useBigscreenData 自动获取真实API数据

    // 播放入场动画
    setTimeout(() => {
      entranceAnimation.playEntrance()
    }, 100)
  }
}

// 初始化 Raycaster（场景就绪后）
watch(isSceneReady, (ready) => {
  if (ready && containerRef.value && threeSceneRef.value) {
    useRaycaster(
      containerRef,
      threeSceneRef.value.camera as unknown as ShallowRef<THREE.PerspectiveCamera | null>,
      threeSceneRef.value.scene as unknown as ShallowRef<THREE.Scene | null>
    )
  }
})

// 监听模式变化，调整刷新频率
watch(() => store.mode, () => {
  const interval = store.modeConfig.refreshInterval
  bigscreenData.setRefreshInterval(interval)
})

// 切换模式
async function handleModeChange(mode: SceneMode) {
  // 如果正在巡航，先停止
  if (autoTour?.isTouring.value) {
    autoTour.stopTour()
  }

  if (sceneMode) {
    await sceneMode.switchMode(mode)
  } else {
    store.setMode(mode)
  }

  // 如果切换到展示模式，自动开始巡航
  if (mode === 'showcase') {
    setTimeout(() => {
      autoTour?.startTour()
    }, 500)
  }
}

// 切换全屏
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 返回主系统 - 始终关闭当前标签页，不影响主界面
function goBack() {
  // 尝试关闭当前窗口/标签页
  // 浏览器只允许脚本关闭由脚本打开的窗口
  window.close()

  // 如果关闭失败（例如用户直接在地址栏输入URL打开），
  // 使用 location.href 而非 router.push，避免影响 Vue 状态
  setTimeout(() => {
    // 如果代码还在执行，说明窗口没有被关闭
    window.location.href = '/dashboard'
  }, 100)
}

// 设置相机预设视角（使用动画）
function setCamera(preset: string) {
  const presetConfig = store.cameraPresets[preset]
  if (!presetConfig || !cameraAnimation) return

  cameraAnimation.flyToPreset(presetConfig)
}

// 定位设备
function handleLocateDevice(deviceId: string) {
  if (!cameraAnimation || !threeSceneRef.value?.scene) return

  cameraAnimation.flyToDevice(deviceId, threeSceneRef.value.scene, {
    distance: 8,
    height: 4,
    duration: 1.2
  })
}

// 查看历史（占位，后续实现）
function handleViewHistory(deviceId: string) {
  console.log('View history for:', deviceId)
  // TODO: 打开历史数据弹窗
}

// 定位告警设备
function handleLocateAlarm(alarm: BigscreenAlarm) {
  store.selectDevice(alarm.deviceId)
  handleLocateDevice(alarm.deviceId)
}

// 查看全部告警
function handleViewAllAlarms() {
  handleNavigate('/alarms')
}

// 导航到主界面指定页面 - 始终在新标签页打开
function handleNavigate(path: string) {
  // 构建完整URL
  const baseUrl = window.location.origin
  const fullUrl = `${baseUrl}${path}`

  // 始终在新标签页打开
  window.open(fullUrl, '_blank')
}

// 切换巡航状态
function handleToggleTour() {
  autoTour?.toggleTour()
}

// 处理右键菜单选择
function handleContextMenuSelect(item: ContextMenuItem) {
  const key = item.action
  switch (key) {
    case 'overview':
    case 'topDown':
      setCamera(key)
      break
    case 'heatmap':
      store.toggleLayer('heatmap')
      break
    case 'fullscreen':
      toggleFullscreen()
      break
  }
}

// 处理右键菜单
function handleContextMenu(event: MouseEvent) {
  event.preventDefault()
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

// 处理楼层切换
function handleFloorChange(data: { floor: string; mode: '2d' | '3d'; mapData: any }) {
  currentFloor.value = data.floor
  viewMode.value = data.mode

  if (data.mode === '2d') {
    floorMapData2D.value = data.mapData as MapData2D
  } else {
    floorMapData2D.value = null
    // 3D模式下，可以根据楼层加载不同的3D场景数据
    // TODO: 加载对应楼层的3D场景
  }
}

// 处理2D平面图元素点击
function handleFloorElementClick(element: any) {
  // 如果是设备，选中并显示详情
  if (element.type === 'device' || element.type === 'equipment' || element.type === 'cabinet') {
    store.selectDevice(element.id)
  }
}

onMounted(() => {
  updateTime()
  timeTimer = window.setInterval(updateTime, 1000)

  // 初始化键盘快捷键
  const keyboardShortcuts = useKeyboardShortcuts({
    onCameraPreset: (preset) => setCamera(preset),
    onToggleFullscreen: toggleFullscreen,
    onToggleTour: handleToggleTour,
    onToggleHeatmap: () => store.toggleLayer('heatmap'),
    onEscape: () => {
      contextMenuVisible.value = false
      store.selectDevice(null)
    }
  })

  // 添加右键菜单事件监听
  document.addEventListener('contextmenu', handleContextMenu)
})

onUnmounted(() => {
  if (timeTimer) {
    clearInterval(timeTimer)
  }
  // 停止巡航
  if (autoTour?.isTouring.value) {
    autoTour.stopTour()
  }
  // 移除右键菜单事件监听
  document.removeEventListener('contextmenu', handleContextMenu)
})
</script>

<style scoped lang="scss">
.bigscreen-container {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #0a0a1a;
}

.overlay-panels {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;

  > * {
    pointer-events: auto;
  }
}

.top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50px;
  background: linear-gradient(180deg, rgba(10, 10, 26, 0.9) 0%, rgba(10, 10, 26, 0) 100%);
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 20px;
  color: #fff;

  .time {
    font-size: 14px;
    color: #8899aa;
    font-family: 'Courier New', monospace;
  }

  .title {
    font-size: 18px;
    font-weight: bold;
    background: linear-gradient(90deg, #00ccff, #0088ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    flex: 1;
    text-align: center;
  }

  .mode-selector {
    .mode-label {
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 6px 12px;
      background: rgba(0, 136, 255, 0.2);
      border: 1px solid rgba(0, 136, 255, 0.4);
      border-radius: 4px;
      font-size: 13px;

      &:hover {
        background: rgba(0, 136, 255, 0.3);
      }
    }
  }

  .back-btn {
    cursor: pointer;
    padding: 8px;
    border-radius: 4px;
    margin-right: 12px;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }
  }

  .fullscreen-btn {
    cursor: pointer;
    padding: 8px;
    border-radius: 4px;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }
  }

  .kpi {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;

    .label {
      font-size: 12px;
      color: #8899aa;
    }

    .value {
      font-size: 16px;
      font-weight: bold;
      color: #00ff88;
    }

    &.alarm {
      .value {
        color: #8899aa;
      }

      &.has-alarm .value {
        color: #ff3300;
        animation: pulse 1s ease-in-out infinite;
      }
    }
  }
}

.bottom-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 50px;
  background: linear-gradient(0deg, rgba(10, 10, 26, 0.9) 0%, rgba(10, 10, 26, 0) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  gap: 40px;
  color: #fff;

  .label {
    font-size: 13px;
    color: #8899aa;
    margin-right: 8px;
  }

  .layer-toggles {
    display: flex;
    align-items: center;
    gap: 12px;

    :deep(.el-checkbox) {
      color: #ccc;

      .el-checkbox__label {
        color: #ccc;
        font-size: 13px;
      }
    }
  }

  .panel-toggles {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-left: 20px;
    border-left: 1px solid rgba(255, 255, 255, 0.2);

    :deep(.el-checkbox) {
      color: #ccc;

      .el-checkbox__label {
        color: #ccc;
        font-size: 13px;
      }
    }

    :deep(.el-button) {
      background: rgba(0, 136, 255, 0.2);
      border-color: rgba(0, 136, 255, 0.4);
      color: #ccc;
      margin-left: 8px;

      &:hover {
        background: rgba(0, 136, 255, 0.3);
        color: #fff;
      }
    }
  }

  .view-presets {
    display: flex;
    align-items: center;
    gap: 8px;

    :deep(.el-button) {
      background: rgba(0, 136, 255, 0.2);
      border-color: rgba(0, 136, 255, 0.4);
      color: #ccc;

      &:hover {
        background: rgba(0, 136, 255, 0.3);
        color: #fff;
      }
    }
  }

  .tour-control {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: 20px;
    padding-left: 20px;
    border-left: 1px solid rgba(255, 255, 255, 0.2);

    :deep(.el-button) {
      background: rgba(0, 136, 255, 0.2);
      border-color: rgba(0, 136, 255, 0.4);
      color: #ccc;

      &:hover {
        background: rgba(0, 136, 255, 0.3);
        color: #fff;
      }

      &.el-button--primary {
        background: rgba(0, 136, 255, 0.4);
        color: #fff;
      }
    }

    .tour-label {
      font-size: 12px;
      color: #00ccff;
      background: rgba(0, 136, 255, 0.2);
      padding: 4px 8px;
      border-radius: 4px;
    }
  }
}

.loading-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #8899aa;

  .loading-icon {
    font-size: 32px;
    animation: spin 1s linear infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
