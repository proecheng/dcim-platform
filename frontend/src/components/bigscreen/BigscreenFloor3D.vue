<!-- frontend/src/components/bigscreen/BigscreenFloor3D.vue -->
<template>
  <div class="floor-3d-view" ref="containerRef">
    <!-- WebGL不支持时的降级提示 -->
    <div v-if="webglError" class="webgl-fallback">
      <div class="fallback-icon">⚠️</div>
      <div class="fallback-text">{{ webglError }}</div>
      <div class="fallback-hint">已自动切换到2D平面图模式</div>
    </div>

    <!-- 悬浮提示 -->
    <div
      v-if="hoveredCabinet && !webglError"
      class="cabinet-tooltip"
      :style="tooltipStyle"
    >
      <div class="tooltip-name">{{ hoveredCabinet.name }}</div>
      <div class="tooltip-code">{{ hoveredCabinet.code }}</div>
      <div :class="['tooltip-status', hoveredCabinet.status]">
        {{ statusLabel(hoveredCabinet.status) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { getSpatialTree } from '@/api/modules/spatial'
import type { SpatialTreeNode, TreeFloor, TreeRow } from '@/api/modules/spatial'
import { useBigscreenStore } from '@/stores/bigscreen'

// ==================== 类型定义 ====================

/** 机柜渲染信息 */
interface CabinetInfo {
  id: string
  code: string
  name: string
  status: 'normal' | 'alarm' | 'offline'
  mesh: THREE.Mesh
}

/** 悬浮提示数据 */
interface TooltipData {
  name: string
  code: string
  status: string
}

// ==================== Props & Emits ====================

const props = defineProps<{
  /** 当前楼层编码 */
  floorCode: string
}>()

const emit = defineEmits<{
  /** 设备点击事件 */
  (e: 'cabinetClick', cabinetId: string): void
  /** WebGL不支持，请求降级 */
  (e: 'fallback'): void
}>()

// ==================== 常量 ====================

/** 标准42U机柜尺寸 (米) */
const CABINET_WIDTH = 0.6
const CABINET_HEIGHT = 2.0
const CABINET_DEPTH = 1.2

/** 通道宽度 (米) */
const COLD_AISLE_WIDTH = 1.2
const HOT_AISLE_WIDTH = 0.9

/** 机柜间距 (米) */
const CABINET_GAP = 0.05

/** 默认布局: 4行×10列 */
const DEFAULT_ROWS = 4
const DEFAULT_COLS = 10

/** 状态颜色 */
const STATUS_COLORS = {
  normal: 0x00cc66,
  alarm: 0xff3333,
  offline: 0x666666
} as const

// ==================== 响应式状态 ====================

const store = useBigscreenStore()
const containerRef = ref<HTMLDivElement>()
const webglError = ref('')
const hoveredCabinet = ref<TooltipData | null>(null)
const mousePos = ref({ x: 0, y: 0 })

const tooltipStyle = computed(() => ({
  left: `${mousePos.value.x + 15}px`,
  top: `${mousePos.value.y + 15}px`
}))

// ==================== Three.js 对象 ====================

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let animationId: number | null = null
let resizeObserver: ResizeObserver | null = null

/** 机柜信息映射 (mesh.uuid → CabinetInfo) */
const cabinetMap = new Map<string, CabinetInfo>()

/** 告警脉冲动画时钟 */
let alarmClock = 0

// ==================== 工具函数 ====================

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    normal: '正常运行',
    alarm: '告警中',
    offline: '离线'
  }
  return map[status] || status
}

/** 检测WebGL支持 */
function checkWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    return gl !== null
  } catch {
    return false
  }
}

// ==================== 场景初始化 ====================

