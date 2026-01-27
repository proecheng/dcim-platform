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

// ============== 材质缓存（性能优化核心）==============
const materialCache = new Map<string, THREE.Material>()

function getOrCreateMaterial(key: string, factory: () => THREE.Material): THREE.Material {
  if (!materialCache.has(key)) {
    materialCache.set(key, factory())
  }
  return materialCache.get(key)!
}

// 共享材质定义
const SharedMaterials = {
  get cabinetBody() {
    return getOrCreateMaterial('cabinet_body', () => new THREE.MeshStandardMaterial({
      color: 0x2a2a3a,
      roughness: 0.25,
      metalness: 0.8,
      envMapIntensity: 1.0
    }))
  },
  get cabinetBodyAlarm() {
    return getOrCreateMaterial('cabinet_body_alarm', () => new THREE.MeshStandardMaterial({
      color: 0x3a2020,
      roughness: 0.25,
      metalness: 0.8,
      envMapIntensity: 1.0
    }))
  },
  get cabinetBodyOffline() {
    return getOrCreateMaterial('cabinet_body_offline', () => new THREE.MeshStandardMaterial({
      color: 0x252525,
      roughness: 0.4,
      metalness: 0.5,
      envMapIntensity: 0.5
    }))
  },
  get cabinetFrame() {
    return getOrCreateMaterial('cabinet_frame', () => new THREE.MeshStandardMaterial({
      color: 0x1a1a2a,
      roughness: 0.2,
      metalness: 0.9,
      envMapIntensity: 1.2
    }))
  },
  get cabinetFront() {
    return getOrCreateMaterial('cabinet_front', () => new THREE.MeshStandardMaterial({
      color: 0x0a0a15,
      roughness: 0.15,
      metalness: 0.95,
      envMapIntensity: 1.5
    }))
  },
  get coolingBody() {
    return getOrCreateMaterial('cooling_body', () => new THREE.MeshStandardMaterial({
      color: 0x4a4a5a,
      roughness: 0.3,
      metalness: 0.6,
      envMapIntensity: 1.0
    }))
  },
  get upsBody() {
    return getOrCreateMaterial('ups_body', () => new THREE.MeshStandardMaterial({
      color: 0x1a3a1a,
      roughness: 0.3,
      metalness: 0.6,
      envMapIntensity: 1.0
    }))
  },
  get wall() {
    return getOrCreateMaterial('wall', () => new THREE.MeshStandardMaterial({
      color: 0x3a3a4a,
      roughness: 0.5,
      metalness: 0.4,
      transparent: true,
      opacity: 0.8,
      envMapIntensity: 0.8
    }))
  },
  get floor() {
    return getOrCreateMaterial('floor_material', () => new THREE.MeshStandardMaterial({
      color: 0x1a1a25,
      roughness: 0.5,
      metalness: 0.3
    }))
  },
  indicatorNormal() {
    return getOrCreateMaterial('indicator_normal', () => new THREE.MeshStandardMaterial({
      color: STATUS_COLORS.normal,
      emissive: STATUS_COLORS.normal,
      emissiveIntensity: 1.0,
      roughness: 0.2,
      metalness: 0.1
    }))
  },
  indicatorAlarm() {
    return getOrCreateMaterial('indicator_alarm', () => new THREE.MeshStandardMaterial({
      color: STATUS_COLORS.alarm,
      emissive: STATUS_COLORS.alarm,
      emissiveIntensity: 1.0,
      roughness: 0.2,
      metalness: 0.1
    }))
  },
  indicatorOffline() {
    return getOrCreateMaterial('indicator_offline', () => new THREE.MeshStandardMaterial({
      color: STATUS_COLORS.offline,
      emissive: STATUS_COLORS.offline,
      emissiveIntensity: 0.3,
      roughness: 0.4,
      metalness: 0.1
    }))
  }
}

// ============== 几何体缓存（性能优化）==============
const geometryCache = new Map<string, THREE.BufferGeometry>()

function getOrCreateGeometry(key: string, factory: () => THREE.BufferGeometry): THREE.BufferGeometry {
  if (!geometryCache.has(key)) {
    geometryCache.set(key, factory())
  }
  return geometryCache.get(key)!
}

