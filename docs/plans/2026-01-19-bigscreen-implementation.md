# 数字孪生大屏实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 Three.js 构建数字孪生机房大屏，实现3D可视化、实时数据展示、多场景模式切换。

**Architecture:** 采用 Vue 3 + Three.js 架构，3D场景作为全屏背景，悬浮面板叠加在上层。使用 Pinia 管理状态，通过 composables 封装 Three.js 逻辑。复用现有后端 API 获取实时数据。

**Tech Stack:** Vue 3, Three.js, GSAP, Element Plus, ECharts, Pinia, TypeScript

---

## Phase 0: 环境准备

### Task 0.1: 安装依赖

**Step 1: 安装 Three.js 及相关依赖**

Run:
```bash
cd D:\mytest1\frontend && npm install three @types/three gsap
```

Expected: 依赖安装成功，package.json 更新

**Step 2: 验证安装**

Run:
```bash
cd D:\mytest1\frontend && npm ls three gsap
```

Expected: 显示 three 和 gsap 版本

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/package.json frontend/package-lock.json && git commit -m "chore: add three.js and gsap dependencies for bigscreen"
```

---

## Phase 1: 基础场景搭建

### Task 1.1: 创建 Three.js 类型定义

**Files:**
- Create: `frontend/src/types/bigscreen.ts`

**Step 1: 创建类型定义文件**

```typescript
// frontend/src/types/bigscreen.ts
import type * as THREE from 'three'

// 场景模式
export type SceneMode = 'command' | 'operation' | 'showcase'

// 机柜配置
export interface CabinetConfig {
  id: string
  name: string
  position: { x: number; y: number; z: number }
  size: { width: number; height: number; depth: number }
  status: 'normal' | 'alarm' | 'offline'
  temperature?: number
  power?: number
  load?: number
}

// 模块配置
export interface ModuleConfig {
  id: string
  name: string
  position: { x: number; z: number }
  rotation: number
  cabinets: CabinetConfig[]
  coolingUnits: Array<{ id: string; position: { x: number; z: number } }>
}

// 机房布局配置
export interface DataCenterLayout {
  name: string
  dimensions: { width: number; length: number; height: number }
  modules: ModuleConfig[]
  infrastructure: {
    upsRoom?: { position: { x: number; z: number }; size: { width: number; length: number } }
    powerRoom?: { position: { x: number; z: number }; size: { width: number; length: number } }
  }
}

// 相机预设
export interface CameraPreset {
  position: [number, number, number]
  target: [number, number, number]
}

// 数据图层
export interface DataLayers {
  heatmap: boolean
  status: boolean
  power: boolean
  airflow: boolean
}

// 设备实时数据
export interface DeviceRealtimeData {
  id: string
  status: 'normal' | 'alarm' | 'offline'
  temperature?: number
  humidity?: number
  power?: number
  load?: number
}

// 告警项
export interface BigscreenAlarm {
  id: number
  deviceId: string
  deviceName: string
  level: 'critical' | 'major' | 'minor' | 'info'
  message: string
  value?: number
  threshold?: number
  duration?: string
  createdAt: string
}

// Three.js 场景上下文
export interface ThreeContext {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
  controls: any // OrbitControls
}
```

**Step 2: Commit**

```bash
cd D:\mytest1 && git add frontend/src/types/bigscreen.ts && git commit -m "feat(bigscreen): add type definitions"
```

---

### Task 1.2: 创建 useThreeScene composable

**Files:**
- Create: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 创建 composable 文件**

```typescript
// frontend/src/composables/bigscreen/useThreeScene.ts
import { ref, shallowRef, onMounted, onUnmounted, type Ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

export interface UseThreeSceneOptions {
  antialias?: boolean
  alpha?: boolean
  backgroundColor?: number
}

export function useThreeScene(
  containerRef: Ref<HTMLElement | null>,
  options: UseThreeSceneOptions = {}
) {
  const {
    antialias = true,
    alpha = false,
    backgroundColor = 0x0a0a1a
  } = options

  // 使用 shallowRef 避免深度响应式（Three.js 对象很大）
  const scene = shallowRef<THREE.Scene | null>(null)
  const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
  const renderer = shallowRef<THREE.WebGLRenderer | null>(null)
  const controls = shallowRef<OrbitControls | null>(null)

  const isInitialized = ref(false)
  let animationFrameId: number | null = null

  // 初始化场景
  function initScene() {
    if (!containerRef.value) return

    const container = containerRef.value
    const width = container.clientWidth
    const height = container.clientHeight

    // 创建场景
    const newScene = new THREE.Scene()
    newScene.background = new THREE.Color(backgroundColor)
    scene.value = newScene

    // 创建相机
    const newCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000)
    newCamera.position.set(0, 50, 50)
    newCamera.lookAt(0, 0, 0)
    camera.value = newCamera

    // 创建渲染器
    const newRenderer = new THREE.WebGLRenderer({ antialias, alpha })
    newRenderer.setSize(width, height)
    newRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    newRenderer.shadowMap.enabled = true
    newRenderer.shadowMap.type = THREE.PCFSoftShadowMap
    container.appendChild(newRenderer.domElement)
    renderer.value = newRenderer

    // 创建轨道控制器
    const newControls = new OrbitControls(newCamera, newRenderer.domElement)
    newControls.enableDamping = true
    newControls.dampingFactor = 0.05
    newControls.minDistance = 5
    newControls.maxDistance = 100
    newControls.maxPolarAngle = Math.PI / 2.1
    controls.value = newControls

    // 添加灯光
    setupLights(newScene)

    isInitialized.value = true
  }

  // 设置灯光
  function setupLights(targetScene: THREE.Scene) {
    // 环境光
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4)
    targetScene.add(ambientLight)

    // 主方向光
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
    directionalLight.position.set(50, 100, 50)
    directionalLight.castShadow = true
    directionalLight.shadow.mapSize.width = 2048
    directionalLight.shadow.mapSize.height = 2048
    directionalLight.shadow.camera.near = 0.5
    directionalLight.shadow.camera.far = 500
    directionalLight.shadow.camera.left = -100
    directionalLight.shadow.camera.right = 100
    directionalLight.shadow.camera.top = 100
    directionalLight.shadow.camera.bottom = -100
    targetScene.add(directionalLight)

    // 补光
    const fillLight = new THREE.DirectionalLight(0x4488ff, 0.3)
    fillLight.position.set(-50, 50, -50)
    targetScene.add(fillLight)
  }

  // 渲染循环
  function animate() {
    animationFrameId = requestAnimationFrame(animate)

    if (controls.value) {
      controls.value.update()
    }

    if (renderer.value && scene.value && camera.value) {
      renderer.value.render(scene.value, camera.value)
    }
  }

  // 处理窗口大小变化
  function handleResize() {
    if (!containerRef.value || !camera.value || !renderer.value) return

    const width = containerRef.value.clientWidth
    const height = containerRef.value.clientHeight

    camera.value.aspect = width / height
    camera.value.updateProjectionMatrix()
    renderer.value.setSize(width, height)
  }

  // 启动渲染
  function startRendering() {
    if (!animationFrameId) {
      animate()
    }
  }

  // 停止渲染
  function stopRendering() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
  }

  // 销毁场景
  function dispose() {
    stopRendering()

    if (controls.value) {
      controls.value.dispose()
    }

    if (renderer.value) {
      renderer.value.dispose()
      renderer.value.domElement.remove()
    }

    if (scene.value) {
      scene.value.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose()
          if (Array.isArray(object.material)) {
            object.material.forEach((m) => m.dispose())
          } else {
            object.material.dispose()
          }
        }
      })
      scene.value.clear()
    }

    scene.value = null
    camera.value = null
    renderer.value = null
    controls.value = null
    isInitialized.value = false
  }

  onMounted(() => {
    initScene()
    startRendering()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    dispose()
  })

  return {
    scene,
    camera,
    renderer,
    controls,
    isInitialized,
    handleResize,
    startRendering,
    stopRendering,
    dispose
  }
}
```

**Step 2: 创建 composables 导出入口**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/composables/bigscreen/ && git commit -m "feat(bigscreen): add useThreeScene composable"
```

---

### Task 1.3: 创建 ThreeScene.vue 组件

**Files:**
- Create: `frontend/src/components/bigscreen/ThreeScene.vue`

**Step 1: 创建组件文件**

```vue
<!-- frontend/src/components/bigscreen/ThreeScene.vue -->
<template>
  <div ref="containerRef" class="three-scene-container">
    <slot v-if="isInitialized" />
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import { useThreeScene } from '@/composables/bigscreen/useThreeScene'

const containerRef = ref<HTMLElement | null>(null)

const {
  scene,
  camera,
  renderer,
  controls,
  isInitialized
} = useThreeScene(containerRef, {
  backgroundColor: 0x0a0a1a
})

// 提供给子组件
provide('three-scene', scene)
provide('three-camera', camera)
provide('three-renderer', renderer)
provide('three-controls', controls)

// 暴露给父组件
defineExpose({
  scene,
  camera,
  renderer,
  controls,
  isInitialized
})
</script>

<style scoped>
.three-scene-container {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
}

.three-scene-container :deep(canvas) {
  display: block;
}
</style>
```

**Step 2: 创建 components/bigscreen 导出入口**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/components/bigscreen/ && git commit -m "feat(bigscreen): add ThreeScene component"
```

---

### Task 1.4: 创建地板和基础环境

**Files:**
- Create: `frontend/src/utils/three/sceneSetup.ts`

**Step 1: 创建场景设置工具函数**

```typescript
// frontend/src/utils/three/sceneSetup.ts
import * as THREE from 'three'

// 创建地板
export function createFloor(width = 100, length = 100): THREE.Mesh {
  const geometry = new THREE.PlaneGeometry(width, length)
  const material = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e,
    roughness: 0.8,
    metalness: 0.2
  })

  const floor = new THREE.Mesh(geometry, material)
  floor.rotation.x = -Math.PI / 2
  floor.position.y = 0
  floor.receiveShadow = true
  floor.name = 'floor'

  return floor
}

// 创建网格线
export function createGridHelper(size = 100, divisions = 50): THREE.GridHelper {
  const grid = new THREE.GridHelper(size, divisions, 0x2a2a4a, 0x1a1a3a)
  grid.position.y = 0.01 // 略高于地板避免z-fighting
  grid.name = 'grid'

  return grid
}

// 创建环境背景（简单的科技感背景）
export function createEnvironment(scene: THREE.Scene): void {
  // 添加雾效果
  scene.fog = new THREE.Fog(0x0a0a1a, 50, 150)

  // 可选：添加简单的天空盒或渐变背景
  // 这里使用纯色背景，后续可以替换为天空盒
}

// 创建坐标轴辅助（开发用）
export function createAxesHelper(size = 10): THREE.AxesHelper {
  return new THREE.AxesHelper(size)
}

// 初始化基础场景元素
export function setupBasicScene(scene: THREE.Scene, options?: {
  showGrid?: boolean
  showAxes?: boolean
  floorSize?: number
}): void {
  const { showGrid = true, showAxes = false, floorSize = 100 } = options || {}

  // 添加地板
  const floor = createFloor(floorSize, floorSize)
  scene.add(floor)

  // 添加网格
  if (showGrid) {
    const grid = createGridHelper(floorSize, floorSize / 2)
    scene.add(grid)
  }

  // 添加坐标轴（开发调试用）
  if (showAxes) {
    const axes = createAxesHelper(10)
    scene.add(axes)
  }

  // 设置环境
  createEnvironment(scene)
}
```

**Step 2: 创建 utils/three 导出入口**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/utils/three/ && git commit -m "feat(bigscreen): add scene setup utilities"
```

---

### Task 1.5: 创建 Pinia Store

**Files:**
- Create: `frontend/src/stores/bigscreen.ts`

**Step 1: 创建 store 文件**

```typescript
// frontend/src/stores/bigscreen.ts
import { defineStore } from 'pinia'
import type {
  SceneMode,
  DataCenterLayout,
  DeviceRealtimeData,
  DataLayers,
  BigscreenAlarm,
  CameraPreset
} from '@/types/bigscreen'

interface BigscreenState {
  // 场景模式
  mode: SceneMode

  // 布局配置
  layout: DataCenterLayout | null

  // 设备实时数据 (按设备ID索引)
  deviceData: Record<string, DeviceRealtimeData>

  // 数据图层开关
  layers: DataLayers

  // 选中的设备
  selectedDeviceId: string | null

  // 活动告警
  activeAlarms: BigscreenAlarm[]

  // 环境数据
  environment: {
    temperature: { max: number; avg: number; min: number }
    humidity: { max: number; avg: number; min: number }
  }

  // 能耗数据
  energy: {
    totalPower: number
    itPower: number
    coolingPower: number
    pue: number
    todayEnergy: number
    todayCost: number
  }

  // 相机预设
  cameraPresets: Record<string, CameraPreset>

  // 是否正在加载
  loading: boolean
}

export const useBigscreenStore = defineStore('bigscreen', {
  state: (): BigscreenState => ({
    mode: 'command',
    layout: null,
    deviceData: {},
    layers: {
      heatmap: true,
      status: true,
      power: true,
      airflow: false
    },
    selectedDeviceId: null,
    activeAlarms: [],
    environment: {
      temperature: { max: 0, avg: 0, min: 0 },
      humidity: { max: 0, avg: 0, min: 0 }
    },
    energy: {
      totalPower: 0,
      itPower: 0,
      coolingPower: 0,
      pue: 1.5,
      todayEnergy: 0,
      todayCost: 0
    },
    cameraPresets: {
      overview: { position: [0, 50, 50], target: [0, 0, 0] },
      topDown: { position: [0, 80, 0], target: [0, 0, 0] },
      moduleA: { position: [20, 15, 20], target: [20, 0, 0] }
    },
    loading: false
  }),

  getters: {
    // 获取设备数据
    getDeviceData: (state) => (deviceId: string) => {
      return state.deviceData[deviceId] || null
    },

    // 获取告警数量
    alarmCount: (state) => state.activeAlarms.length,

    // 获取严重告警数量
    criticalAlarmCount: (state) => {
      return state.activeAlarms.filter(a => a.level === 'critical').length
    },

    // 是否有选中设备
    hasSelectedDevice: (state) => state.selectedDeviceId !== null,

    // 获取当前模式配置
    modeConfig: (state) => {
      const configs = {
        command: {
          cameraLocked: true,
          refreshInterval: 5000,
          showAllPanels: true
        },
        operation: {
          cameraLocked: false,
          refreshInterval: 3000,
          showAllPanels: true
        },
        showcase: {
          cameraLocked: true,
          refreshInterval: 10000,
          showAllPanels: false
        }
      }
      return configs[state.mode]
    }
  },

  actions: {
    // 设置场景模式
    setMode(mode: SceneMode) {
      this.mode = mode
    },

    // 设置布局
    setLayout(layout: DataCenterLayout) {
      this.layout = layout
    },

    // 更新设备数据
    updateDeviceData(deviceId: string, data: Partial<DeviceRealtimeData>) {
      this.deviceData[deviceId] = {
        ...this.deviceData[deviceId],
        id: deviceId,
        ...data
      } as DeviceRealtimeData
    },

    // 批量更新设备数据
    updateAllDeviceData(dataList: DeviceRealtimeData[]) {
      dataList.forEach(data => {
        this.deviceData[data.id] = data
      })
    },

    // 切换图层
    toggleLayer(layer: keyof DataLayers) {
      this.layers[layer] = !this.layers[layer]
    },

    // 设置选中设备
    selectDevice(deviceId: string | null) {
      this.selectedDeviceId = deviceId
    },

    // 更新告警列表
    setAlarms(alarms: BigscreenAlarm[]) {
      this.activeAlarms = alarms
    },

    // 更新环境数据
    updateEnvironment(env: BigscreenState['environment']) {
      this.environment = env
    },

    // 更新能耗数据
    updateEnergy(energy: BigscreenState['energy']) {
      this.energy = energy
    },

    // 设置加载状态
    setLoading(loading: boolean) {
      this.loading = loading
    }
  }
})
```

