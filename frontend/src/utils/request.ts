import axios, { AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { degradationFlags } from '@/stores/degradation'
import { PUBLIC_AUTH_UNAVAILABLE_EVENT } from '@/utils/authEvents'

// API基础URL - 始终使用相对路径，通过代理访问后端
// 开发环境: Vite 代理转发到 localhost:8080
// 生产环境: Node.js 代理转发到 localhost:8080
const getBaseURL = () => {
  return '/api'
}

const instance = axios.create({
  baseURL: getBaseURL(),
  timeout: 10000
})

export interface RequestConfig extends AxiosRequestConfig {
  silentError?: boolean
}

// 不需要站点过滤的 API 路径（Story 27.6）
export const SITE_FILTER_EXCLUDED_PATHS = [
  '/v1/auth/',           // 认证
  '/v1/spatial/sites',   // 站点管理本身不过滤
  '/v1/system/',         // 系统配置
  '/v1/users/',          // 用户管理
  '/v1/demo/',           // Demo 系统
  '/v1/configs/',        // 全局配置
  '/v1/logs/',           // 系统日志
  '/v1/notification/',   // 通知管理
]

export function shouldInjectSiteId(url: string): boolean {
  return !SITE_FILTER_EXCLUDED_PATHS.some(
    path => url === path || url.startsWith(path.endsWith('/') ? path : path + '/')
  )
}

// 请求拦截器
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // site_id 自动注入（Story 27.6）
    // 直接读 localStorage 而非 useSiteStore()，避免 Pinia 生命周期问题
    // switchSite(null) 使用 removeItem，所以 null 表示"全部站点"
    const siteIdStr = localStorage.getItem('current_site_id')
    if (siteIdStr != null) {
      const siteId = Number(siteIdStr)
      if (!isNaN(siteId) && siteId > 0) {
        const url = config.url || ''
        if (shouldInjectSiteId(url)) {
          if (!config.params) config.params = {}
          // 手动指定优先，不覆盖
          if (config.params.site_id === undefined) {
            config.params.site_id = siteId
          }
        }
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
instance.interceptors.response.use(
  (response) => {
    // 检测降级标志
    const degraded = response.headers['x-degraded']
    if (degraded === 'true') {
      degradationFlags.redisDown = true
      degradationFlags.degradedMessage = '实时数据可能有延迟'
    } else if (degraded === 'false' || !degraded) {
      // 仅在明确收到非降级响应时清除（避免非 realtime 接口误清）
      if (response.config.url?.includes('/realtime')) {
        degradationFlags.redisDown = false
        degradationFlags.degradedMessage = ''
      }
    }
    return response.data
  },
  (error) => {
    const silentError = Boolean((error.config as RequestConfig | undefined)?.silentError)
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        // 公开页面（如大屏）不清 token、不跳登录页，仅静默忽略
        const currentRoute = router.currentRoute.value
        if (currentRoute.meta?.requiresAuth !== false) {
          localStorage.removeItem('token')
          router.push('/login')
          // 防止多个 401 同时弹出多个提示，使用全局标记
          if (!(window as any).__authExpiredShown) {
            ;(window as any).__authExpiredShown = true
            ElMessage.error('登录已过期，请重新登录')
            // 3 秒后重置标记，允许下次再显示
            setTimeout(() => {
              ;(window as any).__authExpiredShown = false
            }, 3000)
          }
        } else {
          window.dispatchEvent(new Event(PUBLIC_AUTH_UNAVAILABLE_EVENT))
        }
      } else if (!silentError && status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else if (!silentError) {
        ElMessage.error(data.detail || '请求失败')
      }
    } else if (!silentError) {
      ElMessage.error('网络错误')
    }
    return Promise.reject(error)
  }
)

// 封装请求方法，返回数据而非AxiosResponse
const request = {
  get<T = any>(url: string, config?: RequestConfig): Promise<T> {
    return instance.get(url, config) as Promise<T>
  },
  post<T = any>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    return instance.post(url, data, config) as Promise<T>
  },
  put<T = any>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    return instance.put(url, data, config) as Promise<T>
  },
  delete<T = any>(url: string, config?: RequestConfig): Promise<T> {
    return instance.delete(url, config) as Promise<T>
  },
  patch<T = any>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    return instance.patch(url, data, config) as Promise<T>
  }
}

export default request