function initScene(): boolean {
  if (!containerRef.value) return false

  // WebGL检测
  if (!checkWebGL()) {
    webglError.value = '当前浏览器不支持WebGL'
    emit('fallback')
    return false
  }

  const container = containerRef.value
  const rect = container.getBoundingClientRect()

  // 渲染器
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(rect.width, rect.height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    container.appendChild(renderer.domElement)
  } catch {
    webglError.value = '3D场景初始化失败'
    emit('fallback')
    return false
  }

  // 场景
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0a0a1a)
  scene.fog = new THREE.Fog(0x0a0a1a, 30, 80)

  // 相机
  camera = new THREE.PerspectiveCamera(50, rect.width / rect.height, 0.1, 200)
  camera.position.set(12, 10, 12)

  // 控制器 (旋转/缩放/平移)
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 3
  controls.maxDistance = 60
  controls.maxPolarAngle = Math.PI / 2.1
  controls.target.set(0, 1, 0)

  // 光照
  const ambientLight = new THREE.AmbientLight(0x334466, 0.6)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight.position.set(15, 20, 10)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.set(1024, 1024)
  dirLight.shadow.camera.near = 1
  dirLight.shadow.camera.far = 50
  dirLight.shadow.camera.left = -20
  dirLight.shadow.camera.right = 20
  dirLight.shadow.camera.top = 20
  dirLight.shadow.camera.bottom = -20
  scene.add(dirLight)

  // 补光
  const fillLight = new THREE.DirectionalLight(0x4488cc, 0.3)
  fillLight.position.set(-10, 8, -5)
  scene.add(fillLight)

  return true
}

// ==================== 场景构建 ====================

/** 创建地板 */
function createFloor(width: number, depth: number) {
  if (!scene) return

  const geometry = new THREE.PlaneGeometry(width, depth)
  const material = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e,
    roughness: 0.8,
    metalness: 0.2
  })
  const floor = new THREE.Mesh(geometry, material)
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  scene.add(floor)

  // 网格线
  const gridHelper = new THREE.GridHelper(Math.max(width, depth), Math.max(width, depth) * 2, 0x222244, 0x111133)
  gridHelper.position.y = 0.01
  scene.add(gridHelper)
}

/** 创建通道标识 */
function createAisle(
  x: number, z: number,
  width: number, depth: number,
  type: 'cold' | 'hot'
) {
  if (!scene) return

  const color = type === 'cold' ? 0x0066ff : 0xff3300
  const geometry = new THREE.PlaneGeometry(width, depth)
  const material = new THREE.MeshStandardMaterial({
    color,
    transparent: true,
    opacity: 0.15,
    side: THREE.DoubleSide
  })
  const aisleMesh = new THREE.Mesh(geometry, material)
  aisleMesh.rotation.x = -Math.PI / 2
  aisleMesh.position.set(x, 0.02, z)
  scene.add(aisleMesh)
}