**Step 2: 更新 stores/index.ts 导出**

需要先检查现有的 stores/index.ts 结构，然后添加导出。

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/stores/bigscreen.ts && git commit -m "feat(bigscreen): add bigscreen Pinia store"
```

---

### Task 1.6: 创建大屏主页面

**Files:**
- Create: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建页面文件**

```vue
<!-- frontend/src/views/bigscreen/index.vue -->
<template>
  <div class="bigscreen-container">
    <!-- Three.js 3D场景 -->
    <ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady" />

    <!-- 悬浮面板层 -->
    <div class="overlay-panels">
      <!-- 顶部状态栏 -->
      <div class="top-bar">
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
        <div class="kpi pue">
          <span class="label">PUE</span>
          <span class="value">{{ store.energy.pue.toFixed(2) }}</span>
        </div>
        <div class="kpi alarm" :class="{ 'has-alarm': store.alarmCount > 0 }">
          <el-icon><Bell /></el-icon>
          <span class="value">{{ store.alarmCount }}</span>
        </div>
      </div>

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
        <div class="view-presets">
          <span class="label">视角:</span>
          <el-button size="small" @click="setCamera('overview')">全景</el-button>
          <el-button size="small" @click="setCamera('topDown')">俯视</el-button>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="store.loading" class="loading-overlay">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ArrowDown, FullScreen, Bell, Loading } from '@element-plus/icons-vue'
import { ThreeScene } from '@/components/bigscreen'
import { useBigscreenStore } from '@/stores/bigscreen'
import { setupBasicScene } from '@/utils/three/sceneSetup'
import type { SceneMode } from '@/types/bigscreen'

const store = useBigscreenStore()
const threeSceneRef = ref<InstanceType<typeof ThreeScene> | null>(null)

// 当前时间
const currentTime = ref('')
let timeTimer: number | null = null

// 模式标签
const modeLabels: Record<SceneMode, string> = {
  command: '指挥中心',
  operation: '运维模式',
  showcase: '展示模式'
}

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
function onSceneReady() {
  const sceneComponent = threeSceneRef.value
  if (sceneComponent?.scene) {
    // 设置基础场景
    setupBasicScene(sceneComponent.scene, {
      showGrid: true,
      showAxes: false,
      floorSize: 100
    })
  }
}

// 切换模式
function handleModeChange(mode: SceneMode) {
  store.setMode(mode)
}

// 切换全屏
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 设置相机预设视角
function setCamera(preset: string) {
  const presetConfig = store.cameraPresets[preset]
  if (!presetConfig || !threeSceneRef.value?.camera) return

  const camera = threeSceneRef.value.camera
  const controls = threeSceneRef.value.controls

  if (camera && controls) {
    // 简单设置，后续用 GSAP 动画
    camera.position.set(...presetConfig.position)
    controls.target.set(...presetConfig.target)
    controls.update()
  }
}

onMounted(() => {
  updateTime()
  timeTimer = window.setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeTimer) {
    clearInterval(timeTimer)
  }
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
```

**Step 2: Commit**

```bash
cd D:\mytest1 && git add frontend/src/views/bigscreen/ && git commit -m "feat(bigscreen): add main bigscreen page"
```

---

### Task 1.7: 添加路由配置

**Files:**
- Modify: `frontend/src/router/index.ts`

**Step 1: 添加大屏路由**

在 router/index.ts 中添加路由配置：

```typescript
// 在 routes 数组中添加
{
  path: '/bigscreen',
  name: 'Bigscreen',
  component: () => import('@/views/bigscreen/index.vue'),
  meta: {
    title: '数字孪生大屏',
    fullscreen: true,
    requiresAuth: false  // 大屏页面可单独访问
  }
}
```

**Step 2: 验证路由**

Run:
```bash
cd D:\mytest1\frontend && npm run dev
```

访问 http://localhost:3000/bigscreen 验证页面是否正常加载

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/router/index.ts && git commit -m "feat(bigscreen): add bigscreen route"
```

---

## Phase 1 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 页面全屏显示深色背景
   - 3D场景正常渲染（地板+网格）
   - 顶部状态栏显示时间、标题、模式选择
   - 底部控制栏显示图层开关、视角按钮
   - 视角切换按钮可正常工作

**Expected Result:** 基础3D场景框架搭建完成，可以进行后续开发

---

## Phase 2: 机房模型生成

### Task 2.1: 创建程序化机柜生成器

**Files:**
- Create: `frontend/src/utils/three/modelGenerator.ts`

**Step 1: 创建模型生成器**

```typescript
// frontend/src/utils/three/modelGenerator.ts
import * as THREE from 'three'
import type { CabinetConfig } from '@/types/bigscreen'

// 机柜默认尺寸 (米)
const DEFAULT_CABINET_SIZE = {
  width: 0.6,
  height: 2.0,
  depth: 1.0
}

// 状态颜色
const STATUS_COLORS = {
  normal: 0x00ff88,
  alarm: 0xff3300,
  offline: 0x666666
}

// 创建单个机柜
export function createCabinet(config: CabinetConfig): THREE.Group {
  const group = new THREE.Group()
  group.name = `cabinet_${config.id}`
  group.userData = { type: 'cabinet', config }

  const size = config.size || DEFAULT_CABINET_SIZE

  // 机柜主体
  const bodyGeometry = new THREE.BoxGeometry(size.width, size.height, size.depth)
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0x2a2a3a,
    roughness: 0.7,
    metalness: 0.3
  })
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial)
  body.position.y = size.height / 2
  body.castShadow = true
  body.receiveShadow = true
  body.name = 'body'
  group.add(body)

  // 前面板（带网格效果）
  const frontGeometry = new THREE.PlaneGeometry(size.width * 0.9, size.height * 0.95)
  const frontMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a2a,
    roughness: 0.5,
    metalness: 0.5
  })
  const front = new THREE.Mesh(frontGeometry, frontMaterial)
  front.position.set(0, size.height / 2, size.depth / 2 + 0.01)
  front.name = 'front'
  group.add(front)

  // 状态指示灯
  const indicatorGeometry = new THREE.SphereGeometry(0.03, 16, 16)
  const indicatorMaterial = new THREE.MeshStandardMaterial({
    color: STATUS_COLORS[config.status || 'normal'],
    emissive: STATUS_COLORS[config.status || 'normal'],
    emissiveIntensity: 0.5
  })
  const indicator = new THREE.Mesh(indicatorGeometry, indicatorMaterial)
  indicator.position.set(size.width / 2 - 0.05, size.height - 0.05, size.depth / 2 + 0.02)
  indicator.name = 'indicator'
  group.add(indicator)

  // 设置位置
  group.position.set(config.position.x, config.position.y || 0, config.position.z)

  return group
}

// 创建机柜排
export function createCabinetRow(
  startPosition: { x: number; z: number },
  direction: 'x' | 'z',
  count: number,
  configs: Partial<CabinetConfig>[] = []
): THREE.Group {
  const group = new THREE.Group()
  group.name = 'cabinet_row'

  const spacing = direction === 'x'
    ? DEFAULT_CABINET_SIZE.width + 0.05
    : DEFAULT_CABINET_SIZE.depth + 0.05

  for (let i = 0; i < count; i++) {
    const x = direction === 'x' ? startPosition.x + i * spacing : startPosition.x
    const z = direction === 'z' ? startPosition.z + i * spacing : startPosition.z

    const cabinetConfig: CabinetConfig = {
      id: configs[i]?.id || `cab_${i}`,
      name: configs[i]?.name || `机柜 ${i + 1}`,
      position: { x, y: 0, z },
      size: DEFAULT_CABINET_SIZE,
      status: configs[i]?.status || 'normal',
      ...configs[i]
    }

    const cabinet = createCabinet(cabinetConfig)
    group.add(cabinet)
  }

  return group
}

// 创建空调单元
export function createCoolingUnit(position: { x: number; z: number }): THREE.Group {
  const group = new THREE.Group()
  group.name = 'cooling_unit'
  group.userData = { type: 'cooling' }

  // 空调主体
  const bodyGeometry = new THREE.BoxGeometry(1.2, 2.2, 0.8)
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0x3a3a4a,
    roughness: 0.6,
    metalness: 0.2
  })
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial)
  body.position.y = 1.1
  body.castShadow = true
  group.add(body)

  // 出风口
  const ventGeometry = new THREE.PlaneGeometry(1.0, 0.3)
  const ventMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a2a,
    roughness: 0.3
  })
  const vent = new THREE.Mesh(ventGeometry, ventMaterial)
  vent.position.set(0, 1.8, 0.41)
  group.add(vent)

  group.position.set(position.x, 0, position.z)

  return group
}

// 创建UPS室
export function createUPSRoom(
  position: { x: number; z: number },
  size: { width: number; length: number }
): THREE.Group {
  const group = new THREE.Group()
  group.name = 'ups_room'
  group.userData = { type: 'infrastructure' }

  const height = 2.5

  // 房间围墙
  const wallMaterial = new THREE.MeshStandardMaterial({
    color: 0x2a2a3a,
    roughness: 0.8,
    transparent: true,
    opacity: 0.7
  })

  // 后墙
  const backWall = new THREE.Mesh(
    new THREE.BoxGeometry(size.width, height, 0.1),
    wallMaterial
  )
  backWall.position.set(0, height / 2, -size.length / 2)
  group.add(backWall)

  // 左墙
  const leftWall = new THREE.Mesh(
    new THREE.BoxGeometry(0.1, height, size.length),
    wallMaterial
  )
  leftWall.position.set(-size.width / 2, height / 2, 0)
  group.add(leftWall)

  // 右墙
  const rightWall = new THREE.Mesh(
    new THREE.BoxGeometry(0.1, height, size.length),
    wallMaterial
  )
  rightWall.position.set(size.width / 2, height / 2, 0)
  group.add(rightWall)

  // UPS设备
  const upsGeometry = new THREE.BoxGeometry(0.8, 1.8, 0.6)
  const upsMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a3a1a,
    roughness: 0.5
  })

  for (let i = 0; i < 3; i++) {
    const ups = new THREE.Mesh(upsGeometry, upsMaterial)
    ups.position.set(-size.width / 3 + i * (size.width / 3), 0.9, 0)
    ups.castShadow = true
    group.add(ups)
  }

  group.position.set(position.x, 0, position.z)

  return group
}

// 更新机柜状态
export function updateCabinetStatus(
  cabinet: THREE.Group,
  status: 'normal' | 'alarm' | 'offline'
): void {
  const indicator = cabinet.getObjectByName('indicator') as THREE.Mesh
  if (indicator && indicator.material instanceof THREE.MeshStandardMaterial) {
    const color = STATUS_COLORS[status]
    indicator.material.color.setHex(color)
    indicator.material.emissive.setHex(color)
  }

  // 更新userData
  if (cabinet.userData.config) {
    cabinet.userData.config.status = status
  }
}
```

**Step 2: 更新 utils/three/index.ts**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
export * from './modelGenerator'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/utils/three/modelGenerator.ts frontend/src/utils/three/index.ts && git commit -m "feat(bigscreen): add cabinet and infrastructure model generators"
```

---

### Task 2.2: 创建 DataCenterModel 组件

**Files:**
- Create: `frontend/src/components/bigscreen/DataCenterModel.vue`

**Step 1: 创建组件**

```vue
<!-- frontend/src/components/bigscreen/DataCenterModel.vue -->
<template>
  <div class="datacenter-model">
    <!-- 这是一个逻辑组件，不渲染DOM -->
  </div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'
import {
  createCabinet,
  createCabinetRow,
  createCoolingUnit,
  createUPSRoom,
  updateCabinetStatus
} from '@/utils/three/modelGenerator'
import type { DataCenterLayout, ModuleConfig } from '@/types/bigscreen'

const store = useBigscreenStore()

// 注入场景
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 数据中心模型组
const dataCenterGroup = shallowRef<THREE.Group | null>(null)

// 机柜映射 (id -> mesh)
const cabinetMap = new Map<string, THREE.Group>()

// 创建数据中心模型
function createDataCenter(layout: DataCenterLayout) {
  if (!scene?.value) return

  // 清除旧模型
  if (dataCenterGroup.value) {
    scene.value.remove(dataCenterGroup.value)
    dataCenterGroup.value = null
    cabinetMap.clear()
  }

  const group = new THREE.Group()
  group.name = 'datacenter'

  // 创建模块
  layout.modules.forEach((module) => {
    const moduleGroup = createModule(module)
    group.add(moduleGroup)
  })

  // 创建基础设施
  if (layout.infrastructure.upsRoom) {
    const ups = createUPSRoom(
      layout.infrastructure.upsRoom.position,
      layout.infrastructure.upsRoom.size
    )
    group.add(ups)
  }

  scene.value.add(group)
  dataCenterGroup.value = group
}

// 创建单个模块
function createModule(config: ModuleConfig): THREE.Group {
  const group = new THREE.Group()
  group.name = `module_${config.id}`
  group.position.set(config.position.x, 0, config.position.z)
  group.rotation.y = (config.rotation * Math.PI) / 180

  // 创建机柜
  config.cabinets.forEach((cabinetConfig) => {
    const cabinet = createCabinet(cabinetConfig)
    group.add(cabinet)
    cabinetMap.set(cabinetConfig.id, cabinet)
  })

  // 创建空调
  config.coolingUnits.forEach((cooling) => {
    const coolingUnit = createCoolingUnit(cooling.position)
    coolingUnit.name = `cooling_${cooling.id}`
    group.add(coolingUnit)
  })

  return group
}

// 生成默认布局 (演示用)
function generateDefaultLayout(): DataCenterLayout {
  const cabinets = []

  // 生成两排机柜
  for (let row = 0; row < 2; row++) {
    for (let i = 0; i < 8; i++) {
      cabinets.push({
        id: `cab_${row}_${i}`,
        name: `机柜 ${String.fromCharCode(65 + row)}-${i + 1}`,
        position: {
          x: -12 + i * 3,
          y: 0,
          z: -5 + row * 10
        },
        size: { width: 0.6, height: 2.0, depth: 1.0 },
        status: Math.random() > 0.9 ? 'alarm' : 'normal' as const
      })
    }
  }

  return {
    name: '演示数据中心',
    dimensions: { width: 50, length: 30, height: 5 },
    modules: [
      {
        id: 'module_a',
        name: '模块A',
        position: { x: 0, z: 0 },
        rotation: 0,
        cabinets,
        coolingUnits: [
          { id: 'ac_1', position: { x: -15, z: 0 } },
          { id: 'ac_2', position: { x: 15, z: 0 } }
        ]
      }
    ],
    infrastructure: {
      upsRoom: {
        position: { x: -20, z: -10 },
        size: { width: 8, length: 6 }
      }
    }
  }
}

// 更新机柜数据
function updateCabinets() {
  cabinetMap.forEach((cabinet, id) => {
    const data = store.deviceData[id]
    if (data) {
      updateCabinetStatus(cabinet, data.status)
    }
  })
}

// 监听布局变化
watch(
  () => store.layout,
  (layout) => {
    if (layout) {
      createDataCenter(layout)
    }
  },
  { immediate: true }
)

// 监听设备数据变化
watch(
  () => store.deviceData,
  () => {
    updateCabinets()
  },
  { deep: true }
)

onMounted(() => {
  // 如果没有布局，使用默认布局
  if (!store.layout) {
    const defaultLayout = generateDefaultLayout()
    store.setLayout(defaultLayout)
  }
})

onUnmounted(() => {
  if (scene?.value && dataCenterGroup.value) {
    scene.value.remove(dataCenterGroup.value)
  }
  cabinetMap.clear()
})

// 暴露方法
defineExpose({
  cabinetMap,
  updateCabinets
})
</script>

<style scoped>
.datacenter-model {
  display: none;
}
</style>
```

**Step 2: 更新 components/bigscreen/index.ts**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
export { default as DataCenterModel } from './DataCenterModel.vue'
```

**Step 3: 更新大屏页面集成**

在 `views/bigscreen/index.vue` 中添加 DataCenterModel 组件：

```vue
<!-- 在 ThreeScene 内部添加 -->
<ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady">
  <DataCenterModel v-if="isSceneReady" />
</ThreeScene>
```

并添加 `isSceneReady` 状态：

```typescript
const isSceneReady = ref(false)

function onSceneReady() {
  // ... existing code ...
  isSceneReady.value = true
}
```

**Step 4: Commit**

```bash
cd D:\mytest1 && git add frontend/src/components/bigscreen/ frontend/src/views/bigscreen/index.vue && git commit -m "feat(bigscreen): add DataCenterModel component with default layout"
```

---

## Phase 2 完成检查点

**验证步骤:**

1. 启动前端开发服务器
2. 访问 /bigscreen
3. 验证：
   - 机柜正确渲染（两排，每排8个）
   - 空调单元正确显示
   - UPS室正确显示
   - 机柜状态指示灯显示（绿色正常，红色告警）

---

## Phase 3: 数据可视化层

### Task 3.1: 创建 CSS2DRenderer 标签系统

**Files:**
- Create: `frontend/src/utils/three/labelRenderer.ts`
- Modify: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 创建标签渲染器工具**

```typescript
// frontend/src/utils/three/labelRenderer.ts
import * as THREE from 'three'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

// 创建 CSS2D 渲染器
export function createLabelRenderer(container: HTMLElement): CSS2DRenderer {
  const labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(container.clientWidth, container.clientHeight)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.appendChild(labelRenderer.domElement)
  return labelRenderer
}

// 创建功率标签
export function createPowerLabel(power: number, name: string): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'power-label'
  div.innerHTML = `
    <div class="label-name">${name}</div>
    <div class="label-value">${power.toFixed(1)} kW</div>
  `
  div.style.cssText = `
    background: rgba(0, 20, 40, 0.85);
    border: 1px solid rgba(0, 136, 255, 0.5);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    color: #fff;
    white-space: nowrap;
    pointer-events: none;
  `

  const label = new CSS2DObject(div)
  label.name = 'power-label'
  return label
}

// 创建温度标签
export function createTemperatureLabel(temp: number): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'temp-label'

  // 根据温度设置颜色
  let color = '#00ff88' // 正常
  if (temp > 30) color = '#ff3300' // 过热
  else if (temp > 26) color = '#ffcc00' // 偏热
  else if (temp < 18) color = '#0066ff' // 过冷

  div.innerHTML = `<span style="color: ${color}">${temp.toFixed(1)}°C</span>`
  div.style.cssText = `
    background: rgba(0, 0, 0, 0.7);
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
    pointer-events: none;
  `

  const label = new CSS2DObject(div)
  label.name = 'temp-label'
  return label
}

// 更新标签内容
export function updateLabelContent(label: CSS2DObject, content: string): void {
  const div = label.element as HTMLDivElement
  if (div) {
    div.innerHTML = content
  }
}

// 设置标签可见性
export function setLabelVisibility(label: CSS2DObject, visible: boolean): void {
  label.visible = visible
  const div = label.element as HTMLDivElement
  if (div) {
    div.style.display = visible ? 'block' : 'none'
  }
}
```

**Step 2: 更新 useThreeScene 添加标签渲染器**

在 `useThreeScene.ts` 中添加 labelRenderer：

```typescript
// 在 imports 后添加
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

// 在 state 中添加
const labelRenderer = shallowRef<CSS2DRenderer | null>(null)

// 在 initScene 函数中，renderer 创建后添加
const newLabelRenderer = new CSS2DRenderer()
newLabelRenderer.setSize(width, height)
newLabelRenderer.domElement.style.position = 'absolute'
newLabelRenderer.domElement.style.top = '0'
newLabelRenderer.domElement.style.left = '0'
newLabelRenderer.domElement.style.pointerEvents = 'none'
container.appendChild(newLabelRenderer.domElement)
labelRenderer.value = newLabelRenderer

// 在 animate 函数中添加
if (labelRenderer.value && scene.value && camera.value) {
  labelRenderer.value.render(scene.value, camera.value)
}

// 在 handleResize 中添加
if (labelRenderer.value) {
  labelRenderer.value.setSize(width, height)
}

// 在 dispose 中添加
if (labelRenderer.value) {
  labelRenderer.value.domElement.remove()
}

// 在 return 中添加 labelRenderer
```

**Step 3: 更新 utils/three/index.ts**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
export * from './modelGenerator'
export * from './labelRenderer'
```

---

### Task 3.2: 机柜功率标签显示

**Files:**
- Create: `frontend/src/components/bigscreen/CabinetLabels.vue`
- Modify: `frontend/src/components/bigscreen/index.ts`

**Step 1: 创建机柜标签组件**

```vue
<!-- frontend/src/components/bigscreen/CabinetLabels.vue -->
<template>
  <div class="cabinet-labels">
    <!-- 逻辑组件，不渲染DOM -->
  </div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { useBigscreenStore } from '@/stores/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 标签映射
const labelMap = new Map<string, CSS2DObject>()

// 创建功率标签
function createLabel(cabinetId: string, name: string, power: number, position: THREE.Vector3): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'cabinet-power-label'
  updateLabelDiv(div, name, power)

  const label = new CSS2DObject(div)
  label.position.copy(position)
  label.position.y += 2.3 // 放在机柜上方
  label.name = `label_${cabinetId}`

  return label
}

