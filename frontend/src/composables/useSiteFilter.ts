import { watch } from 'vue'
import { useSiteStore } from '@/stores'

/**
 * @deprecated Story 27.6: 请求拦截器已自动注入 site_id，不再需要手动调用 getSiteParams()。
 * 保留 onSiteChange() 供页面级监听站点变更重置 UI 状态使用。
 *
 * 站点过滤 composable — 页面级使用
 *
 * getSiteParams(): 返回当前站点过滤参数 { site_id: number } 或 {}
 * onSiteChange(callback): 监听站点切换，触发回调刷新数据
 */
export function useSiteFilter() {
  const siteStore = useSiteStore()

  function getSiteParams(): Record<string, any> {
    if (siteStore.currentSiteId !== null) {
      return { site_id: siteStore.currentSiteId }
    }
    return {}
  }

  function onSiteChange(callback: () => void) {
    watch(() => siteStore.currentSiteId, () => {
      callback()
    })
  }

  return { getSiteParams, onSiteChange }
}