/** 创建单个机柜 */
function createCabinet(
  x: number, z: number,
  id: string, code: string, name: string,
  status: 'normal' | 'alarm' | 'offline'
): CabinetInfo | null {
  if (!scene) return null

  const geometry = new THREE.BoxGeometry(CABINET_WIDTH, CABINET_HEIGHT, CABINET_DEPTH)
  const material = new THREE.MeshStandardMaterial({
    color: STATUS_COLORS[status],
    roughness: 0.4,
    metalness: 0.6
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(x, CABINET_HEIGHT / 2, z)
  mesh.castShadow = true
  mesh.receiveShadow = true
  scene.add(mesh)

  // 机柜顶部边框线
  const edges = new THREE.EdgesGeometry(geometry)
  const lineMaterial = new THREE.LineBasicMaterial({
    color: 0x00ccff,
    transparent: true,
    opacity: 0.3
  })
  const wireframe = new THREE.LineSegments(edges, lineMaterial)
  wireframe.position.copy(mesh.position)
  scene.add(wireframe)

  const info: CabinetInfo = { id, code, name, status, mesh }
  cabinetMap.set(mesh.uuid, info)
  return info
}

/** 获取机柜状态 */
function getCabinetStatus(cabinetId: string): 'normal' | 'alarm' | 'offline' {
  const data = store.deviceData[cabinetId]
  if (!data) return 'normal'
  return data.status
}

/** 从拓扑数据构建场景 */
function buildSceneFromTopology(floorData: TreeFloor) {
  if (!scene) return

  // 收集所有行和机柜
  const allRows: Array<{ row: TreeRow; roomId: number }> = []
  for (const room of floorData.rooms) {
    for (const row of room.rows) {
      allRows.push({ row, roomId: room.id })
    }
  }

  if (allRows.length === 0) {
    console.warn(`[BigscreenFloor3D] 楼层 ${props.floorCode} 无拓扑行数据，使用默认布局`)
    buildDefaultScene()
    return
  }

  // 计算场景尺寸
  let maxCabinetsInRow = 0
  for (const { row } of allRows) {
    maxCabinetsInRow = Math.max(maxCabinetsInRow, row.cabinets.length)
  }
  if (maxCabinetsInRow === 0) maxCabinetsInRow = DEFAULT_COLS

  const sceneWidth = maxCabinetsInRow * (CABINET_WIDTH + CABINET_GAP) + 4
  const rowSpacing = CABINET_DEPTH + COLD_AISLE_WIDTH
  const sceneDepth = allRows.length * rowSpacing + 4

  createFloor(sceneWidth + 4, sceneDepth + 4)

  // 起始偏移（居中）
  const startX = -(maxCabinetsInRow * (CABINET_WIDTH + CABINET_GAP)) / 2
  const startZ = -(allRows.length * rowSpacing) / 2

  allRows.forEach(({ row }, rowIndex) => {
    const rowZ = startZ + rowIndex * rowSpacing
    const aisleType = row.aisle_type || 'none'

    // 创建通道标识
    if (aisleType === 'cold' || aisleType === 'hot') {
      const aisleWidth = aisleType === 'cold' ? COLD_AISLE_WIDTH : HOT_AISLE_WIDTH
      const cabCount = row.cabinets.length || maxCabinetsInRow
      const aisleLength = cabCount * (CABINET_WIDTH + CABINET_GAP)
      const aisleCenterX = startX + aisleLength / 2
      const aisleZ = rowZ + CABINET_DEPTH / 2 + aisleWidth / 2
      createAisle(aisleCenterX, aisleZ, aisleLength, aisleWidth, aisleType)
    }

    // 创建机柜
    if (row.cabinets.length > 0) {
      row.cabinets.forEach((cab, colIndex) => {
        const x = startX + colIndex * (CABINET_WIDTH + CABINET_GAP) + CABINET_WIDTH / 2
        const status = getCabinetStatus(String(cab.id))
        createCabinet(x, rowZ, String(cab.id), cab.cabinet_code, cab.cabinet_name, status)
      })
    } else {
      // 行存在但无机柜，生成占位
      for (let col = 0; col < DEFAULT_COLS; col++) {
        const x = startX + col * (CABINET_WIDTH + CABINET_GAP) + CABINET_WIDTH / 2
        const fakeId = `${row.row_code}-C${String(col + 1).padStart(2, '0')}`
        createCabinet(x, rowZ, fakeId, fakeId, fakeId, 'normal')
      }
    }
  })

  // 调整相机
  if (camera && controls) {
    camera.position.set(sceneWidth * 0.6, sceneDepth * 0.5, sceneDepth * 0.6)
    controls.target.set(0, 1, 0)
    controls.update()
  }
}

/** 构建默认4×10布局 */
function buildDefaultScene() {
  if (!scene) return

  const totalCols = DEFAULT_COLS
  const totalRows = DEFAULT_ROWS
  const rowSpacing = CABINET_DEPTH + COLD_AISLE_WIDTH
  const sceneWidth = totalCols * (CABINET_WIDTH + CABINET_GAP) + 4
  const sceneDepth = totalRows * rowSpacing + 4

  createFloor(sceneWidth + 4, sceneDepth + 4)

  const startX = -(totalCols * (CABINET_WIDTH + CABINET_GAP)) / 2
  const startZ = -(totalRows * rowSpacing) / 2

  for (let row = 0; row < totalRows; row++) {
    const rowZ = startZ + row * rowSpacing
    // 交替冷热通道
    const aisleType: 'cold' | 'hot' = row % 2 === 0 ? 'cold' : 'hot'
    const aisleWidth = aisleType === 'cold' ? COLD_AISLE_WIDTH : HOT_AISLE_WIDTH
    const aisleLength = totalCols * (CABINET_WIDTH + CABINET_GAP)
    const aisleCenterX = startX + aisleLength / 2
    const aisleZ = rowZ + CABINET_DEPTH / 2 + aisleWidth / 2
    createAisle(aisleCenterX, aisleZ, aisleLength, aisleWidth, aisleType)

    for (let col = 0; col < totalCols; col++) {
      const x = startX + col * (CABINET_WIDTH + CABINET_GAP) + CABINET_WIDTH / 2
      const id = `demo-R${row + 1}-C${String(col + 1).padStart(2, '0')}`
      createCabinet(x, rowZ, id, id, `机柜 R${row + 1}-C${col + 1}`, 'normal')
    }
  }

  if (camera && controls) {
    camera.position.set(sceneWidth * 0.6, sceneDepth * 0.5, sceneDepth * 0.6)
    controls.target.set(0, 1, 0)
    controls.update()
  }
}

// ==================== 数据加载 ====================

async function loadFloorTopology() {
  if (!scene) return

  // 清除旧场景对象（保留光照）
  clearSceneObjects()

  try {
    const res = await getSpatialTree()
    const treeData: SpatialTreeNode[] = (res as unknown as { data: SpatialTreeNode[] }).data || (res as unknown as SpatialTreeNode[])

    // 在所有站点中查找匹配楼层
    let matchedFloor: TreeFloor | null = null
    if (Array.isArray(treeData)) {
      for (const site of treeData) {
        for (const floor of site.floors) {
          if (floor.floor_code === props.floorCode) {
            matchedFloor = floor
            break
          }
        }
        if (matchedFloor) break
      }
    }

    if (matchedFloor && matchedFloor.rooms.length > 0) {
      buildSceneFromTopology(matchedFloor)
    } else {
      console.info(`[BigscreenFloor3D] 楼层 ${props.floorCode} 无拓扑数据，使用默认布局`)
      buildDefaultScene()
    }
  } catch (err) {
    console.warn('[BigscreenFloor3D] 获取拓扑数据失败，使用默认布局:', err)
    buildDefaultScene()
  }
}

/** 清除场景中的机柜和地板对象（保留光照） */
function clearSceneObjects() {
  if (!scene) return

  cabinetMap.clear()

  const toRemove: THREE.Object3D[] = []
  scene.traverse((obj) => {
    if (obj instanceof THREE.Mesh || obj instanceof THREE.LineSegments || obj instanceof THREE.GridHelper) {
      toRemove.push(obj)
    }
  })
  for (const obj of toRemove) {
    scene.remove(obj)
    // Mesh / LineSegments / GridHelper 均需 dispose geometry + material
    if ('geometry' in obj && (obj as THREE.Mesh).geometry) {
      ;(obj as THREE.Mesh).geometry.dispose()
    }
    if ('material' in obj) {
      const mat = (obj as THREE.Mesh).material
      if (Array.isArray(mat)) {
        mat.forEach(m => m.dispose())
      } else if (mat) {
        mat.dispose()
      }
    }
  }
}

// ==================== 交互 ====================

const raycaster = new THREE.Raycaster()
const mouse = new THREE.Vector2()

function onMouseMove(event: MouseEvent) {
  if (!containerRef.value || !camera || !scene) return

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  mousePos.value = { x: event.clientX - rect.left, y: event.clientY - rect.top }

  raycaster.setFromCamera(mouse, camera)
  const meshes = Array.from(cabinetMap.values()).map(c => c.mesh)
  const intersects = raycaster.intersectObjects(meshes)

  if (intersects.length > 0) {
    const hit = intersects[0].object as THREE.Mesh
    const info = cabinetMap.get(hit.uuid)
    if (info) {
      hoveredCabinet.value = { name: info.name, code: info.code, status: info.status }
      containerRef.value.style.cursor = 'pointer'
      return
    }
  }

  hoveredCabinet.value = null
  containerRef.value.style.cursor = 'grab'
}

function onClick(event: MouseEvent) {
  if (!containerRef.value || !camera || !scene) return

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const meshes = Array.from(cabinetMap.values()).map(c => c.mesh)
  const intersects = raycaster.intersectObjects(meshes)

  if (intersects.length > 0) {
    const hit = intersects[0].object as THREE.Mesh
    const info = cabinetMap.get(hit.uuid)
    if (info) {
      emit('cabinetClick', info.id)
    }
  }
}

// ==================== 动画循环 ====================

function animate() {
  animationId = requestAnimationFrame(animate)

  if (!renderer || !scene || !camera || !controls) return

  controls.update()

  // 告警脉冲动画
  alarmClock += 0.03
  const pulse = (Math.sin(alarmClock * 3) + 1) / 2
  cabinetMap.forEach((info) => {
    if (info.status === 'alarm') {
      const mat = info.mesh.material as THREE.MeshStandardMaterial
      mat.emissive.setHex(0xff0000)
      mat.emissiveIntensity = 0.2 + pulse * 0.6
    }
  })

  renderer.render(scene, camera)
}

// ==================== 状态更新 ====================

/** 根据store中的设备数据更新机柜颜色 */
function updateCabinetStatuses() {
  cabinetMap.forEach((info) => {
    const newStatus = getCabinetStatus(info.id)
    if (newStatus !== info.status) {
      info.status = newStatus
      const mat = info.mesh.material as THREE.MeshStandardMaterial
      mat.color.setHex(STATUS_COLORS[newStatus])
      if (newStatus !== 'alarm') {
        mat.emissive.setHex(0x000000)
        mat.emissiveIntensity = 0
      }
    }
  })
}

// ==================== 尺寸自适应 ====================

function handleResize() {
  if (!containerRef.value || !renderer || !camera) return

  const rect = containerRef.value.getBoundingClientRect()
  camera.aspect = rect.width / rect.height
  camera.updateProjectionMatrix()
  renderer.setSize(rect.width, rect.height)
}

// ==================== 生命周期 ====================

onMounted(() => {
  const ok = initScene()
  if (!ok) return

  loadFloorTopology()
  animate()

  // 事件监听
  containerRef.value?.addEventListener('mousemove', onMouseMove)
  containerRef.value?.addEventListener('click', onClick)

  // 尺寸监听
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  // 停止动画
  if (animationId !== null) {
    cancelAnimationFrame(animationId)
    animationId = null
  }

  // 移除事件
  containerRef.value?.removeEventListener('mousemove', onMouseMove)
  containerRef.value?.removeEventListener('click', onClick)

  // 停止尺寸监听
  resizeObserver?.disconnect()

  // 释放Three.js资源
  clearSceneObjects()
  if (scene) scene.fog = null
  controls?.dispose()
  renderer?.dispose()
  if (renderer?.domElement && containerRef.value?.contains(renderer.domElement)) {
    containerRef.value.removeChild(renderer.domElement)
  }

  renderer = null
  scene = null
  camera = null
  controls = null
})

// 监听楼层切换
watch(() => props.floorCode, () => {
  loadFloorTopology()
})

// 监听设备数据变化，更新机柜状态
watch(() => store.deviceData, () => {
  updateCabinetStatuses()
}, { deep: true })
</script>

<style scoped lang="scss">
.floor-3d-view {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #0a0a1a;
  overflow: hidden;
}

.webgl-fallback {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #668899;

  .fallback-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .fallback-text {
    font-size: 18px;
    margin-bottom: 8px;
    color: #ff8844;
  }

  .fallback-hint {
    font-size: 14px;
    opacity: 0.7;
  }
}

.cabinet-tooltip {
  position: absolute;
  background: rgba(0, 20, 40, 0.95);
  border: 1px solid rgba(0, 200, 255, 0.5);
  border-radius: 6px;
  padding: 10px 14px;
  pointer-events: none;
  z-index: 100;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);

  .tooltip-name {
    color: #ffffff;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 2px;
  }

  .tooltip-code {
    color: #88ccff;
    font-size: 12px;
    margin-bottom: 4px;
  }

  .tooltip-status {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    display: inline-block;

    &.normal {
      background: rgba(0, 200, 100, 0.3);
      color: #00ff88;
    }
    &.alarm {
      background: rgba(255, 50, 50, 0.3);
      color: #ff5555;
    }
    &.offline {
      background: rgba(100, 100, 100, 0.3);
      color: #888888;
    }
  }
}
</style>
