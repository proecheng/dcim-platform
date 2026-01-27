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
  id: number | string
  deviceId: string
  deviceName?: string
  level: 'critical' | 'major' | 'minor' | 'warning' | 'info'
  message: string
  value?: number
  threshold?: number
  duration?: string
  time?: number
  createdAt?: string
}

// Three.js 场景上下文
export interface ThreeContext {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
  controls: any // OrbitControls
}