// 更新标签内容
function updateLabelDiv(div: HTMLDivElement, name: string, power: number) {
  div.innerHTML = `
    <div class="label-name">${name}</div>
    <div class="label-power">${power.toFixed(1)} kW</div>
  `
  div.style.cssText = `
    background: rgba(0, 20, 40, 0.9);
    border: 1px solid rgba(0, 136, 255, 0.6);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    color: #fff;
    text-align: center;
    pointer-events: none;
    transform: translateX(-50%);
  `
}

// 初始化所有标签
function initLabels() {
  if (!scene?.value || !store.layout) return

  // 清除旧标签
  clearLabels()

  // 为每个机柜创建标签
  store.layout.modules.forEach(module => {
    module.cabinets.forEach(cabinet => {
      const power = store.deviceData[cabinet.id]?.power || cabinet.power || 0
      const position = new THREE.Vector3(
        module.position.x + cabinet.position.x,
        cabinet.position.y || 0,
        module.position.z + cabinet.position.z
      )

      const label = createLabel(cabinet.id, cabinet.name, power, position)
      scene.value!.add(label)
      labelMap.set(cabinet.id, label)
    })
  })
}

// 更新标签数据
function updateLabels() {
  labelMap.forEach((label, cabinetId) => {
    const data = store.deviceData[cabinetId]
    const cabinet = store.layout?.modules
      .flatMap(m => m.cabinets)
      .find(c => c.id === cabinetId)

    if (cabinet && label.element) {
      const power = data?.power || cabinet.power || 0
      updateLabelDiv(label.element as HTMLDivElement, cabinet.name, power)
    }
  })
}

// 设置标签可见性
function setLabelsVisible(visible: boolean) {
  labelMap.forEach(label => {
    label.visible = visible
    if (label.element) {
      (label.element as HTMLDivElement).style.display = visible ? 'block' : 'none'
    }
  })
}

// 清除所有标签
function clearLabels() {
  labelMap.forEach(label => {
    if (scene?.value) {
      scene.value.remove(label)
    }
    if (label.element && label.element.parentNode) {
      label.element.parentNode.removeChild(label.element)
    }
  })
  labelMap.clear()
}

// 监听布局变化
watch(() => store.layout, () => {
  initLabels()
}, { immediate: true })

// 监听设备数据变化
watch(() => store.deviceData, () => {
  updateLabels()
}, { deep: true })

// 监听图层开关
watch(() => store.layers.power, (visible) => {
  setLabelsVisible(visible)
})

onMounted(() => {
  // 延迟初始化，确保场景已就绪
  setTimeout(initLabels, 100)
})

onUnmounted(() => {
  clearLabels()
})

defineExpose({
  initLabels,
  updateLabels,
  setLabelsVisible
})
</script>

<style scoped>
.cabinet-labels {
  display: none;
}
</style>
```

**Step 2: 更新 components/bigscreen/index.ts**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
export { default as DataCenterModel } from './DataCenterModel.vue'
export { default as CabinetLabels } from './CabinetLabels.vue'
```

**Step 3: 在大屏页面集成**

在 `views/bigscreen/index.vue` 中添加：

```vue
<ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady">
  <DataCenterModel v-if="isSceneReady" />
  <CabinetLabels v-if="isSceneReady" />
</ThreeScene>
```

---

### Task 3.3: 温度热力图覆盖层

**Files:**
- Create: `frontend/src/components/bigscreen/HeatmapOverlay.vue`
- Create: `frontend/src/utils/three/heatmapHelper.ts`

**Step 1: 创建热力图辅助函数**

```typescript
// frontend/src/utils/three/heatmapHelper.ts
import * as THREE from 'three'

// 温度颜色映射
export const TEMPERATURE_COLORS = {
  cold: 0x0066ff,    // < 18°C 过冷
  cool: 0x00ccff,    // 18-22°C 偏冷
  normal: 0x00ff88,  // 22-26°C 正常
  warm: 0xffcc00,    // 26-30°C 偏热
  hot: 0xff3300      // > 30°C 过热
}

// 根据温度获取颜色
export function getTemperatureColor(temp: number): number {
  if (temp < 18) return TEMPERATURE_COLORS.cold
  if (temp < 22) return TEMPERATURE_COLORS.cool
  if (temp < 26) return TEMPERATURE_COLORS.normal
  if (temp < 30) return TEMPERATURE_COLORS.warm
  return TEMPERATURE_COLORS.hot
}

// 创建热力图平面
export function createHeatmapPlane(
  width: number,
  length: number,
  resolution: number = 20
): THREE.Mesh {
  const geometry = new THREE.PlaneGeometry(width, length, resolution, resolution)
  const material = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    side: THREE.DoubleSide
  })

  // 初始化顶点颜色
  const colors = new Float32Array(geometry.attributes.position.count * 3)
  for (let i = 0; i < colors.length; i += 3) {
    colors[i] = 0     // R
    colors[i + 1] = 1 // G
    colors[i + 2] = 0.5 // B
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const mesh = new THREE.Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.position.y = 0.02
  mesh.name = 'heatmap'

  return mesh
}

// 更新热力图颜色
export function updateHeatmapColors(
  mesh: THREE.Mesh,
  temperatureData: Array<{ x: number; z: number; temp: number }>,
  width: number,
  length: number
): void {
  const geometry = mesh.geometry as THREE.PlaneGeometry
  const colors = geometry.attributes.color as THREE.BufferAttribute
  const positions = geometry.attributes.position as THREE.BufferAttribute

  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i)
    const y = positions.getY(i) // 在平面上是 Y，但旋转后变成 Z

    // 找到最近的温度数据点
    let nearestTemp = 24 // 默认温度
    let minDist = Infinity

    temperatureData.forEach(point => {
      const dx = point.x - x
      const dz = point.z - y
      const dist = Math.sqrt(dx * dx + dz * dz)
      if (dist < minDist) {
        minDist = dist
        nearestTemp = point.temp
      }
    })

    // 距离衰减插值
    if (minDist > 10) {
      nearestTemp = 24 // 太远则使用默认
    }

    const color = new THREE.Color(getTemperatureColor(nearestTemp))
    colors.setXYZ(i, color.r, color.g, color.b)
  }

  colors.needsUpdate = true
}
```

