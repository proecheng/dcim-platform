/**
 * App Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态正确', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
    expect(store.theme).toBe('light')
    expect(store.language).toBe('zh-CN')
    expect(store.alarmSoundEnabled).toBe(true)
    expect(store.alarmPopupEnabled).toBe(true)
    expect(store.refreshInterval).toBe(5)
    expect(store.isFullscreen).toBe(false)
    expect(store.globalLoading).toBe(false)
    expect(store.loadingText).toBe('')
    expect(store.breadcrumbs).toEqual([])
    expect(store.tabs).toEqual([])
    expect(store.activeTab).toBe('')
  })

  it('toggleSidebar 切换侧边栏并持久化', () => {
    const store = useAppStore()
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'true')
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'false')
  })

  it('setSidebarCollapsed 设置侧边栏状态', () => {
    const store = useAppStore()
    store.setSidebarCollapsed(true)
    expect(store.sidebarCollapsed).toBe(true)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'true')
  })

  it('setTheme 设置主题并持久化', () => {
    const store = useAppStore()
    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
  })

  it('toggleTheme 切换主题', () => {
    const store = useAppStore()
    expect(store.theme).toBe('light')
    store.toggleTheme()
    expect(store.theme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
    store.toggleTheme()
    expect(store.theme).toBe('light')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'light')
  })

  it('setLanguage 设置语言并持久化', () => {
    const store = useAppStore()
    store.setLanguage('en-US')
    expect(store.language).toBe('en-US')
    expect(localStorage.setItem).toHaveBeenCalledWith('language', 'en-US')
  })

  it('toggleAlarmSound 切换告警声音', () => {
    const store = useAppStore()
    store.toggleAlarmSound()
    expect(store.alarmSoundEnabled).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('alarm_sound', 'false')
    store.toggleAlarmSound()
    expect(store.alarmSoundEnabled).toBe(true)
  })

  it('toggleAlarmPopup 切换告警弹窗', () => {
    const store = useAppStore()
    store.toggleAlarmPopup()
    expect(store.alarmPopupEnabled).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('alarm_popup', 'false')
  })

  it('setRefreshInterval 设置刷新间隔', () => {
    const store = useAppStore()
    store.setRefreshInterval(10)
    expect(store.refreshInterval).toBe(10)
    expect(localStorage.setItem).toHaveBeenCalledWith('refresh_interval', '10')
  })

  it('showLoading / hideLoading 控制加载状态', () => {
    const store = useAppStore()
    store.showLoading('正在保存...')
    expect(store.globalLoading).toBe(true)
    expect(store.loadingText).toBe('正在保存...')
    store.hideLoading()
    expect(store.globalLoading).toBe(false)
    expect(store.loadingText).toBe('')
  })

  it('showLoading 默认文本', () => {
    const store = useAppStore()
    store.showLoading()
    expect(store.loadingText).toBe('加载中...')
  })

  it('setBreadcrumbs 设置面包屑', () => {
    const store = useAppStore()
    const items = [{ title: '首页', path: '/' }, { title: '设置' }]
    store.setBreadcrumbs(items)
    expect(store.breadcrumbs).toEqual(items)
  })

  it('addTab 添加标签页并激活标签', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '首页' })
    expect(store.tabs).toHaveLength(1)
    expect(store.activeTab).toBe('/')
  })

  it('addTab 不重复添加相同路径', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '首页' })
    store.addTab({ name: 'home', path: '/', title: '首页' })
    expect(store.tabs).toHaveLength(1)
    expect(store.activeTab).toBe('/')
  })

  it('removeTab 移除标签页', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '首页' })
    store.addTab({ name: 'settings', path: '/settings', title: '设置' })
    store.removeTab('/settings')
    expect(store.tabs).toHaveLength(1)
  })

  it('removeTab 关闭当前标签时切换到最后一个', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '首页' })
    store.addTab({ name: 'settings', path: '/settings', title: '设置' })
    expect(store.activeTab).toBe('/settings')
    store.removeTab('/settings')
    expect(store.activeTab).toBe('/')
  })

  it('removeTab 移除不存在的标签无副作用', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '首页' })
    store.removeTab('/nonexistent')
    expect(store.tabs).toHaveLength(1)
  })

  it('initFromStorage 从 localStorage 恢复状态', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    localStorage.setItem('theme', 'dark')
    localStorage.setItem('language', 'en-US')
    localStorage.setItem('alarm_sound', 'false')
    localStorage.setItem('alarm_popup', 'false')
    localStorage.setItem('refresh_interval', '15')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.sidebarCollapsed).toBe(true)
    expect(store.theme).toBe('dark')
    expect(store.language).toBe('en-US')
    expect(store.alarmSoundEnabled).toBe(false)
    expect(store.alarmPopupEnabled).toBe(false)
    expect(store.refreshInterval).toBe(15)
  })

  it('initFromStorage 无存储时保持默认值', () => {
    const store = useAppStore()
    store.initFromStorage()
    expect(store.sidebarCollapsed).toBe(false)
    expect(store.theme).toBe('light')
    expect(store.language).toBe('zh-CN')
    expect(store.alarmSoundEnabled).toBe(true)
    expect(store.refreshInterval).toBe(5)
  })

  it('initFromStorage 非法 refresh_interval 回退默认值', () => {
    localStorage.setItem('refresh_interval', 'abc')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.refreshInterval).toBe(5)
  })

  it('initFromStorage 迁移旧 alarm_sound_enabled 到 alarm_sound', () => {
    localStorage.setItem('alarm_sound_enabled', 'false')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.alarmSoundEnabled).toBe(false)
    expect(localStorage.getItem('alarm_sound')).toBe('false')
    expect(localStorage.getItem('alarm_sound_enabled')).toBeNull()
  })

  it('initFromStorage 迁移时不覆盖已有的 alarm_sound', () => {
    localStorage.setItem('alarm_sound_enabled', 'false')
    localStorage.setItem('alarm_sound', 'true')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.alarmSoundEnabled).toBe(true)
    expect(localStorage.getItem('alarm_sound')).toBe('true')
  })

  it('settings 计算属性聚合所有设置项', () => {
    const store = useAppStore()
    store.setTheme('dark')
    store.setLanguage('en-US')
    store.setRefreshInterval(10)
    const s = store.settings
    expect(s.theme).toBe('dark')
    expect(s.language).toBe('en-US')
    expect(s.refreshInterval).toBe(10)
    expect(s.sidebarCollapsed).toBe(false)
    expect(s.alarmSoundEnabled).toBe(true)
    expect(s.alarmPopupEnabled).toBe(true)
  })
})