// ============== 简化的机柜生成器 ==============

// 创建单个机柜 - 简化版（高性能）
export function createCabinet(config: CabinetConfig): THREE.Group {
  const group = new THREE.Group()
  group.name = `cabinet_${config.id}`
  group.userData = { type: 'cabinet', config }

  const size = config.size || DEFAULT_CABINET_SIZE
  const status = config.status || 'normal'

  // 机柜主体 - 使用简单BoxGeometry
  const bodyGeometry = getOrCreateGeometry(
    `cabinet_body_${size.width}_${size.height}_${size.depth}`,
    () => new THREE.BoxGeometry(size.width, size.height, size.depth)
  )

  // 根据状态选择材质
  const bodyMaterial = status === 'alarm' ? SharedMaterials.cabinetBodyAlarm :
                       status === 'offline' ? SharedMaterials.cabinetBodyOffline :
                       SharedMaterials.cabinetBody

  const body = new THREE.Mesh(bodyGeometry, bodyMaterial)
  body.position.y = size.height / 2
  body.castShadow = true
  body.receiveShadow = true
  body.name = 'body'
  group.add(body)

  // 顶部边框 - 增加层次感
  const topFrameGeometry = getOrCreateGeometry(
    `cabinet_top_frame_${size.width}_${size.depth}`,
    () => new THREE.BoxGeometry(size.width + 0.02, 0.03, size.depth + 0.02)
  )
  const topFrame = new THREE.Mesh(topFrameGeometry, SharedMaterials.cabinetFrame)
  topFrame.position.y = size.height + 0.015
  topFrame.castShadow = true
  group.add(topFrame)

  // 底座
  const baseGeometry = getOrCreateGeometry(
    `cabinet_base_${size.width}_${size.depth}`,
    () => new THREE.BoxGeometry(size.width + 0.04, 0.05, size.depth + 0.04)
  )
  const base = new THREE.Mesh(baseGeometry, SharedMaterials.cabinetFrame)
  base.position.y = 0.025
  base.castShadow = true
  base.receiveShadow = true
  group.add(base)

  // 前面板 - 简单反光面板代替复杂槽位
  const frontPanelGeometry = getOrCreateGeometry(
    `cabinet_front_${size.width}_${size.height}`,
    () => new THREE.PlaneGeometry(size.width * 0.9, size.height * 0.92)
  )
  const frontPanel = new THREE.Mesh(frontPanelGeometry, SharedMaterials.cabinetFront)
  frontPanel.position.set(0, size.height / 2, size.depth / 2 + 0.005)
  frontPanel.name = 'front'
  group.add(frontPanel)

  // 状态指示灯 - 简化的球体
  const indicatorGeometry = getOrCreateGeometry(
    'cabinet_indicator',
    () => new THREE.SphereGeometry(0.04, 16, 16)
  )
  const indicatorMaterial = status === 'alarm' ? SharedMaterials.indicatorAlarm() :
                            status === 'offline' ? SharedMaterials.indicatorOffline() :
                            SharedMaterials.indicatorNormal()

  const indicator = new THREE.Mesh(indicatorGeometry, indicatorMaterial)
  indicator.position.set(size.width / 2 - 0.06, size.height - 0.08, size.depth / 2 + 0.01)
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

// 创建空调单元 - 简化版
export function createCoolingUnit(position: { x: number; z: number }): THREE.Group {
  const group = new THREE.Group()
  group.name = 'cooling_unit'
  group.userData = { type: 'cooling' }

  // 空调主体
  const bodyGeometry = getOrCreateGeometry('cooling_body', () => new THREE.BoxGeometry(1.2, 2.2, 0.8))
  const body = new THREE.Mesh(bodyGeometry, SharedMaterials.coolingBody)
  body.position.y = 1.1
  body.castShadow = true
  body.receiveShadow = true
  group.add(body)

  // 顶部装饰
  const topGeometry = getOrCreateGeometry('cooling_top', () => new THREE.BoxGeometry(1.25, 0.05, 0.85))
  const top = new THREE.Mesh(topGeometry, SharedMaterials.cabinetFrame)
  top.position.y = 2.25
  top.castShadow = true
  group.add(top)

  // 底座
  const baseGeometry = getOrCreateGeometry('cooling_base', () => new THREE.BoxGeometry(1.3, 0.1, 0.9))
  const base = new THREE.Mesh(baseGeometry, SharedMaterials.cabinetFrame)
  base.position.y = 0.05
  base.castShadow = true
  base.receiveShadow = true
  group.add(base)

  // 出风口区域
  const ventGeometry = getOrCreateGeometry('cooling_vent', () => new THREE.PlaneGeometry(1.0, 0.4))
  const ventMaterial = getOrCreateMaterial('cooling_vent_mat', () => new THREE.MeshStandardMaterial({
    color: 0x1a1a2a,
    roughness: 0.2,
    metalness: 0.9
  }))
  const vent = new THREE.Mesh(ventGeometry, ventMaterial)
  vent.position.set(0, 1.9, 0.41)
  group.add(vent)

  // 运行指示灯
  const indicatorGeometry = getOrCreateGeometry('cooling_indicator', () => new THREE.CircleGeometry(0.04, 16))
  const indicator = new THREE.Mesh(indicatorGeometry, SharedMaterials.indicatorNormal())
  indicator.position.set(0.4, 0.5, 0.41)
  group.add(indicator)

  group.position.set(position.x, 0, position.z)

  return group
}

// 创建UPS室 - 简化版
export function createUPSRoom(
  position: { x: number; z: number },
  size: { width: number; length: number }
): THREE.Group {
  const group = new THREE.Group()
  group.name = 'ups_room'
  group.userData = { type: 'infrastructure' }

  const height = 2.5

  // 地板
  const floorGeometry = new THREE.BoxGeometry(size.width, 0.1, size.length)
  const floor = new THREE.Mesh(floorGeometry, SharedMaterials.floor)
  floor.position.y = 0.05
  floor.receiveShadow = true
  group.add(floor)

  // 后墙
  const backWallGeometry = new THREE.BoxGeometry(size.width, height, 0.15)
  const backWall = new THREE.Mesh(backWallGeometry, SharedMaterials.wall)
  backWall.position.set(0, height / 2, -size.length / 2)
  backWall.castShadow = true
  backWall.receiveShadow = true
  group.add(backWall)

  // 左墙
  const sideWallGeometry = new THREE.BoxGeometry(0.15, height, size.length)
  const leftWall = new THREE.Mesh(sideWallGeometry, SharedMaterials.wall)
  leftWall.position.set(-size.width / 2, height / 2, 0)
  leftWall.castShadow = true
  leftWall.receiveShadow = true
  group.add(leftWall)

  // 右墙
  const rightWall = new THREE.Mesh(sideWallGeometry, SharedMaterials.wall)
  rightWall.position.set(size.width / 2, height / 2, 0)
  rightWall.castShadow = true
  rightWall.receiveShadow = true
  group.add(rightWall)

  // UPS设备
  const upsGeometry = getOrCreateGeometry('ups_body', () => new THREE.BoxGeometry(0.8, 1.8, 0.6))
  const upsCount = 3
  for (let i = 0; i < upsCount; i++) {
    const ups = new THREE.Mesh(upsGeometry, SharedMaterials.upsBody)
    ups.position.set(-size.width / 3 + i * (size.width / 3), 0.9, 0)
    ups.castShadow = true
    ups.receiveShadow = true
    group.add(ups)

    // UPS显示屏
    const screenGeometry = getOrCreateGeometry('ups_screen', () => new THREE.PlaneGeometry(0.25, 0.15))
    const screenMaterial = getOrCreateMaterial('ups_screen_mat', () => new THREE.MeshStandardMaterial({
      color: 0x002200,
      emissive: 0x003300,
      emissiveIntensity: 0.5
    }))
    const screen = new THREE.Mesh(screenGeometry, screenMaterial)
    screen.position.set(-size.width / 3 + i * (size.width / 3), 1.5, 0.31)
    group.add(screen)

    // UPS状态灯
    const statusGeometry = getOrCreateGeometry('ups_status', () => new THREE.CircleGeometry(0.03, 16))
    const status = new THREE.Mesh(statusGeometry, SharedMaterials.indicatorNormal())
    status.position.set(-size.width / 3 + i * (size.width / 3) + 0.2, 1.5, 0.31)
    group.add(status)
  }

  group.position.set(position.x, 0, position.z)

  return group
}

// 更新机柜状态
export function updateCabinetStatus(
  cabinet: THREE.Group,
  status: 'normal' | 'alarm' | 'offline'
): void {
  // 更新主体材质
  const body = cabinet.getObjectByName('body') as THREE.Mesh
  if (body) {
    body.material = status === 'alarm' ? SharedMaterials.cabinetBodyAlarm :
                    status === 'offline' ? SharedMaterials.cabinetBodyOffline :
                    SharedMaterials.cabinetBody
  }

  // 更新指示灯材质
  const indicator = cabinet.getObjectByName('indicator') as THREE.Mesh
  if (indicator) {
    indicator.material = status === 'alarm' ? SharedMaterials.indicatorAlarm() :
                         status === 'offline' ? SharedMaterials.indicatorOffline() :
                         SharedMaterials.indicatorNormal()
  }

  // 更新userData
  if (cabinet.userData.config) {
    cabinet.userData.config.status = status
  }
}

// 创建发电机房 - 简化版
export function createPowerRoom(
  position: { x: number; z: number },
  size: { width: number; length: number }
): THREE.Group {
  const group = new THREE.Group()
  group.name = 'power_room'
  group.userData = { type: 'infrastructure' }

  const height = 3.0

  // 地板
  const floorGeometry = new THREE.BoxGeometry(size.width, 0.15, size.length)
  const floor = new THREE.Mesh(floorGeometry, SharedMaterials.floor)
  floor.position.y = 0.075
  floor.receiveShadow = true
  group.add(floor)

  // 三面墙
  const wallConfigs = [
    { geo: [size.width, height, 0.15], pos: [0, height / 2, size.length / 2] },
    { geo: [0.15, height, size.length], pos: [-size.width / 2, height / 2, 0] },
    { geo: [0.15, height, size.length], pos: [size.width / 2, height / 2, 0] }
  ]

  wallConfigs.forEach(w => {
    const wallGeometry = new THREE.BoxGeometry(w.geo[0], w.geo[1], w.geo[2])
    const wall = new THREE.Mesh(wallGeometry, SharedMaterials.wall)
    wall.position.set(w.pos[0], w.pos[1], w.pos[2])
    wall.castShadow = true
    wall.receiveShadow = true
    group.add(wall)
  })

  // 发电机组
  const generatorGeometry = getOrCreateGeometry('generator', () => new THREE.BoxGeometry(2, 1.5, 1.2))
  const generatorMaterial = getOrCreateMaterial('generator_mat', () => new THREE.MeshStandardMaterial({
    color: 0x2a4a2a,
    roughness: 0.3,
    metalness: 0.6,
    envMapIntensity: 1.0
  }))
  const generator = new THREE.Mesh(generatorGeometry, generatorMaterial)
  generator.position.set(0, 0.85, 0)
  generator.castShadow = true
  generator.receiveShadow = true
  group.add(generator)

  // 控制面板
  const panelGeometry = getOrCreateGeometry('generator_panel', () => new THREE.BoxGeometry(0.5, 0.8, 0.1))
  const panel = new THREE.Mesh(panelGeometry, SharedMaterials.cabinetFrame)
  panel.position.set(-1.3, 0.7, 0)
  panel.castShadow = true
  group.add(panel)

  // 控制面板显示屏
  const screenGeometry = getOrCreateGeometry('generator_screen', () => new THREE.PlaneGeometry(0.35, 0.25))
  const screenMaterial = getOrCreateMaterial('generator_screen_mat', () => new THREE.MeshStandardMaterial({
    color: 0x001122,
    emissive: 0x002244,
    emissiveIntensity: 0.5
  }))
  const screen = new THREE.Mesh(screenGeometry, screenMaterial)
  screen.position.set(-1.3, 0.85, 0.06)
  group.add(screen)

  group.position.set(position.x, 0, position.z)

  return group
}

// 清理缓存（组件卸载时调用）
export function disposeMaterialsAndGeometries(): void {
  materialCache.forEach(mat => mat.dispose())
  materialCache.clear()

  geometryCache.forEach(geo => geo.dispose())
  geometryCache.clear()
}
