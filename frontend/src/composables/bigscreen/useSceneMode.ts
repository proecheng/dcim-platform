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
