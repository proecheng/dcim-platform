/**
 * 应用状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface AppSettings {
  sidebarCollapsed: boolean
  theme: 'light' | 'dark'
  language: 'zh-CN' | 'en-US'
  alarmSoundEnabled: boolean
  alarmPopupEnabled: boolean
  refreshInterval: number
}

export const useAppStore = defineStore('app', () => {
  // 侧边栏状态
  const sidebarCollapsed = ref(false)

  // 主题
  const theme = ref<'light' | 'dark'>('light')

  // 语言
  const language = ref<'zh-CN' | 'en-US'>('zh-CN')

  // 告警设置
  const alarmSoundEnabled = ref(true)
  const alarmPopupEnabled = ref(true)

  // 数据刷新间隔（秒）
  const refreshInterval = ref(5)

  // 全屏模式
  const isFullscreen = ref(false)

  // 加载状态
  const globalLoading = ref(false)
  const loadingText = ref('')

  // 面包屑
  const breadcrumbs = ref<{ title: string; path?: string }[]>([])

  // 标签页
  const tabs = ref<{ name: string; path: string; title: string }[]>([])
  const activeTab = ref('')

  // 切换侧边栏
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('sidebar_collapsed', String(sidebarCollapsed.value))
  }

  // 设置侧边栏状态
  function setSidebarCollapsed(collapsed: boolean) {
    sidebarCollapsed.value = collapsed
    localStorage.setItem('sidebar_collapsed', String(collapsed))
  }

  // 切换主题
  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', theme.value)
    localStorage.setItem('theme', theme.value)
  }

  // 设置主题
  function setTheme(t: 'light' | 'dark') {
    theme.value = t
    document.documentElement.setAttribute('data-theme', t)
    localStorage.setItem('theme', t)
  }

  // 设置语言
  function setLanguage(lang: 'zh-CN' | 'en-US') {
    language.value = lang
    localStorage.setItem('language', lang)
  }

  // 切换告警声音
  function toggleAlarmSound() {
    alarmSoundEnabled.value = !alarmSoundEnabled.value
    localStorage.setItem('alarm_sound', String(alarmSoundEnabled.value))
  }

  // 切换告警弹窗
  function toggleAlarmPopup() {
    alarmPopupEnabled.value = !alarmPopupEnabled.value
    localStorage.setItem('alarm_popup', String(alarmPopupEnabled.value))
  }

  // 设置刷新间隔
  function setRefreshInterval(interval: number) {
    refreshInterval.value = interval
    localStorage.setItem('refresh_interval', String(interval))
  }

  // 显示全局加载
  function showLoading(text = '加载中...') {
    globalLoading.value = true
    loadingText.value = text
  }

  // 隐藏全局加载
  function hideLoading() {
    globalLoading.value = false
    loadingText.value = ''
  }

  // 设置面包屑
  function setBreadcrumbs(items: { title: string; path?: string }[]) {
    breadcrumbs.value = items
  }

  // 添加标签页
  function addTab(tab: { name: string; path: string; title: string }) {
    const exists = tabs.value.find(t => t.path === tab.path)
    if (!exists) {
      tabs.value.push(tab)
    }
    activeTab.value = tab.path
  }

  // 移除标签页
  function removeTab(path: string) {
    const index = tabs.value.findIndex(t => t.path === path)
    if (index !== -1) {
      tabs.value.splice(index, 1)
      // 如果关闭的是当前标签，切换到最后一个
      if (activeTab.value === path && tabs.value.length > 0) {
        activeTab.value = tabs.value[tabs.value.length - 1].path
      }
    }
  }

  // 从本地存储初始化
  function initFromStorage() {
    const collapsed = localStorage.getItem('sidebar_collapsed')
    if (collapsed !== null) {
      sidebarCollapsed.value = collapsed === 'true'
    }

    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    if (savedTheme) {
      setTheme(savedTheme)
    }

    const savedLang = localStorage.getItem('language') as 'zh-CN' | 'en-US' | null
    if (savedLang) {
      language.value = savedLang
    }

    const sound = localStorage.getItem('alarm_sound')
    if (sound !== null) {
      alarmSoundEnabled.value = sound === 'true'
    }

    const popup = localStorage.getItem('alarm_popup')
    if (popup !== null) {
      alarmPopupEnabled.value = popup === 'true'
    }

    const interval = localStorage.getItem('refresh_interval')
    if (interval !== null) {
      refreshInterval.value = parseInt(interval, 10) || 5
    }
  }

  // 获取所有设置
  const settings = computed<AppSettings>(() => ({
    sidebarCollapsed: sidebarCollapsed.value,
    theme: theme.value,
    language: language.value,
    alarmSoundEnabled: alarmSoundEnabled.value,
    alarmPopupEnabled: alarmPopupEnabled.value,
    refreshInterval: refreshInterval.value
  }))

  return {
    sidebarCollapsed,
    theme,
    language,
    alarmSoundEnabled,
    alarmPopupEnabled,
    refreshInterval,
    isFullscreen,
    globalLoading,
    loadingText,
    breadcrumbs,
    tabs,
    activeTab,
    settings,
    toggleSidebar,
    setSidebarCollapsed,
    toggleTheme,
    setTheme,
    setLanguage,
    toggleAlarmSound,
    toggleAlarmPopup,
    setRefreshInterval,
    showLoading,
    hideLoading,
    setBreadcrumbs,
    addTab,
    removeTab,
    initFromStorage
  }
})
