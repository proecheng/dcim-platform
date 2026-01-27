// frontend/src/utils/three/performanceMonitor.ts
import { ref } from 'vue'

export interface PerformanceStats {
  fps: number
  frameTime: number
  memory?: {
    usedJSHeapSize: number
    totalJSHeapSize: number
  }
}

export function usePerformanceMonitor() {
  const stats = ref<PerformanceStats>({
    fps: 0,
    frameTime: 0
  })

  const isEnabled = ref(false)
  let frameCount = 0
  let lastTime = performance.now()
  let animationId: number | null = null

  function update() {
    if (!isEnabled.value) return

    frameCount++
    const currentTime = performance.now()
    const elapsed = currentTime - lastTime

    if (elapsed >= 1000) {
      stats.value.fps = Math.round((frameCount * 1000) / elapsed)
      stats.value.frameTime = Math.round(elapsed / frameCount * 100) / 100
      frameCount = 0
      lastTime = currentTime

      // 获取内存信息（仅 Chrome 支持）
      const performance_ = performance as Performance & {
        memory?: {
          usedJSHeapSize: number
          totalJSHeapSize: number
        }
      }
      if (performance_.memory) {
        stats.value.memory = {
          usedJSHeapSize: performance_.memory.usedJSHeapSize,
          totalJSHeapSize: performance_.memory.totalJSHeapSize
        }
      }
    }

    animationId = requestAnimationFrame(update)
  }

  function start() {
    if (isEnabled.value) return
    isEnabled.value = true
    lastTime = performance.now()
    frameCount = 0
    update()
  }

  function stop() {
    isEnabled.value = false
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  function formatMemory(bytes: number): string {
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  return {
    stats,
    isEnabled,
    start,
    stop,
    formatMemory
  }
}
