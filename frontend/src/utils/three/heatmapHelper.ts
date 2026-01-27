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
