// frontend/src/utils/three/alarmPulseEffect.ts
import * as THREE from 'three'

export interface AlarmPulseOptions {
  color?: number
  pulseSpeed?: number
  maxRadius?: number
  ringCount?: number
  height?: number
}

export interface AlarmPulse {
  group: THREE.Group
  animate: (delta: number) => void
  dispose: () => void
  setPosition: (x: number, y: number, z: number) => void
  setColor: (color: number) => void
  setVisible: (visible: boolean) => void
}

/**
 * 创建告警脉冲效果
 * 包含发光球体和向外扩散的波纹环
 */
export function createAlarmPulse(
  scene: THREE.Scene,
  position: THREE.Vector3,
  options: AlarmPulseOptions = {}
): AlarmPulse {
  const {
    color = 0xff4d4f,
    pulseSpeed = 1.5,
    maxRadius = 2,
    ringCount = 3,
    height = 0.1
  } = options

  const group = new THREE.Group()
  group.position.copy(position)

  // 中心发光球
  const sphereGeometry = new THREE.SphereGeometry(0.15, 16, 16)
  const sphereMaterial = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.9
  })
  const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial)
  sphere.position.y = height
  group.add(sphere)

  // 波纹环
  const rings: THREE.Mesh[] = []
  const ringMaterials: THREE.MeshBasicMaterial[] = []

  for (let i = 0; i < ringCount; i++) {
    const ringGeometry = new THREE.RingGeometry(0.1, 0.15, 32)
    const ringMaterial = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
      depthWrite: false
    })
    const ring = new THREE.Mesh(ringGeometry, ringMaterial)
    ring.rotation.x = -Math.PI / 2
    ring.position.y = height * 0.5
    ring.userData.progress = i / ringCount
    rings.push(ring)
    ringMaterials.push(ringMaterial)
    group.add(ring)
  }

  scene.add(group)

  let elapsedTime = 0

  function animate(delta: number) {
    elapsedTime += delta

    // 中心球呼吸效果
    const scale = 1 + Math.sin(elapsedTime * 3) * 0.2
    sphere.scale.set(scale, scale, scale)
    sphereMaterial.opacity = 0.7 + Math.sin(elapsedTime * 3) * 0.3

    // 波纹扩散
    rings.forEach((ring, index) => {
      const progress = ((elapsedTime * pulseSpeed + index * (1 / ringCount)) % 1)
      const radius = progress * maxRadius
      ring.scale.set(radius, radius, 1)
      ringMaterials[index].opacity = 0.6 * (1 - progress)
    })
  }

  function dispose() {
    scene.remove(group)
    sphereGeometry.dispose()
    sphereMaterial.dispose()
    rings.forEach((ring, index) => {
      ring.geometry.dispose()
      ringMaterials[index].dispose()
    })
  }

  function setPosition(x: number, y: number, z: number) {
    group.position.set(x, y, z)
  }

  function setColor(newColor: number) {
    sphereMaterial.color.setHex(newColor)
    ringMaterials.forEach(m => m.color.setHex(newColor))
  }

  function setVisible(visible: boolean) {
    group.visible = visible
  }

  return {
    group,
    animate,
    dispose,
    setPosition,
    setColor,
    setVisible
  }
}

/**
 * 告警脉冲管理器
 * 管理多个告警脉冲效果
 */
export class AlarmPulseManager {
  private scene: THREE.Scene
  private pulses: Map<string, AlarmPulse> = new Map()
  private defaultOptions: AlarmPulseOptions

  constructor(scene: THREE.Scene, options: AlarmPulseOptions = {}) {
    this.scene = scene
    this.defaultOptions = options
  }

  /**
   * 添加告警脉冲
   */
  add(id: string, position: THREE.Vector3, options?: AlarmPulseOptions): AlarmPulse {
    if (this.pulses.has(id)) {
      this.remove(id)
    }

    const pulse = createAlarmPulse(this.scene, position, {
      ...this.defaultOptions,
      ...options
    })
    this.pulses.set(id, pulse)
    return pulse
  }

  /**
   * 移除告警脉冲
   */
  remove(id: string) {
    const pulse = this.pulses.get(id)
    if (pulse) {
      pulse.dispose()
      this.pulses.delete(id)
    }
  }

  /**
   * 更新所有脉冲动画
   */
  animate(delta: number) {
    this.pulses.forEach(pulse => pulse.animate(delta))
  }

  /**
   * 获取脉冲
   */
  get(id: string): AlarmPulse | undefined {
    return this.pulses.get(id)
  }

  /**
   * 清空所有脉冲
   */
  clear() {
    this.pulses.forEach(pulse => pulse.dispose())
    this.pulses.clear()
  }

  /**
   * 获取所有脉冲ID
   */
  getIds(): string[] {
    return Array.from(this.pulses.keys())
  }

  /**
   * 设置告警颜色
   */
  setColor(id: string, color: number) {
    const pulse = this.pulses.get(id)
    if (pulse) {
      pulse.setColor(color)
    }
  }

  /**
   * 根据告警级别获取颜色
   */
  static getLevelColor(level: 'critical' | 'warning' | 'info'): number {
    switch (level) {
      case 'critical': return 0xff4d4f
      case 'warning': return 0xffaa00
      case 'info': return 0x00ccff
      default: return 0xff4d4f
    }
  }
}
