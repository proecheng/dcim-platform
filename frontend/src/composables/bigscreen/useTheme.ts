// frontend/src/composables/bigscreen/useTheme.ts
import { ref, computed, watch } from 'vue'
import type { BigscreenTheme, ThemeName } from '@/types/theme'
import { themes, defaultTheme, getTheme, getThemeList } from '@/config/themes'

const STORAGE_KEY = 'bigscreen-theme'

/**
 * 大屏主题管理 composable
 */
export function useTheme() {
  // 当前主题名称
  const currentThemeName = ref<ThemeName>('tech-blue')

  // 当前主题配置
  const currentTheme = computed(() => getTheme(currentThemeName.value))

  // 主题列表
  const themeList = computed(() => getThemeList())

  /**
   * 从 localStorage 加载主题
   */
  function loadTheme() {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && themes[saved as ThemeName]) {
      currentThemeName.value = saved as ThemeName
    }
  }

  /**
   * 保存主题到 localStorage
   */
  function saveTheme() {
    localStorage.setItem(STORAGE_KEY, currentThemeName.value)
  }

  /**
   * 切换主题
   */
  function setTheme(name: ThemeName) {
    if (themes[name]) {
      currentThemeName.value = name
      saveTheme()
      applyThemeCssVariables(themes[name])
    }
  }

  /**
   * 应用主题 CSS 变量
   */
  function applyThemeCssVariables(theme: BigscreenTheme) {
    const root = document.documentElement

    // UI 颜色变量
    root.style.setProperty('--bs-primary-color', theme.ui.primaryColor)
    root.style.setProperty('--bs-secondary-color', theme.ui.secondaryColor)
    root.style.setProperty('--bs-success-color', theme.ui.successColor)
    root.style.setProperty('--bs-warning-color', theme.ui.warningColor)
    root.style.setProperty('--bs-danger-color', theme.ui.dangerColor)
    root.style.setProperty('--bs-background-color', theme.ui.backgroundColor)
    root.style.setProperty('--bs-border-color', theme.ui.borderColor)
    root.style.setProperty('--bs-text-color', theme.ui.textColor)
    root.style.setProperty('--bs-text-color-secondary', theme.ui.textColorSecondary)
    root.style.setProperty('--bs-panel-opacity', String(theme.ui.panelOpacity))

    // 场景背景色
    const bgColor = theme.scene.backgroundColor.toString(16).padStart(6, '0')
    root.style.setProperty('--bs-scene-bg-color', `#${bgColor}`)
  }

  /**
   * 获取场景配置 (供 Three.js 使用)
   */
  function getSceneConfig() {
    return currentTheme.value.scene
  }

  /**
   * 获取材质配置 (供 Three.js 使用)
   */
  function getMaterialsConfig() {
    return currentTheme.value.materials
  }

  /**
   * 获取特效配置
   */
  function getEffectsConfig() {
    return currentTheme.value.effects
  }

  /**
   * 获取 UI 配置
   */
  function getUiConfig() {
    return currentTheme.value.ui
  }

  // 初始化时加载主题
  loadTheme()
  applyThemeCssVariables(currentTheme.value)

  // 监听主题变化
  watch(currentThemeName, () => {
    applyThemeCssVariables(currentTheme.value)
  })

  return {
    currentThemeName,
    currentTheme,
    themeList,
    setTheme,
    getSceneConfig,
    getMaterialsConfig,
    getEffectsConfig,
    getUiConfig
  }
}
