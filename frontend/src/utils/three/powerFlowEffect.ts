// frontend/src/utils/three/powerFlowEffect.ts
import * as THREE from 'three'

export interface PowerFlowOptions {
  color?: number
  speed?: number
  tubeRadius?: number
  segments?: number
  dashLength?: number
  gapLength?: number
}

export interface PowerFlowLine {
  tube: THREE.Mesh
  animate: () => void
  dispose: () => void
  setVisible: (visible: boolean) => void
  setSpeed: (speed: number) => void
}

/**
 * 创建电力流动线效果
 * 使用 TubeGeometry + UV动画实现流动效果
 */
export function createPowerFlowLine(
  path: THREE.Vector3[],
  scene: THREE.Scene,
  options: PowerFlowOptions = {}
): PowerFlowLine {
  const {
    color = 0x00ccff,
    speed = 0.02,
    tubeRadius = 0.03,
    segments = 64,
    dashLength = 0.3,
    gapLength = 0.2
  } = options

  let currentSpeed = speed

  // 创建曲线
  const curve = new THREE.CatmullRomCurve3(path)

  // 创建管道几何体
  const tubeGeometry = new THREE.TubeGeometry(curve, segments, tubeRadius, 8, false)

  // 创建流动纹理 (使用 canvas 动态生成)
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 32
  const ctx = canvas.getContext('2d')!

  // 绘制渐变虚线纹理
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0)
  gradient.addColorStop(0, `rgba(${(color >> 16) & 255}, ${(color >> 8) & 255}, ${color & 255}, 0)`)
  gradient.addColorStop(0.3, `rgba(${(color >> 16) & 255}, ${(color >> 8) & 255}, ${color & 255}, 1)`)
  gradient.addColorStop(0.5, `rgba(255, 255, 255, 1)`)
  gradient.addColorStop(0.7, `rgba(${(color >> 16) & 255}, ${(color >> 8) & 255}, ${color & 255}, 1)`)
  gradient.addColorStop(1, `rgba(${(color >> 16) & 255}, ${(color >> 8) & 255}, ${color & 255}, 0)`)

  ctx.fillStyle = gradient
  const totalWidth = dashLength + gapLength
  const dashCount = Math.ceil(1 / totalWidth)
  for (let i = 0; i < dashCount; i++) {
    const x = (i * totalWidth) * canvas.width
    const width = dashLength * canvas.width
    ctx.fillRect(x, 0, width, canvas.height)
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.repeat.x = 3

  // 创建材质
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    opacity: 0.9,
    side: THREE.DoubleSide,
    depthWrite: false
  })

  // 创建网格
  const tube = new THREE.Mesh(tubeGeometry, material)
  tube.renderOrder = 10
  scene.add(tube)

  // 动画函数
  function animate() {
    texture.offset.x -= currentSpeed
    if (texture.offset.x < -1) {
      texture.offset.x = 0
    }
  }

  // 清理
  function dispose() {
    scene.remove(tube)
    tubeGeometry.dispose()
    material.dispose()
    texture.dispose()
  }

  // 设置可见性
  function setVisible(visible: boolean) {
    tube.visible = visible
  }

  // 设置速度
  function setSpeed(newSpeed: number) {
    currentSpeed = newSpeed
  }

  return {
    tube,
    animate,
    dispose,
    setVisible,
    setSpeed
  }
}

/**
 * 创建电力流动网络
 * 支持多条路径的流动效果
 */
export function createPowerFlowNetwork(
  scene: THREE.Scene,
  paths: THREE.Vector3[][],
  options: PowerFlowOptions = {}
): {
  lines: PowerFlowLine[]
  animate: () => void
  dispose: () => void
  setVisible: (visible: boolean) => void
} {
  const lines = paths.map(path => createPowerFlowLine(path, scene, options))

  function animate() {
    lines.forEach(line => line.animate())
  }

  function dispose() {
    lines.forEach(line => line.dispose())
  }

  function setVisible(visible: boolean) {
    lines.forEach(line => line.setVisible(visible))
  }

  return {
    lines,
    animate,
    dispose,
    setVisible
  }
}

/**
 * 创建数据流粒子效果
 */
export function createDataFlowParticles(
  path: THREE.Vector3[],
  scene: THREE.Scene,
  options: {
    particleCount?: number
    particleSize?: number
    color?: number
    speed?: number
  } = {}
): {
  particles: THREE.Points
  animate: () => void
  dispose: () => void
} {
  const {
    particleCount = 50,
    particleSize = 0.1,
    color = 0x00ff88,
    speed = 0.005
  } = options

  const curve = new THREE.CatmullRomCurve3(path)

  // 创建粒子位置
  const positions = new Float32Array(particleCount * 3)
  const progress = new Float32Array(particleCount)

  for (let i = 0; i < particleCount; i++) {
    progress[i] = Math.random()
    const point = curve.getPoint(progress[i])
    positions[i * 3] = point.x
    positions[i * 3 + 1] = point.y
    positions[i * 3 + 2] = point.z
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

  const material = new THREE.PointsMaterial({
    color,
    size: particleSize,
    transparent: true,
    opacity: 0.8,
    sizeAttenuation: true,
    depthWrite: false
  })

  const particles = new THREE.Points(geometry, material)
  scene.add(particles)

  function animate() {
    const posAttr = geometry.getAttribute('position') as THREE.BufferAttribute

    for (let i = 0; i < particleCount; i++) {
      progress[i] += speed
      if (progress[i] > 1) progress[i] = 0

      const point = curve.getPoint(progress[i])
      posAttr.setXYZ(i, point.x, point.y, point.z)
    }

    posAttr.needsUpdate = true
  }

  function dispose() {
    scene.remove(particles)
    geometry.dispose()
    material.dispose()
  }

  return {
    particles,
    animate,
    dispose
  }
}