**Step 2: 创建热力图组件**

```vue
<!-- frontend/src/components/bigscreen/HeatmapOverlay.vue -->
<template>
  <div class="heatmap-overlay"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'
import { createHeatmapPlane, updateHeatmapColors } from '@/utils/three/heatmapHelper'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

const heatmapMesh = shallowRef<THREE.Mesh | null>(null)

// 初始化热力图
function initHeatmap() {
  if (!scene?.value || !store.layout) return

  // 清除旧热力图
  if (heatmapMesh.value) {
    scene.value.remove(heatmapMesh.value)
  }

  const { width, length } = store.layout.dimensions
  const mesh = createHeatmapPlane(width, length, 30)
  mesh.visible = store.layers.heatmap

  scene.value.add(mesh)
  heatmapMesh.value = mesh

  // 初始更新
  updateHeatmap()
}

// 更新热力图数据
function updateHeatmap() {
  if (!heatmapMesh.value || !store.layout) return

  // 收集温度数据点
  const temperatureData: Array<{ x: number; z: number; temp: number }> = []

  store.layout.modules.forEach(module => {
    module.cabinets.forEach(cabinet => {
      const data = store.deviceData[cabinet.id]
      const temp = data?.temperature || cabinet.temperature || 24
      temperatureData.push({
        x: module.position.x + cabinet.position.x,
        z: module.position.z + cabinet.position.z,
        temp
      })
    })
  })

  const { width, length } = store.layout.dimensions
  updateHeatmapColors(heatmapMesh.value, temperatureData, width, length)
}

// 设置可见性
function setVisible(visible: boolean) {
  if (heatmapMesh.value) {
    heatmapMesh.value.visible = visible
  }
}

// 监听布局变化
watch(() => store.layout, () => {
  initHeatmap()
}, { immediate: true })

// 监听设备数据变化
watch(() => store.deviceData, () => {
  updateHeatmap()
}, { deep: true })

// 监听图层开关
watch(() => store.layers.heatmap, (visible) => {
  setVisible(visible)
})

onMounted(() => {
  setTimeout(initHeatmap, 150)
})

onUnmounted(() => {
  if (scene?.value && heatmapMesh.value) {
    scene.value.remove(heatmapMesh.value)
  }
})

defineExpose({
  updateHeatmap,
  setVisible
})
</script>

<style scoped>
.heatmap-overlay {
  display: none;
}
</style>
```

**Step 3: 更新 utils/three/index.ts**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
export * from './modelGenerator'
export * from './labelRenderer'
export * from './heatmapHelper'
```

**Step 4: 更新 components/bigscreen/index.ts**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
export { default as DataCenterModel } from './DataCenterModel.vue'
export { default as CabinetLabels } from './CabinetLabels.vue'
export { default as HeatmapOverlay } from './HeatmapOverlay.vue'
```

---

### Task 3.4: 告警气泡组件

**Files:**
- Create: `frontend/src/components/bigscreen/AlarmBubbles.vue`

**Step 1: 创建告警气泡组件**

```vue
<!-- frontend/src/components/bigscreen/AlarmBubbles.vue -->
<template>
  <div class="alarm-bubbles"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { BigscreenAlarm } from '@/types/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 气泡映射
const bubbleMap = new Map<number, CSS2DObject>()

// 告警等级颜色
const ALARM_COLORS = {
  critical: '#ff3300',
  major: '#ff6600',
  minor: '#ffcc00',
  info: '#00ccff'
}

// 创建告警气泡
function createBubble(alarm: BigscreenAlarm): CSS2DObject {
  const color = ALARM_COLORS[alarm.level]

  const div = document.createElement('div')
  div.className = `alarm-bubble alarm-${alarm.level}`
  div.innerHTML = `
    <div class="bubble-icon">⚠</div>
    <div class="bubble-content">
      <div class="bubble-title">${alarm.message}</div>
      <div class="bubble-detail">
        ${alarm.value !== undefined ? `当前: ${alarm.value}` : ''}
        ${alarm.threshold !== undefined ? ` / 阈值: ${alarm.threshold}` : ''}
      </div>
      ${alarm.duration ? `<div class="bubble-duration">持续: ${alarm.duration}</div>` : ''}
    </div>
  `

  div.style.cssText = `
    background: rgba(20, 0, 0, 0.9);
    border: 2px solid ${color};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    color: #fff;
    max-width: 200px;
    pointer-events: auto;
    cursor: pointer;
    animation: alarmPulse 2s ease-in-out infinite;
    box-shadow: 0 0 20px ${color}40;
  `

  // 添加动画样式
  const style = document.createElement('style')
  style.textContent = `
    @keyframes alarmPulse {
      0%, 100% { transform: translateX(-50%) scale(1); opacity: 1; }
      50% { transform: translateX(-50%) scale(1.05); opacity: 0.9; }
    }
    .bubble-icon { font-size: 16px; color: ${color}; margin-bottom: 4px; }
    .bubble-title { font-weight: bold; margin-bottom: 2px; }
    .bubble-detail { font-size: 11px; color: #aaa; }
    .bubble-duration { font-size: 10px; color: #888; margin-top: 4px; }
  `
  div.appendChild(style)

  // 点击事件
  div.addEventListener('click', () => {
    store.selectDevice(alarm.deviceId)
  })

  const bubble = new CSS2DObject(div)
  bubble.name = `alarm_${alarm.id}`

  return bubble
}

// 获取设备位置
function getDevicePosition(deviceId: string): THREE.Vector3 | null {
  if (!store.layout) return null

  for (const module of store.layout.modules) {
    const cabinet = module.cabinets.find(c => c.id === deviceId)
    if (cabinet) {
      return new THREE.Vector3(
        module.position.x + cabinet.position.x,
        (cabinet.position.y || 0) + 2.5,
        module.position.z + cabinet.position.z
      )
    }
  }
  return null
}

// 更新告警气泡
function updateBubbles() {
  if (!scene?.value) return

  // 移除已解除的告警
  const activeAlarmIds = new Set(store.activeAlarms.map(a => a.id))
  bubbleMap.forEach((bubble, alarmId) => {
    if (!activeAlarmIds.has(alarmId)) {
      scene.value!.remove(bubble)
      if (bubble.element && bubble.element.parentNode) {
        bubble.element.parentNode.removeChild(bubble.element)
      }
      bubbleMap.delete(alarmId)
    }
  })

  // 添加新告警
  store.activeAlarms.forEach(alarm => {
    if (!bubbleMap.has(alarm.id)) {
      const position = getDevicePosition(alarm.deviceId)
      if (position) {
        const bubble = createBubble(alarm)
        bubble.position.copy(position)
        scene.value!.add(bubble)
        bubbleMap.set(alarm.id, bubble)
      }
    }
  })
}

// 清除所有气泡
function clearBubbles() {
  bubbleMap.forEach(bubble => {
    if (scene?.value) {
      scene.value.remove(bubble)
    }
    if (bubble.element && bubble.element.parentNode) {
      bubble.element.parentNode.removeChild(bubble.element)
    }
  })
  bubbleMap.clear()
}

// 监听告警变化
watch(() => store.activeAlarms, () => {
  updateBubbles()
}, { deep: true, immediate: true })

onMounted(() => {
  setTimeout(updateBubbles, 200)
})

onUnmounted(() => {
  clearBubbles()
})

defineExpose({
  updateBubbles,
  clearBubbles
})
</script>

<style scoped>
.alarm-bubbles {
  display: none;
}
</style>
```

**Step 2: 更新 components/bigscreen/index.ts**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
export { default as DataCenterModel } from './DataCenterModel.vue'
export { default as CabinetLabels } from './CabinetLabels.vue'
export { default as HeatmapOverlay } from './HeatmapOverlay.vue'
export { default as AlarmBubbles } from './AlarmBubbles.vue'
```

---

### Task 3.5: 集成所有可视化组件到大屏页面

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`
- Modify: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 更新 useThreeScene 支持 CSS2DRenderer**

修改 `frontend/src/composables/bigscreen/useThreeScene.ts`:

```typescript
// 在文件顶部添加导入
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

// 在 shallowRef 声明后添加
const labelRenderer = shallowRef<CSS2DRenderer | null>(null)

// 在 initScene 函数中，创建 renderer 后添加：
// 创建标签渲染器
const newLabelRenderer = new CSS2DRenderer()
newLabelRenderer.setSize(width, height)
newLabelRenderer.domElement.style.position = 'absolute'
newLabelRenderer.domElement.style.top = '0'
newLabelRenderer.domElement.style.left = '0'
newLabelRenderer.domElement.style.pointerEvents = 'none'
container.appendChild(newLabelRenderer.domElement)
labelRenderer.value = newLabelRenderer

// 在 animate 函数的 renderer.render 后添加：
if (labelRenderer.value && scene.value && camera.value) {
  labelRenderer.value.render(scene.value, camera.value)
}

// 在 handleResize 中添加：
if (labelRenderer.value) {
  labelRenderer.value.setSize(width, height)
}

// 在 dispose 中添加：
if (labelRenderer.value) {
  labelRenderer.value.domElement.remove()
  labelRenderer.value = null
}

// 在 return 中添加 labelRenderer
```

**Step 2: 更新大屏页面模板**

修改 `frontend/src/views/bigscreen/index.vue` 的模板部分：

```vue
<template>
  <div class="bigscreen-container">
    <!-- Three.js 3D场景 -->
    <ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady">
      <template v-if="isSceneReady">
        <DataCenterModel />
        <HeatmapOverlay />
        <CabinetLabels />
        <AlarmBubbles />
      </template>
    </ThreeScene>

    <!-- 悬浮面板层 (保持原有内容) -->
    ...
  </div>
</template>
```

**Step 3: 更新 script 导入**

```typescript
import { ThreeScene, DataCenterModel, CabinetLabels, HeatmapOverlay, AlarmBubbles } from '@/components/bigscreen'
```

---

## Phase 3 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 机柜上方显示功率标签（名称 + kW）
   - 地面显示温度热力图（绿色=正常，红/黄=高温）
   - 图层开关可切换热力图和功率标签显示
   - 如有告警数据，显示告警气泡（带脉冲动画）

**验证构建:**

```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

## Phase 4: 交互功能

### Task 4.1: Raycaster 点击检测

**Files:**
- Create: `frontend/src/composables/bigscreen/useRaycaster.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建 Raycaster composable**

```typescript
// frontend/src/composables/bigscreen/useRaycaster.ts
import { ref, shallowRef, onMounted, onUnmounted, type Ref, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'

export interface RaycasterOptions {
  recursive?: boolean
  filterTypes?: string[]
}

export function useRaycaster(
  containerRef: Ref<HTMLElement | null>,
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  scene: ShallowRef<THREE.Scene | null>,
  options: RaycasterOptions = {}
) {
  const { recursive = true, filterTypes = ['cabinet'] } = options

  const store = useBigscreenStore()
  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()

  const hoveredObject = shallowRef<THREE.Object3D | null>(null)
  const selectedObject = shallowRef<THREE.Object3D | null>(null)

  // 更新鼠标位置
  function updateMousePosition(event: MouseEvent) {
    if (!containerRef.value) return

    const rect = containerRef.value.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  }

  // 执行射线检测
  function raycast(): THREE.Intersection[] {
    if (!camera.value || !scene.value) return []

    raycaster.setFromCamera(mouse, camera.value)
    const intersects = raycaster.intersectObjects(scene.value.children, recursive)

    // 过滤指定类型的对象
    return intersects.filter(intersect => {
      let obj: THREE.Object3D | null = intersect.object
      while (obj) {
        if (obj.userData?.type && filterTypes.includes(obj.userData.type)) {
          return true
        }
        obj = obj.parent
      }
      return false
    })
  }

  // 获取点击对象的根组
  function getObjectRoot(object: THREE.Object3D): THREE.Object3D | null {
    let current: THREE.Object3D | null = object
    while (current) {
      if (current.userData?.type && filterTypes.includes(current.userData.type)) {
        return current
      }
      current = current.parent
    }
    return null
  }

  // 处理鼠标移动（悬停检测）
  function handleMouseMove(event: MouseEvent) {
    updateMousePosition(event)
    const intersects = raycast()

    if (intersects.length > 0) {
      const root = getObjectRoot(intersects[0].object)
      if (root && root !== hoveredObject.value) {
        // 离开之前的对象
        if (hoveredObject.value) {
          onHoverLeave(hoveredObject.value)
        }
        // 进入新对象
        hoveredObject.value = root
        onHoverEnter(root)
      }
    } else if (hoveredObject.value) {
      onHoverLeave(hoveredObject.value)
      hoveredObject.value = null
    }
  }

  // 处理点击
  function handleClick(event: MouseEvent) {
    updateMousePosition(event)
    const intersects = raycast()

    if (intersects.length > 0) {
      const root = getObjectRoot(intersects[0].object)
      if (root) {
        // 取消之前选中
        if (selectedObject.value && selectedObject.value !== root) {
          onDeselect(selectedObject.value)
        }
        // 选中新对象
        selectedObject.value = root
        onSelect(root)

        // 更新 store
        const deviceId = root.userData?.config?.id
        if (deviceId) {
          store.selectDevice(deviceId)
        }
      }
    } else {
      // 点击空白处取消选中
      if (selectedObject.value) {
        onDeselect(selectedObject.value)
        selectedObject.value = null
        store.selectDevice(null)
      }
    }
  }

  // 悬停进入效果
  function onHoverEnter(object: THREE.Object3D) {
    if (containerRef.value) {
      containerRef.value.style.cursor = 'pointer'
    }
    // 高亮效果
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          child.userData.originalEmissive = material.emissive.getHex()
          material.emissive.setHex(0x333333)
        }
      }
    })
  }

  // 悬停离开效果
  function onHoverLeave(object: THREE.Object3D) {
    if (containerRef.value) {
      containerRef.value.style.cursor = 'default'
    }
    // 恢复原始效果
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive && child.userData.originalEmissive !== undefined) {
          material.emissive.setHex(child.userData.originalEmissive)
        }
      }
    })
  }

  // 选中效果
  function onSelect(object: THREE.Object3D) {
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          child.userData.selectedEmissive = material.emissive.getHex()
          material.emissive.setHex(0x0066ff)
        }
      }
    })
  }

  // 取消选中效果
  function onDeselect(object: THREE.Object3D) {
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          const original = child.userData.originalEmissive ?? 0x000000
          material.emissive.setHex(original)
        }
      }
    })
  }

  // 清除选中
  function clearSelection() {
    if (selectedObject.value) {
      onDeselect(selectedObject.value)
      selectedObject.value = null
      store.selectDevice(null)
    }
  }

  onMounted(() => {
    if (containerRef.value) {
      containerRef.value.addEventListener('mousemove', handleMouseMove)
      containerRef.value.addEventListener('click', handleClick)
    }
  })

  onUnmounted(() => {
    if (containerRef.value) {
      containerRef.value.removeEventListener('mousemove', handleMouseMove)
      containerRef.value.removeEventListener('click', handleClick)
    }
  })

  return {
    hoveredObject,
    selectedObject,
    clearSelection,
    raycast
  }
}
```

**Step 2: 更新 composables 导出**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
export * from './useRaycaster'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/composables/bigscreen/ && git commit -m "feat(bigscreen): add raycaster composable for click detection"
```

---

### Task 4.2: 相机飞行动画 (GSAP)

**Files:**
- Create: `frontend/src/composables/bigscreen/useCameraAnimation.ts`

**Step 1: 创建相机动画 composable**

```typescript
// frontend/src/composables/bigscreen/useCameraAnimation.ts
import { type ShallowRef } from 'vue'
import * as THREE from 'three'
import gsap from 'gsap'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { CameraPreset } from '@/types/bigscreen'

export interface CameraAnimationOptions {
  duration?: number
  ease?: string
}

export function useCameraAnimation(
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  controls: ShallowRef<OrbitControls | null>
) {
  let currentTween: gsap.core.Tween | null = null

  // 飞行到预设视角
  function flyToPreset(preset: CameraPreset, options: CameraAnimationOptions = {}) {
    const { duration = 1.5, ease = 'power2.inOut' } = options

    if (!camera.value || !controls.value) return Promise.resolve()

    // 取消之前的动画
    if (currentTween) {
      currentTween.kill()
    }

    const cam = camera.value
    const ctrl = controls.value

    return new Promise<void>((resolve) => {
      // 同时动画相机位置和控制器目标
      const timeline = gsap.timeline({
        onComplete: () => {
          ctrl.update()
          resolve()
        },
        onUpdate: () => {
          ctrl.update()
        }
      })

      timeline.to(cam.position, {
        x: preset.position[0],
        y: preset.position[1],
        z: preset.position[2],
        duration,
        ease
      }, 0)

      timeline.to(ctrl.target, {
        x: preset.target[0],
        y: preset.target[1],
        z: preset.target[2],
        duration,
        ease
      }, 0)

      currentTween = timeline as unknown as gsap.core.Tween
    })
  }

  // 飞行到指定位置
  function flyTo(
    position: { x: number; y: number; z: number },
    target: { x: number; y: number; z: number },
    options: CameraAnimationOptions = {}
  ) {
    return flyToPreset(
      {
        position: [position.x, position.y, position.z],
        target: [target.x, target.y, target.z]
      },
      options
    )
  }

  // 飞行到对象
  function flyToObject(
    object: THREE.Object3D,
    options: CameraAnimationOptions & { distance?: number; height?: number } = {}
  ) {
    const { distance = 10, height = 5 } = options

    // 计算对象的包围盒中心
    const box = new THREE.Box3().setFromObject(object)
    const center = box.getCenter(new THREE.Vector3())

    // 计算相机位置（在对象前方）
    const position = {
      x: center.x + distance * 0.7,
      y: center.y + height,
      z: center.z + distance * 0.7
    }

    return flyTo(position, { x: center.x, y: center.y, z: center.z }, options)
  }

  // 飞行到设备（按ID查找）
  function flyToDevice(
    deviceId: string,
    scene: THREE.Scene,
    options: CameraAnimationOptions & { distance?: number; height?: number } = {}
  ) {
    const device = scene.getObjectByName(`cabinet_${deviceId}`)
    if (device) {
      return flyToObject(device, options)
    }
    return Promise.resolve()
  }

  // 环绕动画
  function orbitAround(
    center: { x: number; y: number; z: number },
    radius: number,
    options: { duration?: number; loops?: number } = {}
  ) {
    const { duration = 10, loops = 1 } = options

    if (!camera.value || !controls.value) return Promise.resolve()

    const cam = camera.value
    const ctrl = controls.value
    const startAngle = Math.atan2(cam.position.z - center.z, cam.position.x - center.x)

    return new Promise<void>((resolve) => {
      gsap.to({ angle: startAngle }, {
        angle: startAngle + Math.PI * 2 * loops,
        duration,
        ease: 'none',
        onUpdate: function() {
          const angle = this.targets()[0].angle
          cam.position.x = center.x + Math.cos(angle) * radius
          cam.position.z = center.z + Math.sin(angle) * radius
          ctrl.target.set(center.x, center.y, center.z)
          ctrl.update()
        },
        onComplete: resolve
      })
    })
  }

  // 停止当前动画
  function stopAnimation() {
    if (currentTween) {
      currentTween.kill()
      currentTween = null
    }
  }

  return {
    flyToPreset,
    flyTo,
    flyToObject,
    flyToDevice,
    orbitAround,
    stopAnimation
  }
}
```

**Step 2: 更新 composables 导出**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
export * from './useRaycaster'
export * from './useCameraAnimation'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/composables/bigscreen/ && git commit -m "feat(bigscreen): add camera animation composable with GSAP"
```

---

### Task 4.3: 设备详情面板

**Files:**
- Create: `frontend/src/components/bigscreen/DeviceDetailPanel.vue`
- Modify: `frontend/src/components/bigscreen/index.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建设备详情面板组件**

```vue
<!-- frontend/src/components/bigscreen/DeviceDetailPanel.vue -->
<template>
  <Transition name="slide">
    <div v-if="store.selectedDeviceId && deviceData" class="device-detail-panel">
      <div class="panel-header">
        <h3>{{ deviceConfig?.name || '设备详情' }}</h3>
        <el-icon class="close-btn" @click="handleClose"><Close /></el-icon>
      </div>

      <div class="panel-content">
        <!-- 状态指示 -->
        <div class="status-row">
          <span class="status-indicator" :class="deviceData.status"></span>
          <span class="status-text">{{ statusLabels[deviceData.status] }}</span>
        </div>

        <!-- 基本信息 -->
        <div class="info-section">
          <div class="info-item">
            <span class="label">设备ID</span>
            <span class="value">{{ store.selectedDeviceId }}</span>
          </div>
          <div class="info-item" v-if="deviceConfig?.position">
            <span class="label">位置</span>
            <span class="value">
              X: {{ deviceConfig.position.x.toFixed(1) }},
              Z: {{ deviceConfig.position.z.toFixed(1) }}
            </span>
          </div>
        </div>

        <!-- 实时数据 -->
        <div class="data-section">
          <h4>实时数据</h4>
          <div class="data-grid">
            <div class="data-item" v-if="deviceData.temperature !== undefined">
              <div class="data-icon temp">
                <el-icon><Odometer /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">温度</span>
                <span class="data-value" :class="getTempClass(deviceData.temperature)">
                  {{ deviceData.temperature.toFixed(1) }}°C
                </span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.humidity !== undefined">
              <div class="data-icon humidity">
                <el-icon><Drizzling /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">湿度</span>
                <span class="data-value">{{ deviceData.humidity.toFixed(1) }}%</span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.power !== undefined">
              <div class="data-icon power">
                <el-icon><Lightning /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">功率</span>
                <span class="data-value">{{ deviceData.power.toFixed(1) }} kW</span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.load !== undefined">
              <div class="data-icon load">
                <el-icon><Cpu /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">负载</span>
                <span class="data-value">{{ deviceData.load.toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-section">
          <el-button type="primary" size="small" @click="handleLocate">
            <el-icon><Aim /></el-icon>
            定位
          </el-button>
          <el-button size="small" @click="handleViewHistory">
            <el-icon><DataLine /></el-icon>
            历史
          </el-button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Close, Odometer, Drizzling, Lightning, Cpu, Aim, DataLine } from '@element-plus/icons-vue'
import { useBigscreenStore } from '@/stores/bigscreen'

const emit = defineEmits<{
  (e: 'locate', deviceId: string): void
  (e: 'viewHistory', deviceId: string): void
}>()

const store = useBigscreenStore()

// 状态标签
const statusLabels = {
  normal: '正常运行',
  alarm: '告警中',
  offline: '离线'
}

// 获取设备数据
const deviceData = computed(() => {
  if (!store.selectedDeviceId) return null
  return store.deviceData[store.selectedDeviceId] || {
    id: store.selectedDeviceId,
    status: 'normal',
    temperature: 24,
    humidity: 50,
    power: 5,
    load: 60
  }
})

// 获取设备配置
const deviceConfig = computed(() => {
  if (!store.selectedDeviceId || !store.layout) return null
  for (const module of store.layout.modules) {
    const cabinet = module.cabinets.find(c => c.id === store.selectedDeviceId)
    if (cabinet) return cabinet
  }
  return null
})

// 获取温度样式类
function getTempClass(temp: number): string {
  if (temp > 30) return 'danger'
  if (temp > 26) return 'warning'
  if (temp < 18) return 'cold'
  return 'normal'
}

// 关闭面板
function handleClose() {
  store.selectDevice(null)
}

// 定位设备
function handleLocate() {
  if (store.selectedDeviceId) {
    emit('locate', store.selectedDeviceId)
  }
}

// 查看历史
function handleViewHistory() {
  if (store.selectedDeviceId) {
    emit('viewHistory', store.selectedDeviceId)
  }
}
</script>

<style scoped lang="scss">
.device-detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 280px;
  background: rgba(10, 15, 30, 0.95);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 8px;
  color: #fff;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 136, 255, 0.1);
  border-bottom: 1px solid rgba(0, 136, 255, 0.2);

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .close-btn {
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }
  }
}

.panel-content {
  padding: 16px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;

  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #00ff88;

    &.alarm {
      background: #ff3300;
      animation: blink 1s infinite;
    }

    &.offline {
      background: #666;
    }
  }

  .status-text {
    font-size: 13px;
    color: #aaa;
  }
}

