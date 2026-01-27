// frontend/src/composables/bigscreen/useAutoTour.ts
import { ref, type ShallowRef } from 'vue'
import type * as THREE from 'three'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useCameraAnimation } from './useCameraAnimation'
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
