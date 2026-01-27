// frontend/src/composables/bigscreen/useScreenAdapt.ts
import { ref, onMounted, onUnmounted, computed } from 'vue'

export interface ScreenAdaptOptions {
  designWidth?: number
  designHeight?: number
  minScale?: number
  maxScale?: number
}

/**
 * 大屏自适应 composable
 * 计算缩放比例并设置 CSS 变量，用于 UI 元素适配
 * Three.js 场景保持原生尺寸，由自身的 handleResize 处理
 */
export function useScreenAdapt(options: ScreenAdaptOptions = {}) {
  const {
    designWidth = 1920,
    designHeight = 1080,
    minScale = 0.5,
    maxScale = 2.0
  } = options

  const scale = ref(1)
  const screenWidth = ref(window.innerWidth)
  const screenHeight = ref(window.innerHeight)

  const scaleX = computed(() => screenWidth.value / designWidth)
  const scaleY = computed(() => screenHeight.value / designHeight)

  // 使用较小的缩放比例，确保内容不会超出屏幕
  const actualScale = computed(() => {
    const s = Math.min(scaleX.value, scaleY.value)
    return Math.max(minScale, Math.min(maxScale, s))
  })

  // 是否为宽屏（宽高比大于设计稿）
  const isWideScreen = computed(() => {
    const currentRatio = screenWidth.value / screenHeight.value
    const designRatio = designWidth / designHeight
    return currentRatio > designRatio
  })

  function updateScale() {
    screenWidth.value = window.innerWidth
    screenHeight.value = window.innerHeight
    scale.value = actualScale.value

    // 设置 CSS 变量供样式使用
    const root = document.documentElement
    root.style.setProperty('--bs-scale', String(scale.value))
    root.style.setProperty('--bs-screen-width', `${screenWidth.value}px`)
    root.style.setProperty('--bs-screen-height', `${screenHeight.value}px`)
    root.style.setProperty('--bs-design-width', `${designWidth}px`)
    root.style.setProperty('--bs-design-height', `${designHeight}px`)

    // 根据缩放调整基础字体大小
    const baseFontSize = 14 * scale.value
    root.style.setProperty('--bs-base-font-size', `${baseFontSize}px`)
  }

  onMounted(() => {
    updateScale()
    window.addEventListener('resize', updateScale)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateScale)
  })

  return {
    scale,
    screenWidth,
    screenHeight,
    scaleX,
    scaleY,
    isWideScreen,
    designWidth,
    designHeight,
    updateScale
  }
}