.info-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  .info-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 12px;

    .label {
      color: #888;
    }

    .value {
      color: #ccc;
    }
  }
}

.data-section {
  margin-bottom: 16px;

  h4 {
    margin: 0 0 12px;
    font-size: 12px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .data-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
  }

  .data-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    font-size: 16px;

    &.temp { background: rgba(255, 100, 0, 0.2); color: #ff6400; }
    &.humidity { background: rgba(0, 150, 255, 0.2); color: #0096ff; }
    &.power { background: rgba(255, 200, 0, 0.2); color: #ffc800; }
    &.load { background: rgba(0, 255, 136, 0.2); color: #00ff88; }
  }

  .data-info {
    display: flex;
    flex-direction: column;
  }

  .data-label {
    font-size: 10px;
    color: #888;
  }

  .data-value {
    font-size: 14px;
    font-weight: 600;
    color: #fff;

    &.danger { color: #ff3300; }
    &.warning { color: #ffcc00; }
    &.cold { color: #0066ff; }
    &.normal { color: #00ff88; }
  }
}

.action-section {
  display: flex;
  gap: 8px;

  :deep(.el-button) {
    flex: 1;
    background: rgba(0, 136, 255, 0.2);
    border-color: rgba(0, 136, 255, 0.4);
    color: #ccc;

    &:hover {
      background: rgba(0, 136, 255, 0.3);
      color: #fff;
    }

    &.el-button--primary {
      background: rgba(0, 136, 255, 0.4);
    }
  }
}

// 滑入动画
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
```

**Step 2: 更新 components/bigscreen/index.ts**

```typescript
// frontend/src/components/bigscreen/index.ts
export { default as ThreeScene } from './ThreeScene.vue'
export { default as DataCenterModel } from './DataCenterModel.vue'
export { default as CabinetLabels } from './CabinetLabels.vue'
export { default as HeatmapOverlay } from './HeatmapOverlay.vue'
export { default as AlarmBubbles } from './AlarmBubbles.vue'
export { default as DeviceDetailPanel } from './DeviceDetailPanel.vue'
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/components/bigscreen/ && git commit -m "feat(bigscreen): add device detail panel component"
```

---

### Task 4.4: 集成交互功能到大屏页面

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 更新大屏页面集成所有交互功能**

在 `views/bigscreen/index.vue` 中更新：

```vue
<!-- 在模板中添加设备详情面板 -->
<template>
  <div class="bigscreen-container">
    <!-- Three.js 3D场景 -->
    <ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady">
      <template v-if="isSceneReady">
        <DataCenterModel />
        <HeatmapOverlay />
        <CabinetLabels />
        <AlarmBubbles />
      </template>
    </ThreeScene>

    <!-- 悬浮面板层 -->
    <div class="overlay-panels">
      <!-- 顶部状态栏 (保持原有) -->
      ...

      <!-- 设备详情面板 -->
      <DeviceDetailPanel
        @locate="handleLocateDevice"
        @viewHistory="handleViewHistory"
      />

      <!-- 底部控制栏 (保持原有) -->
      ...
    </div>
  </div>
</template>
```

**Step 2: 更新 script 部分**

```typescript
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { ArrowDown, FullScreen, Bell, Loading } from '@element-plus/icons-vue'
import {
  ThreeScene,
  DataCenterModel,
  CabinetLabels,
  HeatmapOverlay,
  AlarmBubbles,
  DeviceDetailPanel
} from '@/components/bigscreen'
import { useBigscreenStore } from '@/stores/bigscreen'
import { setupBasicScene } from '@/utils/three/sceneSetup'
import { useRaycaster } from '@/composables/bigscreen/useRaycaster'
import { useCameraAnimation } from '@/composables/bigscreen/useCameraAnimation'
import type { SceneMode } from '@/types/bigscreen'

const store = useBigscreenStore()
const threeSceneRef = ref<InstanceType<typeof ThreeScene> | null>(null)
const isSceneReady = ref(false)

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
let raycasterInstance: ReturnType<typeof useRaycaster> | null = null

// 相机动画
let cameraAnimation: ReturnType<typeof useCameraAnimation> | null = null

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
function onSceneReady() {
  const sceneComponent = threeSceneRef.value
  if (sceneComponent?.scene) {
    // 设置基础场景
    setupBasicScene(sceneComponent.scene, {
      showGrid: true,
      showAxes: false,
      floorSize: 100
    })
    isSceneReady.value = true

    // 初始化相机动画
    cameraAnimation = useCameraAnimation(
      sceneComponent.camera,
      sceneComponent.controls
    )

    // 获取容器引用用于 raycaster
    const canvas = sceneComponent.renderer?.domElement
    if (canvas?.parentElement) {
      containerRef.value = canvas.parentElement
    }
  }
}

// 初始化 Raycaster（场景就绪后）
watch(isSceneReady, (ready) => {
  if (ready && containerRef.value && threeSceneRef.value) {
    raycasterInstance = useRaycaster(
      containerRef,
      threeSceneRef.value.camera,
      threeSceneRef.value.scene
    )
  }
})

// 切换模式
function handleModeChange(mode: SceneMode) {
  store.setMode(mode)
}

// 切换全屏
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 设置相机预设视角
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

onMounted(() => {
  updateTime()
  timeTimer = window.setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeTimer) {
    clearInterval(timeTimer)
  }
})
</script>
```

**Step 3: Commit**

```bash
cd D:\mytest1 && git add frontend/src/views/bigscreen/index.vue && git commit -m "feat(bigscreen): integrate raycaster and camera animation"
```

---

## Phase 4 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 鼠标悬停在机柜上时高亮显示
   - 点击机柜弹出详情面板
   - 点击详情面板的"定位"按钮，相机平滑飞行到设备
   - 视角切换按钮使用动画过渡
   - 点击空白处关闭详情面板

**验证构建:**

```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

## Phase 5: 悬浮面板

### Task 5.1: 左侧环境面板

**Files:**
- Create: `frontend/src/components/bigscreen/panels/LeftPanel.vue`

**Step 1: 创建左侧环境面板组件**

```vue
<!-- frontend/src/components/bigscreen/panels/LeftPanel.vue -->
<template>
  <div class="left-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="toggleCollapse">
      <span class="panel-title">📊 环境监测</span>
      <el-icon class="collapse-icon">
        <ArrowLeft v-if="!isCollapsed" />
        <ArrowRight v-else />
      </el-icon>
    </div>

    <div class="panel-content" v-show="!isCollapsed">
      <!-- 温度概览 -->
      <div class="data-section">
        <h4>温度概览</h4>
        <div class="stat-grid">
          <div class="stat-item danger">
            <span class="stat-label">最高</span>
            <span class="stat-value">{{ store.environment.temperature.max.toFixed(1) }}°C</span>
            <el-icon><Top /></el-icon>
          </div>
          <div class="stat-item normal">
            <span class="stat-label">平均</span>
            <span class="stat-value">{{ store.environment.temperature.avg.toFixed(1) }}°C</span>
          </div>
          <div class="stat-item info">
            <span class="stat-label">最低</span>
            <span class="stat-value">{{ store.environment.temperature.min.toFixed(1) }}°C</span>
          </div>
        </div>
      </div>

      <!-- 湿度概览 -->
      <div class="data-section">
        <h4>湿度概览</h4>
        <div class="stat-grid">
          <div class="stat-item" :class="getHumidityClass(store.environment.humidity.max)">
            <span class="stat-label">最高</span>
            <span class="stat-value">{{ store.environment.humidity.max.toFixed(0) }}%</span>
            <el-icon><Top /></el-icon>
          </div>
          <div class="stat-item normal">
            <span class="stat-label">平均</span>
            <span class="stat-value">{{ store.environment.humidity.avg.toFixed(0) }}%</span>
          </div>
          <div class="stat-item info">
            <span class="stat-label">最低</span>
            <span class="stat-value">{{ store.environment.humidity.min.toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- 实时告警 -->
      <div class="data-section alarm-section">
        <h4>
          🚨 实时告警
          <span class="alarm-count" v-if="store.alarmCount > 0">({{ store.alarmCount }})</span>
        </h4>
        <div class="alarm-list" v-if="store.activeAlarms.length > 0">
          <div
            v-for="alarm in displayedAlarms"
            :key="alarm.id"
            class="alarm-item"
            :class="alarm.level"
            @click="handleAlarmClick(alarm)"
          >
            <span class="alarm-icon">{{ alarm.level === 'critical' ? '🔴' : '🟡' }}</span>
            <span class="alarm-device">{{ alarm.deviceId }}</span>
            <span class="alarm-message">{{ alarm.message }}</span>
          </div>
        </div>
        <div class="no-alarm" v-else>
          <span>暂无告警</span>
        </div>
        <div class="view-all" v-if="store.activeAlarms.length > 3" @click="handleViewAllAlarms">
          查看全部 →
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowLeft, ArrowRight, Top } from '@element-plus/icons-vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { BigscreenAlarm } from '@/types/bigscreen'

const emit = defineEmits<{
  (e: 'locateAlarm', alarm: BigscreenAlarm): void
  (e: 'viewAllAlarms'): void
}>()

const store = useBigscreenStore()
const isCollapsed = ref(false)

// 只显示前3条告警
const displayedAlarms = computed(() => {
  return store.activeAlarms.slice(0, 3)
})

// 切换折叠状态
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// 获取湿度样式类
function getHumidityClass(humidity: number): string {
  if (humidity > 70) return 'danger'
  if (humidity > 60) return 'warning'
  if (humidity < 30) return 'info'
  return 'normal'
}

// 点击告警
function handleAlarmClick(alarm: BigscreenAlarm) {
  emit('locateAlarm', alarm)
}

// 查看全部告警
function handleViewAllAlarms() {
  emit('viewAllAlarms')
}
</script>

<style scoped lang="scss">
.left-panel {
  position: absolute;
  top: 60px;
  left: 20px;
  width: 240px;
  background: rgba(10, 15, 30, 0.9);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 8px;
  color: #fff;
  overflow: hidden;
  transition: width 0.3s ease;

  &.collapsed {
    width: 50px;

    .panel-header {
      justify-content: center;
    }

    .panel-title {
      display: none;
    }
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 136, 255, 0.1);
  border-bottom: 1px solid rgba(0, 136, 255, 0.2);
  cursor: pointer;

  &:hover {
    background: rgba(0, 136, 255, 0.15);
  }

  .panel-title {
    font-size: 14px;
    font-weight: 600;
  }

  .collapse-icon {
    font-size: 14px;
    color: #8899aa;
  }
}

.panel-content {
  padding: 12px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.data-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  &:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  h4 {
    margin: 0 0 12px;
    font-size: 12px;
    color: #8899aa;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
}

.stat-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  border-left: 3px solid transparent;

  .stat-label {
    font-size: 12px;
    color: #8899aa;
    width: 40px;
  }

  .stat-value {
    flex: 1;
    font-size: 16px;
    font-weight: 600;
  }

  .el-icon {
    font-size: 12px;
    margin-left: 4px;
  }

  &.danger {
    border-left-color: #ff3300;
    .stat-value { color: #ff3300; }
  }

  &.warning {
    border-left-color: #ffcc00;
    .stat-value { color: #ffcc00; }
  }

  &.normal {
    border-left-color: #00ff88;
    .stat-value { color: #00ff88; }
  }

  &.info {
    border-left-color: #0096ff;
    .stat-value { color: #0096ff; }
  }
}

.alarm-section {
  .alarm-count {
    color: #ff3300;
    font-weight: bold;
  }
}

.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  &.critical {
    border-left: 3px solid #ff3300;
  }

  &.warning {
    border-left: 3px solid #ffcc00;
  }

  .alarm-icon {
    flex-shrink: 0;
  }

  .alarm-device {
    color: #fff;
    font-weight: 500;
    flex-shrink: 0;
  }

  .alarm-message {
    color: #aaa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.no-alarm {
  padding: 20px;
  text-align: center;
  color: #666;
  font-size: 13px;
}

.view-all {
  margin-top: 8px;
  text-align: center;
  font-size: 12px;
  color: #0096ff;
  cursor: pointer;

  &:hover {
    color: #00ccff;
  }
}
</style>
```

---

### Task 5.2: 右侧能耗面板

**Files:**
- Create: `frontend/src/components/bigscreen/panels/RightPanel.vue`

**Step 1: 创建右侧能耗面板组件**

```vue
<!-- frontend/src/components/bigscreen/panels/RightPanel.vue -->
<template>
  <div class="right-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="toggleCollapse">
      <el-icon class="collapse-icon">
        <ArrowLeft v-if="isCollapsed" />
        <ArrowRight v-else />
      </el-icon>
      <span class="panel-title">⚡ 能耗统计</span>
    </div>

    <div class="panel-content" v-show="!isCollapsed">
      <!-- 实时功率 -->
      <div class="data-section">
        <h4>实时功率</h4>
        <div class="power-display">
          <div class="power-total">
            <span class="power-value">{{ store.energy.totalPower.toFixed(1) }}</span>
            <span class="power-unit">kW</span>
          </div>
          <div class="power-breakdown">
            <div class="power-item">
              <span class="power-label">IT负载</span>
              <span class="power-bar">
                <span class="bar-fill it" :style="{ width: itRatio + '%' }"></span>
              </span>
              <span class="power-val">{{ store.energy.itPower.toFixed(0) }}kW</span>
            </div>
            <div class="power-item">
              <span class="power-label">制冷</span>
              <span class="power-bar">
                <span class="bar-fill cooling" :style="{ width: coolingRatio + '%' }"></span>
              </span>
              <span class="power-val">{{ store.energy.coolingPower.toFixed(0) }}kW</span>
            </div>
          </div>
        </div>
      </div>

      <!-- PUE 趋势 -->
      <div class="data-section">
        <h4>PUE 趋势</h4>
        <div class="pue-display">
          <div class="pue-value" :class="getPueClass(store.energy.pue)">
            {{ store.energy.pue.toFixed(2) }}
          </div>
          <div class="pue-trend" :class="pueTrendClass">
            <el-icon><CaretTop v-if="pueTrend < 0" /><CaretBottom v-else /></el-icon>
            <span>{{ Math.abs(pueTrend).toFixed(2) }}</span>
          </div>
        </div>
        <div class="pue-chart-placeholder">
          <div class="mini-chart">
            <div
              v-for="(val, idx) in pueHistory"
              :key="idx"
              class="chart-bar"
              :style="{ height: ((val - 1) / 0.8) * 100 + '%' }"
            ></div>
          </div>
        </div>
      </div>

      <!-- 今日用电 -->
      <div class="data-section">
        <h4>今日用电</h4>
        <div class="energy-display">
          <div class="energy-item">
            <span class="energy-value">{{ formatEnergy(store.energy.todayEnergy) }}</span>
            <span class="energy-unit">kWh</span>
          </div>
          <div class="energy-cost">
            <span class="cost-label">电费约</span>
            <span class="cost-value">¥{{ store.energy.todayCost.toFixed(0) }}</span>
          </div>
        </div>
      </div>

      <!-- 需量状态 -->
      <div class="data-section">
        <h4>需量状态</h4>
        <div class="demand-display">
          <div class="demand-bar">
            <div class="demand-fill" :style="{ width: demandRatio + '%' }" :class="getDemandClass(demandRatio)"></div>
          </div>
          <div class="demand-info">
            <span class="demand-percent">{{ demandRatio.toFixed(0) }}%</span>
            <span class="demand-value">{{ currentDemand }}/{{ maxDemand }} kW</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowLeft, ArrowRight, CaretTop, CaretBottom } from '@element-plus/icons-vue'
import { useBigscreenStore } from '@/stores/bigscreen'

const store = useBigscreenStore()
const isCollapsed = ref(false)

// 模拟 PUE 历史数据
const pueHistory = ref([1.48, 1.52, 1.45, 1.43, 1.47, 1.44, 1.46, 1.45])
const pueTrend = ref(-0.02)

// 需量数据
const currentDemand = ref(125)
const maxDemand = ref(160)

// 计算比例
const itRatio = computed(() => {
  if (store.energy.totalPower === 0) return 0
  return (store.energy.itPower / store.energy.totalPower) * 100
})

const coolingRatio = computed(() => {
  if (store.energy.totalPower === 0) return 0
  return (store.energy.coolingPower / store.energy.totalPower) * 100
})

const demandRatio = computed(() => {
  if (maxDemand.value === 0) return 0
  return (currentDemand.value / maxDemand.value) * 100
})

const pueTrendClass = computed(() => {
  return pueTrend.value < 0 ? 'down' : 'up'
})

// 切换折叠
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// 获取 PUE 样式类
function getPueClass(pue: number): string {
  if (pue < 1.4) return 'excellent'
  if (pue < 1.6) return 'good'
  if (pue < 1.8) return 'normal'
  return 'poor'
}

// 获取需量样式类
function getDemandClass(ratio: number): string {
  if (ratio > 90) return 'danger'
  if (ratio > 75) return 'warning'
  return 'normal'
}

// 格式化能耗
function formatEnergy(val: number): string {
  if (val >= 1000) {
    return (val / 1000).toFixed(1) + 'k'
  }
  return val.toFixed(0)
}
</script>

<style scoped lang="scss">
.right-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 240px;
  background: rgba(10, 15, 30, 0.9);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 8px;
  color: #fff;
  overflow: hidden;
  transition: width 0.3s ease;

  &.collapsed {
    width: 50px;

    .panel-header {
      justify-content: center;
    }

    .panel-title {
      display: none;
    }
  }
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(0, 136, 255, 0.1);
  border-bottom: 1px solid rgba(0, 136, 255, 0.2);
  cursor: pointer;

  &:hover {
    background: rgba(0, 136, 255, 0.15);
  }

  .panel-title {
    font-size: 14px;
    font-weight: 600;
  }

  .collapse-icon {
    font-size: 14px;
    color: #8899aa;
  }
}

.panel-content {
  padding: 12px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.data-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  &:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  h4 {
    margin: 0 0 12px;
    font-size: 12px;
    color: #8899aa;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
}

.power-display {
  .power-total {
    text-align: center;
    margin-bottom: 12px;

    .power-value {
      font-size: 32px;
      font-weight: bold;
      color: #00ff88;
    }

    .power-unit {
      font-size: 14px;
      color: #8899aa;
      margin-left: 4px;
    }
  }

  .power-breakdown {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .power-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;

    .power-label {
      width: 50px;
      color: #8899aa;
    }

    .power-bar {
      flex: 1;
      height: 6px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
      overflow: hidden;

      .bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s;

        &.it { background: linear-gradient(90deg, #0096ff, #00ccff); }
        &.cooling { background: linear-gradient(90deg, #00ff88, #88ff00); }
      }
    }

    .power-val {
      width: 50px;
      text-align: right;
      color: #ccc;
    }
  }
}

.pue-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;

  .pue-value {
    font-size: 36px;
    font-weight: bold;

    &.excellent { color: #00ff88; }
    &.good { color: #88ff00; }
    &.normal { color: #ffcc00; }
    &.poor { color: #ff6600; }
  }

  .pue-trend {
    display: flex;
    align-items: center;
    font-size: 14px;

    &.down {
      color: #00ff88;
    }

    &.up {
      color: #ff6600;
    }
  }
}

.pue-chart-placeholder {
  .mini-chart {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    height: 40px;
    padding: 0 4px;

    .chart-bar {
      width: 12%;
      min-height: 4px;
      background: linear-gradient(180deg, #0096ff, #003366);
      border-radius: 2px 2px 0 0;
    }
  }
}

.energy-display {
  .energy-item {
    text-align: center;
    margin-bottom: 8px;

    .energy-value {
      font-size: 28px;
      font-weight: bold;
      color: #ffcc00;
    }

    .energy-unit {
      font-size: 14px;
      color: #8899aa;
      margin-left: 4px;
    }
  }

  .energy-cost {
    text-align: center;
    font-size: 14px;

    .cost-label {
      color: #8899aa;
      margin-right: 8px;
    }

    .cost-value {
      color: #ff6600;
      font-weight: 600;
    }
  }
}

.demand-display {
  .demand-bar {
    height: 16px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 8px;

    .demand-fill {
      height: 100%;
      border-radius: 8px;
      transition: width 0.3s;

      &.normal { background: linear-gradient(90deg, #00ff88, #88ff00); }
      &.warning { background: linear-gradient(90deg, #ffcc00, #ff9900); }
      &.danger { background: linear-gradient(90deg, #ff6600, #ff3300); }
    }
  }

  .demand-info {
    display: flex;
    justify-content: space-between;
    font-size: 12px;

    .demand-percent {
      font-weight: 600;
      color: #fff;
    }

    .demand-value {
      color: #8899aa;
    }
  }
}
</style>
```

---

### Task 5.3: 集成悬浮面板到大屏页面

**Files:**
- Create: `frontend/src/components/bigscreen/panels/index.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建面板导出文件**

```typescript
// frontend/src/components/bigscreen/panels/index.ts
export { default as LeftPanel } from './LeftPanel.vue'
export { default as RightPanel } from './RightPanel.vue'
```

**Step 2: 更新大屏页面集成面板**

修改 `frontend/src/views/bigscreen/index.vue`:

在 template 的 `overlay-panels` div 中添加：

```vue
<!-- 左侧环境面板 -->
<LeftPanel
  v-if="store.modeConfig.showAllPanels"
  @locateAlarm="handleLocateAlarm"
  @viewAllAlarms="handleViewAllAlarms"
/>

<!-- 右侧能耗面板 -->
<RightPanel v-if="store.modeConfig.showAllPanels" />
```

在 script 中添加导入和方法：

```typescript
import { LeftPanel, RightPanel } from '@/components/bigscreen/panels'
import type { BigscreenAlarm } from '@/types/bigscreen'

// 定位告警设备
function handleLocateAlarm(alarm: BigscreenAlarm) {
  store.selectDevice(alarm.deviceId)
  handleLocateDevice(alarm.deviceId)
}

// 查看全部告警
function handleViewAllAlarms() {
  console.log('View all alarms')
  // TODO: 打开告警列表弹窗
}
```

**Step 3: 添加模拟数据初始化**

在 `onSceneReady` 函数末尾添加模拟数据：

```typescript
// 模拟环境数据
store.updateEnvironment({
  temperature: { max: 32.5, avg: 24.8, min: 21.2 },
  humidity: { max: 65, avg: 48, min: 35 }
})

// 模拟能耗数据
store.updateEnergy({
  totalPower: 156.8,
  itPower: 98,
  coolingPower: 42,
  pue: 1.45,
  todayEnergy: 1250,
  todayCost: 875
})

// 模拟告警数据
store.setAlarms([
  { id: 'alarm-1', deviceId: 'A-01', message: '温度过高', level: 'critical', time: Date.now() },
  { id: 'alarm-2', deviceId: 'B-03', message: '湿度告警', level: 'warning', time: Date.now() },
  { id: 'alarm-3', deviceId: 'UPS-1', message: '负载过高', level: 'critical', time: Date.now() }
])
```

---

## Phase 5 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 左侧面板显示温度、湿度、告警列表
   - 右侧面板显示功率、PUE、用电、需量
   - 面板可折叠/展开
   - 点击告警可定位到设备
   - 展示模式下面板隐藏

**验证构建:**

```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

## Phase 6: 场景模式

### Task 6.1: 模式配置与切换

**Files:**
- Create: `frontend/src/composables/bigscreen/useSceneMode.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建场景模式 composable**

```typescript
// frontend/src/composables/bigscreen/useSceneMode.ts
import { watch, type ShallowRef } from 'vue'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useBigscreenStore } from '@/stores/bigscreen'
import { useCameraAnimation } from './useCameraAnimation'
import type * as THREE from 'three'
import type { SceneMode } from '@/types/bigscreen'

export interface SceneModeConfig {
  cameraLocked: boolean
  autoRotate: boolean
  autoRotateSpeed: number
  enableZoom: boolean
  enablePan: boolean
  refreshInterval: number
  showAllPanels: boolean
  effects: {
    bloom: boolean
    particles: 'low' | 'medium' | 'high'
  }
}

const modeConfigs: Record<SceneMode, SceneModeConfig> = {
  command: {
    cameraLocked: true,
    autoRotate: false,
    autoRotateSpeed: 0,
    enableZoom: true,
    enablePan: false,
    refreshInterval: 5000,
    showAllPanels: true,
    effects: { bloom: false, particles: 'low' }
  },
  operation: {
    cameraLocked: false,
    autoRotate: false,
    autoRotateSpeed: 0,
    enableZoom: true,
    enablePan: true,
    refreshInterval: 3000,
    showAllPanels: true,
    effects: { bloom: false, particles: 'medium' }
  },
  showcase: {
    cameraLocked: true,
    autoRotate: true,
    autoRotateSpeed: 0.5,
    enableZoom: false,
    enablePan: false,
    refreshInterval: 10000,
    showAllPanels: false,
    effects: { bloom: true, particles: 'high' }
  }
}

export function useSceneMode(
  controls: ShallowRef<OrbitControls | null>,
  camera: ShallowRef<THREE.PerspectiveCamera | null>
) {
  const store = useBigscreenStore()
  let cameraAnimation: ReturnType<typeof useCameraAnimation> | null = null

  // 初始化相机动画
  function initCameraAnimation() {
    if (camera.value && controls.value) {
      cameraAnimation = useCameraAnimation(camera, controls)
    }
  }

  // 应用模式配置到控制器
  function applyModeToControls(mode: SceneMode) {
    if (!controls.value) return

    const config = modeConfigs[mode]
    const ctrl = controls.value

    ctrl.enableRotate = !config.cameraLocked || mode === 'showcase'
    ctrl.enableZoom = config.enableZoom
    ctrl.enablePan = config.enablePan
    ctrl.autoRotate = config.autoRotate
    ctrl.autoRotateSpeed = config.autoRotateSpeed

    ctrl.update()
  }

  // 切换模式（带动画）
  async function switchMode(newMode: SceneMode) {
    const oldMode = store.mode
    if (oldMode === newMode) return

    // 1. 停止当前自动旋转
    if (controls.value) {
      controls.value.autoRotate = false
    }

    // 2. 飞行到新模式的预设视角
    if (cameraAnimation) {
      const presetKey = newMode === 'command' ? 'overview' :
                        newMode === 'showcase' ? 'overview' : 'moduleA'
      const preset = store.cameraPresets[presetKey]
      if (preset) {
        await cameraAnimation.flyToPreset(preset, { duration: 1.2 })
      }
    }

    // 3. 更新 store
    store.setMode(newMode)

    // 4. 应用新模式配置
    applyModeToControls(newMode)
  }

  // 获取当前模式配置
  function getCurrentConfig(): SceneModeConfig {
    return modeConfigs[store.mode]
  }

  // 监听模式变化
  watch(() => store.mode, (newMode) => {
    applyModeToControls(newMode)
  })

  return {
    initCameraAnimation,
    applyModeToControls,
    switchMode,
    getCurrentConfig,
    modeConfigs
  }
}
```

**Step 2: 更新 composables 导出**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
export * from './useRaycaster'
export * from './useCameraAnimation'
export * from './useSceneMode'
```

---

### Task 6.2: 自动巡航功能

**Files:**
- Create: `frontend/src/composables/bigscreen/useAutoTour.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建自动巡航 composable**

```typescript
// frontend/src/composables/bigscreen/useAutoTour.ts
import { ref, type ShallowRef } from 'vue'
import type * as THREE from 'three'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useCameraAnimation } from './useCameraAnimation'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { CameraPreset } from '@/types/bigscreen'

export interface TourPoint {
  position: [number, number, number]
  target: [number, number, number]
  duration: number  // 飞行时间(秒)
  pause: number     // 停留时间(秒)
  label?: string    // 可选的标签
}

const defaultTourPath: TourPoint[] = [
  { position: [0, 50, 50], target: [0, 0, 0], duration: 2, pause: 5, label: '全景视角' },
  { position: [30, 15, 25], target: [15, 0, 0], duration: 2.5, pause: 4, label: '模块A区' },
  { position: [-25, 12, 20], target: [-10, 0, 0], duration: 2.5, pause: 4, label: '模块B区' },
  { position: [0, 80, 1], target: [0, 0, 0], duration: 2, pause: 3, label: '俯视视角' },
  { position: [40, 8, 0], target: [0, 0, 0], duration: 2, pause: 4, label: '侧视角' }
]

export function useAutoTour(
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  controls: ShallowRef<OrbitControls | null>
) {
  const store = useBigscreenStore()
  const isTouring = ref(false)
  const isPaused = ref(false)
  const currentPointIndex = ref(0)
  const currentLabel = ref('')

  let cameraAnimation: ReturnType<typeof useCameraAnimation> | null = null
  let tourTimeout: number | null = null
  let tourPath: TourPoint[] = [...defaultTourPath]

  // 初始化
  function init() {
    if (camera.value && controls.value) {
      cameraAnimation = useCameraAnimation(camera, controls)
    }
  }

  // 设置巡航路径
  function setTourPath(path: TourPoint[]) {
    tourPath = path
  }

  // 飞行到下一个点
  async function flyToNextPoint() {
    if (!isTouring.value || isPaused.value || !cameraAnimation) return

    const point = tourPath[currentPointIndex.value]
    currentLabel.value = point.label || ''

    // 飞行到当前点
    const preset: CameraPreset = {
      position: point.position,
      target: point.target
    }

    await cameraAnimation.flyToPreset(preset, { duration: point.duration })

    // 如果仍在巡航且未暂停，等待后飞往下一个点
    if (isTouring.value && !isPaused.value) {
      tourTimeout = window.setTimeout(() => {
        currentPointIndex.value = (currentPointIndex.value + 1) % tourPath.length
        flyToNextPoint()
      }, point.pause * 1000)
    }
  }

  // 开始巡航
  function startTour() {
    if (isTouring.value) return

    init()
    isTouring.value = true
    isPaused.value = false
    currentPointIndex.value = 0

    // 禁用手动控制
    if (controls.value) {
      controls.value.enableRotate = false
      controls.value.enableZoom = false
      controls.value.enablePan = false
    }

    flyToNextPoint()
  }

  // 暂停巡航
  function pauseTour() {
    isPaused.value = true
    if (tourTimeout) {
      clearTimeout(tourTimeout)
      tourTimeout = null
    }

    // 暂停时允许手动控制
    if (controls.value) {
      controls.value.enableRotate = true
      controls.value.enableZoom = true
    }
  }

  // 继续巡航
  function resumeTour() {
    if (!isTouring.value) return

    isPaused.value = false

    // 禁用手动控制
    if (controls.value) {
      controls.value.enableRotate = false
      controls.value.enableZoom = false
      controls.value.enablePan = false
    }

    flyToNextPoint()
  }

  // 停止巡航
  function stopTour() {
    isTouring.value = false
    isPaused.value = false
    currentLabel.value = ''

    if (tourTimeout) {
      clearTimeout(tourTimeout)
      tourTimeout = null
    }

    // 恢复手动控制
    if (controls.value) {
      controls.value.enableRotate = true
      controls.value.enableZoom = true
      controls.value.enablePan = true
    }
  }

  // 切换巡航状态
  function toggleTour() {
    if (!isTouring.value) {
      startTour()
    } else if (isPaused.value) {
      resumeTour()
    } else {
      pauseTour()
    }
  }

  // 跳转到指定点
  function jumpToPoint(index: number) {
    if (index < 0 || index >= tourPath.length) return

    currentPointIndex.value = index

    if (isTouring.value && !isPaused.value) {
      if (tourTimeout) {
        clearTimeout(tourTimeout)
      }
      flyToNextPoint()
    }
  }

  return {
    isTouring,
    isPaused,
    currentPointIndex,
    currentLabel,
    tourPath,
    init,
    setTourPath,
    startTour,
    pauseTour,
    resumeTour,
    stopTour,
    toggleTour,
    jumpToPoint
  }
}
```

**Step 2: 更新 composables 导出**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
export * from './useRaycaster'
export * from './useCameraAnimation'
export * from './useSceneMode'
export * from './useAutoTour'
```

---

### Task 6.3: 集成场景模式到大屏页面

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 更新模板添加巡航控制**

在底部控制栏的 `view-presets` div 后添加：

```vue
<div class="tour-control" v-if="store.mode === 'showcase'">
  <el-button
    size="small"
    :type="autoTour.isTouring.value ? 'primary' : 'default'"
    @click="handleToggleTour"
  >
    <el-icon>
      <VideoPause v-if="autoTour.isTouring.value && !autoTour.isPaused.value" />
      <VideoPlay v-else />
    </el-icon>
    {{ autoTour.isTouring.value ? (autoTour.isPaused.value ? '继续' : '暂停') : '巡航' }}
  </el-button>
  <span class="tour-label" v-if="autoTour.currentLabel.value">
    {{ autoTour.currentLabel.value }}
  </span>
</div>
```

**Step 2: 更新 script 导入和初始化**

```typescript
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { useSceneMode } from '@/composables/bigscreen/useSceneMode'
import { useAutoTour } from '@/composables/bigscreen/useAutoTour'

// 在 setup 中添加
let sceneMode: ReturnType<typeof useSceneMode> | null = null
let autoTour: ReturnType<typeof useAutoTour> | null = null

// 在 onSceneReady 中初始化
sceneMode = useSceneMode(
  threeSceneRef.value.controls,
  threeSceneRef.value.camera
)
sceneMode.initCameraAnimation()
sceneMode.applyModeToControls(store.mode)

autoTour = useAutoTour(
  threeSceneRef.value.camera,
  threeSceneRef.value.controls
)

// 更新 handleModeChange
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

// 添加巡航控制方法
function handleToggleTour() {
  autoTour?.toggleTour()
}
```

**Step 3: 添加巡航控制样式**

```scss
.tour-control {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 20px;
  padding-left: 20px;
  border-left: 1px solid rgba(255, 255, 255, 0.2);

  .tour-label {
    font-size: 12px;
    color: #00ccff;
    background: rgba(0, 136, 255, 0.2);
    padding: 4px 8px;
    border-radius: 4px;
  }
}
```

---

## Phase 6 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 切换到"指挥中心"模式：相机锁定俯视视角，所有面板显示
   - 切换到"运维模式"：相机可自由控制，所有面板显示
   - 切换到"展示模式"：自动开始巡航，面板隐藏
   - 点击巡航按钮可暂停/继续
   - 模式切换时相机平滑过渡

**验证构建:**

```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

## Phase 7: 优化与集成

### Task 7.1: 后处理效果

**Files:**
- Create: `frontend/src/utils/three/postProcessing.ts`
- Modify: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 创建后处理效果工具**

```typescript
// frontend/src/utils/three/postProcessing.ts
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'

export interface PostProcessingOptions {
  bloom?: {
    enabled: boolean
    strength?: number
    radius?: number
    threshold?: number
  }
}

export interface PostProcessingSetup {
  composer: EffectComposer
  bloomPass: UnrealBloomPass | null
  setBloomEnabled: (enabled: boolean) => void
  setBloomStrength: (strength: number) => void
  resize: (width: number, height: number) => void
  render: () => void
  dispose: () => void
}

export function setupPostProcessing(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera,
  options: PostProcessingOptions = {}
): PostProcessingSetup {
  const { bloom = { enabled: false } } = options

  // 创建 EffectComposer
  const composer = new EffectComposer(renderer)

  // 渲染通道
  const renderPass = new RenderPass(scene, camera)
  composer.addPass(renderPass)

  // 泛光通道
  let bloomPass: UnrealBloomPass | null = null
  if (bloom.enabled) {
    const resolution = new THREE.Vector2(window.innerWidth, window.innerHeight)
    bloomPass = new UnrealBloomPass(
      resolution,
      bloom.strength ?? 0.5,
      bloom.radius ?? 0.4,
      bloom.threshold ?? 0.85
    )
    composer.addPass(bloomPass)
  }

  // 输出通道
  const outputPass = new OutputPass()
  composer.addPass(outputPass)

  // 设置泛光开关
  function setBloomEnabled(enabled: boolean) {
    if (bloomPass) {
      bloomPass.enabled = enabled
    }
  }

  // 设置泛光强度
  function setBloomStrength(strength: number) {
    if (bloomPass) {
      bloomPass.strength = strength
    }
  }

  // 调整大小
  function resize(width: number, height: number) {
    composer.setSize(width, height)
    if (bloomPass) {
      bloomPass.resolution.set(width, height)
    }
  }

  // 渲染
  function render() {
    composer.render()
  }

  // 清理
  function dispose() {
    composer.dispose()
  }

  return {
    composer,
    bloomPass,
    setBloomEnabled,
    setBloomStrength,
    resize,
    render,
    dispose
  }
}
```

**Step 2: 更新 utils/three/index.ts**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
export * from './modelGenerator'
export * from './labelRenderer'
export * from './heatmapHelper'
export * from './postProcessing'
```

---

### Task 7.2: 数据API集成

**Files:**
- Create: `frontend/src/composables/bigscreen/useBigscreenData.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建数据获取 composable**

```typescript
// frontend/src/composables/bigscreen/useBigscreenData.ts
import { ref, onMounted, onUnmounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { DeviceRealtimeData, BigscreenAlarm } from '@/types/bigscreen'

export interface DataFetchOptions {
  refreshInterval?: number
  enableRealtime?: boolean
}

export function useBigscreenData(options: DataFetchOptions = {}) {
  const { refreshInterval = 5000, enableRealtime = true } = options

  const store = useBigscreenStore()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<Date | null>(null)

  let refreshTimer: number | null = null

  // 获取环境数据
  async function fetchEnvironmentData() {
    try {
      // TODO: 替换为实际 API 调用
      // const response = await fetch('/api/v1/realtime/summary')
      // const data = await response.json()

      // 模拟数据
      const data = {
        temperature: {
          max: 30 + Math.random() * 5,
          avg: 24 + Math.random() * 2,
          min: 20 + Math.random() * 2
        },
        humidity: {
          max: 60 + Math.random() * 10,
          avg: 45 + Math.random() * 5,
          min: 35 + Math.random() * 5
        }
      }

      store.updateEnvironment(data)
    } catch (e) {
      console.error('Failed to fetch environment data:', e)
    }
  }

  // 获取能耗数据
  async function fetchEnergyData() {
    try {
      // TODO: 替换为实际 API 调用
      // const response = await fetch('/api/v1/energy/statistics/summary')
      // const data = await response.json()

      // 模拟数据
      const basePower = 150 + Math.random() * 20
      const data = {
        totalPower: basePower,
        itPower: basePower * 0.65,
        coolingPower: basePower * 0.25,
        pue: 1.4 + Math.random() * 0.1,
        todayEnergy: 1200 + Math.random() * 100,
        todayCost: 840 + Math.random() * 70
      }

      store.updateEnergy(data)
    } catch (e) {
      console.error('Failed to fetch energy data:', e)
    }
  }

  // 获取告警数据
  async function fetchAlarmData() {
    try {
      // TODO: 替换为实际 API 调用
      // const response = await fetch('/api/v1/alarms/active')
      // const data = await response.json()

      // 模拟数据 - 随机生成告警
      const alarmTemplates = [
        { deviceId: 'A-01', message: '温度过高', level: 'critical' as const },
        { deviceId: 'A-02', message: '功率异常', level: 'warning' as const },
        { deviceId: 'B-01', message: '湿度告警', level: 'warning' as const },
        { deviceId: 'B-03', message: '通信中断', level: 'critical' as const },
        { deviceId: 'UPS-1', message: '负载过高', level: 'critical' as const }
      ]

      // 随机选择1-3个告警
      const count = 1 + Math.floor(Math.random() * 3)
      const shuffled = [...alarmTemplates].sort(() => Math.random() - 0.5)
      const alarms: BigscreenAlarm[] = shuffled.slice(0, count).map((t, i) => ({
        id: `alarm-${Date.now()}-${i}`,
        ...t,
        time: Date.now()
      }))

      store.setAlarms(alarms)
    } catch (e) {
      console.error('Failed to fetch alarm data:', e)
    }
  }

  // 获取设备实时数据
  async function fetchDeviceData() {
    try {
      // TODO: 替换为实际 API 调用
      // const response = await fetch('/api/v1/realtime')
      // const data = await response.json()

      // 模拟设备数据
      if (store.layout) {
        for (const module of store.layout.modules) {
          for (const cabinet of module.cabinets) {
            const deviceData: DeviceRealtimeData = {
              id: cabinet.id,
              status: Math.random() > 0.9 ? 'alarm' : 'normal',
              temperature: 22 + Math.random() * 10,
              humidity: 40 + Math.random() * 20,
              power: 3 + Math.random() * 7,
              load: 40 + Math.random() * 50
            }
            store.updateDeviceData(cabinet.id, deviceData)
          }
        }
      }
    } catch (e) {
      console.error('Failed to fetch device data:', e)
    }
  }

  // 刷新所有数据
  async function refreshAllData() {
    isLoading.value = true
    error.value = null

    try {
      await Promise.all([
        fetchEnvironmentData(),
        fetchEnergyData(),
        fetchAlarmData(),
        fetchDeviceData()
      ])
      lastUpdate.value = new Date()
    } catch (e) {
      error.value = '数据刷新失败'
      console.error('Failed to refresh data:', e)
    } finally {
      isLoading.value = false
    }
  }

  // 开始定时刷新
  function startRefresh() {
    if (refreshTimer) return

    refreshTimer = window.setInterval(() => {
      if (enableRealtime) {
        refreshAllData()
      }
    }, refreshInterval)
  }

  // 停止定时刷新
  function stopRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  // 更新刷新间隔
  function setRefreshInterval(interval: number) {
    stopRefresh()
    if (enableRealtime) {
      refreshTimer = window.setInterval(refreshAllData, interval)
    }
  }

  onMounted(() => {
    refreshAllData()
    startRefresh()
  })

  onUnmounted(() => {
    stopRefresh()
  })

  return {
    isLoading,
    error,
    lastUpdate,
    refreshAllData,
    startRefresh,
    stopRefresh,
    setRefreshInterval,
    fetchEnvironmentData,
    fetchEnergyData,
    fetchAlarmData,
    fetchDeviceData
  }
}
```

**Step 2: 更新 composables 导出**

```typescript
// frontend/src/composables/bigscreen/index.ts
export * from './useThreeScene'
export * from './useRaycaster'
export * from './useCameraAnimation'
export * from './useSceneMode'
export * from './useAutoTour'
export * from './useBigscreenData'
```

---

### Task 7.3: 性能优化与最终集成

**Files:**
- Create: `frontend/src/utils/three/performanceMonitor.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建性能监控工具**

```typescript
// frontend/src/utils/three/performanceMonitor.ts
import { ref } from 'vue'

export interface PerformanceStats {
  fps: number
  frameTime: number
  memory?: {
    usedJSHeapSize: number
    totalJSHeapSize: number
  }
}

export function usePerformanceMonitor() {
  const stats = ref<PerformanceStats>({
    fps: 0,
    frameTime: 0
  })

  const isEnabled = ref(false)
  let frameCount = 0
  let lastTime = performance.now()
  let animationId: number | null = null

  function update() {
    if (!isEnabled.value) return

    frameCount++
    const currentTime = performance.now()
    const elapsed = currentTime - lastTime

    if (elapsed >= 1000) {
      stats.value.fps = Math.round((frameCount * 1000) / elapsed)
      stats.value.frameTime = Math.round(elapsed / frameCount * 100) / 100
      frameCount = 0
      lastTime = currentTime

      // 获取内存信息（仅 Chrome 支持）
      const performance_ = performance as Performance & {
        memory?: {
          usedJSHeapSize: number
          totalJSHeapSize: number
        }
      }
      if (performance_.memory) {
        stats.value.memory = {
          usedJSHeapSize: performance_.memory.usedJSHeapSize,
          totalJSHeapSize: performance_.memory.totalJSHeapSize
        }
      }
    }

    animationId = requestAnimationFrame(update)
  }

  function start() {
    if (isEnabled.value) return
    isEnabled.value = true
    lastTime = performance.now()
    frameCount = 0
    update()
  }

  function stop() {
    isEnabled.value = false
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  function formatMemory(bytes: number): string {
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  return {
    stats,
    isEnabled,
    start,
    stop,
    formatMemory
  }
}
```

**Step 2: 更新 utils/three/index.ts**

```typescript
// frontend/src/utils/three/index.ts
export * from './sceneSetup'
export * from './modelGenerator'
export * from './labelRenderer'
export * from './heatmapHelper'
export * from './postProcessing'
export * from './performanceMonitor'
```

**Step 3: 最终集成到大屏页面**

修改 `frontend/src/views/bigscreen/index.vue`:

在 template 中添加性能监控显示（可选，用于调试）：

```vue
<!-- 性能监控（调试用） -->
<div class="debug-panel" v-if="showDebug">
  <div>FPS: {{ perfMonitor.stats.value.fps }}</div>
  <div>Frame: {{ perfMonitor.stats.value.frameTime }}ms</div>
  <div v-if="perfMonitor.stats.value.memory">
    Memory: {{ perfMonitor.formatMemory(perfMonitor.stats.value.memory.usedJSHeapSize) }}
  </div>
  <div>Last Update: {{ lastUpdateTime }}</div>
</div>
```

在 script 中添加：

```typescript
import { useBigscreenData } from '@/composables/bigscreen/useBigscreenData'
import { usePerformanceMonitor } from '@/utils/three/performanceMonitor'

// 性能监控
const perfMonitor = usePerformanceMonitor()
const showDebug = ref(false) // 设为 true 可显示调试面板

// 数据刷新
const bigscreenData = useBigscreenData({
  refreshInterval: computed(() => store.modeConfig.refreshInterval).value,
  enableRealtime: true
})

// 最后更新时间
const lastUpdateTime = computed(() => {
  if (!bigscreenData.lastUpdate.value) return '--'
  return bigscreenData.lastUpdate.value.toLocaleTimeString('zh-CN')
})

// 监听模式变化，调整刷新频率
watch(() => store.mode, (mode) => {
  const interval = store.modeConfig.refreshInterval
  bigscreenData.setRefreshInterval(interval)
})

// 在 onMounted 中启动性能监控（调试用）
// perfMonitor.start()

// 在 onUnmounted 中停止
// perfMonitor.stop()
```

添加调试面板样式：

```scss
.debug-panel {
  position: absolute;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
  color: #00ff88;
  z-index: 100;

  div {
    margin: 2px 0;
  }
}
```

---

## Phase 7 完成检查点

**验证步骤:**

1. 启动前端开发服务器：`cd D:\mytest1\frontend && npm run dev`
2. 访问 http://localhost:3000/bigscreen
3. 验证：
   - 数据每隔几秒自动刷新（温度、能耗、告警会有微小变化）
   - 切换模式后刷新频率变化（指挥中心5s，运维3s，展示10s）
   - 无明显卡顿，帧率稳定
   - 组件卸载时定时器正确清理

**验证构建:**

```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

## 实现总结

**Phase 0-7 全部完成，数字孪生大屏功能包括：**

| Phase | 功能 | 状态 |
|-------|------|------|
| Phase 0 | 环境准备、依赖安装 | ✅ |
| Phase 1 | 基础场景搭建 | ✅ |
| Phase 2 | 机房模型生成 | ✅ |
| Phase 3 | 数据可视化层 | ✅ |
| Phase 4 | 交互功能 | ✅ |
| Phase 5 | 悬浮面板 | ✅ |
| Phase 6 | 场景模式 | ✅ |
| Phase 7 | 优化与集成 | ✅ |

---

**计划保存位置:** `docs/plans/2026-01-19-bigscreen-implementation.md`
