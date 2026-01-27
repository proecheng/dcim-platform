// frontend/src/composables/bigscreen/useKeyboardShortcuts.ts
import { onMounted, onUnmounted, ref } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'

export interface ShortcutAction {
  key: string
  description: string
  action: () => void
  enabled?: boolean
}

export interface KeyboardShortcutsOptions {
  onToggleFullscreen?: () => void
  onToggleTour?: () => void
  onSetCameraOverview?: () => void
  onSetCameraTopDown?: () => void
  onSetCameraFront?: () => void
  onSetCameraSide?: () => void
  onCameraPreset?: (preset: string) => void
  onToggleHeatmap?: () => void
  onTogglePowerFlow?: () => void
  onDrillBack?: () => void
  onCycleLayer?: () => void
  onEscape?: () => void
}

/**
 * 大屏键盘快捷键 composable
 */
export function useKeyboardShortcuts(options: KeyboardShortcutsOptions = {}) {
  const store = useBigscreenStore()
  const isEnabled = ref(true)

  // 当前激活的图层索引（用于Tab切换）
  let currentLayerIndex = 0
  const layerKeys = ['heatmap', 'status', 'power', 'airflow'] as const

  // 快捷键映射
  const shortcuts: Record<string, ShortcutAction> = {
    // 视角切换 (1-4)
    'Digit1': {
      key: '1',
      description: '全景视角',
      action: () => options.onSetCameraOverview?.()
    },
    'Digit2': {
      key: '2',
      description: '俯视视角',
      action: () => options.onSetCameraTopDown?.()
    },
    'Digit3': {
      key: '3',
      description: '前视视角',
      action: () => options.onSetCameraFront?.()
    },
    'Digit4': {
      key: '4',
      description: '侧视视角',
      action: () => options.onSetCameraSide?.()
    },

    // 功能键
    'Space': {
      key: 'Space',
      description: '开始/暂停巡航',
      action: () => options.onToggleTour?.()
    },
    'Escape': {
      key: 'Esc',
      description: '返回上一级',
      action: () => options.onDrillBack?.()
    },
    'KeyF': {
      key: 'F',
      description: '全屏切换',
      action: () => options.onToggleFullscreen?.()
    },

    // 图层切换
    'Tab': {
      key: 'Tab',
      description: '切换图层',
      action: () => {
        currentLayerIndex = (currentLayerIndex + 1) % layerKeys.length
        const layerKey = layerKeys[currentLayerIndex]
        // 关闭其他图层，只开启当前图层
        layerKeys.forEach(key => {
          store.layers[key] = key === layerKey
        })
        options.onCycleLayer?.()
      }
    },
    'KeyH': {
      key: 'H',
      description: '切换热力图',
      action: () => {
        store.toggleLayer('heatmap')
        options.onToggleHeatmap?.()
      }
    },
    'KeyP': {
      key: 'P',
      description: '切换电力流向',
      action: () => {
        store.toggleLayer('power')
        options.onTogglePowerFlow?.()
      }
    },

    // 快捷重置
    'KeyR': {
      key: 'R',
      description: '重置视角',
      action: () => options.onSetCameraOverview?.()
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    // 如果在输入框中，不处理快捷键
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLTextAreaElement
    ) {
      return
    }

    // 如果快捷键被禁用
    if (!isEnabled.value) {
      return
    }

    const shortcut = shortcuts[event.code]
    if (shortcut && shortcut.enabled !== false) {
      event.preventDefault()
      shortcut.action()
    }
  }

  /**
   * 启用快捷键
   */
  function enable() {
    isEnabled.value = true
  }

  /**
   * 禁用快捷键
   */
  function disable() {
    isEnabled.value = false
  }

  /**
   * 获取所有快捷键列表
   */
  function getShortcutList(): { key: string; description: string }[] {
    return Object.values(shortcuts).map(s => ({
      key: s.key,
      description: s.description
    }))
  }

  /**
   * 动态添加快捷键
   */
  function addShortcut(code: string, shortcut: ShortcutAction) {
    shortcuts[code] = shortcut
  }

  /**
   * 移除快捷键
   */
  function removeShortcut(code: string) {
    delete shortcuts[code]
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    isEnabled,
    enable,
    disable,
    getShortcutList,
    addShortcut,
    removeShortcut
  }
}
