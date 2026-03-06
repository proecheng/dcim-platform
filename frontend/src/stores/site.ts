import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSites, getSiteSummary } from '@/api/modules/spatial'
import type { Site, SiteSummaryResponse } from '@/api/modules/spatial'
import { siteEvents } from '@/utils/siteEvents'

export const useSiteStore = defineStore('site', () => {
  const currentSiteId = ref<number | null>(
    (() => {
      const saved = localStorage.getItem('current_site_id')
      return saved ? parseInt(saved, 10) : null
    })()
  )
  const sites = ref<Site[]>([])
  const summary = ref<SiteSummaryResponse | null>(null)
  const loading = ref(false)

  const currentSite = computed(() =>
    currentSiteId.value !== null
      ? sites.value.find(s => s.id === currentSiteId.value) ?? null
      : null
  )

  const currentSiteName = computed(() =>
    currentSite.value?.site_name ?? '全部站点'
  )

  async function fetchSites() {
    loading.value = true
    try {
      const res = await getSites()
      sites.value = (res as any).data ?? res
    } catch (e) {
      console.error('获取站点列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary() {
    try {
      const res = await getSiteSummary()
      summary.value = (res as any).data ?? res
    } catch (e) {
      console.error('获取站点汇总失败:', e)
    }
  }

  function switchSite(siteId: number | null) {
    currentSiteId.value = siteId
    if (siteId !== null) {
      localStorage.setItem('current_site_id', String(siteId))
    } else {
      localStorage.removeItem('current_site_id')
    }
    // Story 27.6: 通知所有订阅者（各 Store 重新加载、WebSocket 重连）
    siteEvents.emit(siteId)
  }

  return {
    currentSiteId,
    sites,
    summary,
    loading,
    currentSite,
    currentSiteName,
    fetchSites,
    fetchSummary,
    switchSite,
  }
})
