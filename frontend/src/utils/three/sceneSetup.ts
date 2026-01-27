// frontend/src/utils/three/sceneSetup.ts
import * as THREE from 'three'

// 创建地板 - 增强视觉效果
export function createFloor(width = 100, length = 100): THREE.Group {
  const group = new THREE.Group()
  group.name = 'floor_group'

  // 主地板
  const floorGeometry = new THREE.PlaneGeometry(width, length)
  const floorMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e,
    roughness: 0.6,
    metalness: 0.4
  })

  const floor = new THREE.Mesh(floorGeometry, floorMaterial)
  floor.rotation.x = -Math.PI / 2
  floor.position.y = 0
  floor.receiveShadow = true
  floor.name = 'floor'
  group.add(floor)

  // 创建地板反射区域（中心区域高反光）
  const reflectiveAreaGeometry = new THREE.PlaneGeometry(width * 0.6, length * 0.6)
  const reflectiveAreaMaterial = new THREE.MeshStandardMaterial({
    color: 0x202035,
    roughness: 0.3,
    metalness: 0.7,
    transparent: true,
    opacity: 0.5
  })
  const reflectiveArea = new THREE.Mesh(reflectiveAreaGeometry, reflectiveAreaMaterial)
  reflectiveArea.rotation.x = -Math.PI / 2
  reflectiveArea.position.y = 0.002
  reflectiveArea.receiveShadow = true
  group.add(reflectiveArea)

  // 添加边缘发光线条
  const edgeLinesMaterial = new THREE.LineBasicMaterial({
    color: 0x0066ff,
    transparent: true,
    opacity: 0.3
  })

  // 四条边缘线
  const halfWidth = width / 2
  const halfLength = length / 2
  const edgePoints = [
    [new THREE.Vector3(-halfWidth, 0.01, -halfLength), new THREE.Vector3(halfWidth, 0.01, -halfLength)],
    [new THREE.Vector3(halfWidth, 0.01, -halfLength), new THREE.Vector3(halfWidth, 0.01, halfLength)],
    [new THREE.Vector3(halfWidth, 0.01, halfLength), new THREE.Vector3(-halfWidth, 0.01, halfLength)],
    [new THREE.Vector3(-halfWidth, 0.01, halfLength), new THREE.Vector3(-halfWidth, 0.01, -halfLength)]
  ]

  edgePoints.forEach(points => {
    const geometry = new THREE.BufferGeometry().setFromPoints(points)
    const line = new THREE.Line(geometry, edgeLinesMaterial)
    group.add(line)
  })

  return group
}

// 创建网格线 - 增强科技感
export function createGridHelper(size = 100, divisions = 50): THREE.Group {
  const group = new THREE.Group()
  group.name = 'grid_group'

  // 主网格
  const mainGrid = new THREE.GridHelper(size, divisions, 0x0044aa, 0x002255)
  mainGrid.position.y = 0.01
  mainGrid.name = 'main_grid'
  // 调整网格透明度
  if (mainGrid.material instanceof THREE.Material) {
    mainGrid.material.transparent = true
    mainGrid.material.opacity = 0.4
  } else if (Array.isArray(mainGrid.material)) {
    (mainGrid.material as THREE.Material[]).forEach(m => {
      m.transparent = true
      m.opacity = 0.4
    })
  }
  group.add(mainGrid)

  // 细分网格（更细的线条）
  const fineGrid = new THREE.GridHelper(size, divisions * 2, 0x003388, 0x001133)
  fineGrid.position.y = 0.005
  if (fineGrid.material instanceof THREE.Material) {
    fineGrid.material.transparent = true
    fineGrid.material.opacity = 0.2
  } else if (Array.isArray(fineGrid.material)) {
    (fineGrid.material as THREE.Material[]).forEach(m => {
      m.transparent = true
      m.opacity = 0.2
    })
  }
  group.add(fineGrid)

  return group
}

// 创建环境背景（增强科技感）
export function createEnvironment(scene: THREE.Scene): void {
  // 添加雾效果 - 调整参数增强深度感
  scene.fog = new THREE.FogExp2(0x0a0a1a, 0.015)

  // 创建环境粒子效果（可选的科技感粒子）
  createAmbientParticles(scene)
}

// 创建环境粒子效果
function createAmbientParticles(scene: THREE.Scene): void {
  const particleCount = 200
  const positions = new Float32Array(particleCount * 3)

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 80
    positions[i * 3 + 1] = Math.random() * 20 + 2
    positions[i * 3 + 2] = (Math.random() - 0.5) * 80
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

  const material = new THREE.PointsMaterial({
    color: 0x00aaff,
    size: 0.1,
    transparent: true,
    opacity: 0.4,
    sizeAttenuation: true
  })

  const particles = new THREE.Points(geometry, material)
  particles.name = 'ambient_particles'
  scene.add(particles)
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
