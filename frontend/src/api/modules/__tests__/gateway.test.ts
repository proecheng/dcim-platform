/**
 * 网关管理 API 模块单元测试
 *
 * 覆盖:
 *   - getGatewayList: 列表查询（含分页/筛选参数）
 *   - getGatewaySummary: 状态汇总
 *   - getGatewayDetail: 详情查询
 *   - getGatewayEvents: 事件历史
 *   - pushGatewayConfig: 配置下发
 *   - getConfigHistory: 配置下发历史
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock request 模块
const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/utils/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
  },
}))

import {
  getGatewayList,
  getGatewaySummary,
  getGatewayDetail,
  getGatewayEvents,
  pushGatewayConfig,
  getConfigHistory,
} from '../gateway'

describe('gateway API 模块', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ==================== getGatewayList ====================

  describe('getGatewayList', () => {
    it('无参数时调用正确的 URL', async () => {
      const mockData = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
      mockGet.mockResolvedValue(mockData)

      const result = await getGatewayList()
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways', { params: undefined })
      expect(result).toEqual(mockData)
    })

    it('传递分页和筛选参数', async () => {
      mockGet.mockResolvedValue({ items: [], total: 0 })

      await getGatewayList({ page: 2, page_size: 10, status: 'online', keyword: 'gw' })
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways', {
        params: { page: 2, page_size: 10, status: 'online', keyword: 'gw' },
      })
    })

    it('请求失败时抛出异常', async () => {
      mockGet.mockRejectedValue(new Error('网络错误'))
      await expect(getGatewayList()).rejects.toThrow('网络错误')
    })
  })

  // ==================== getGatewaySummary ====================

  describe('getGatewaySummary', () => {
    it('返回状态汇总数据', async () => {
      const summary = { total: 10, online: 8, offline: 2 }
      mockGet.mockResolvedValue(summary)

      const result = await getGatewaySummary()
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/summary', { params: undefined })
      expect(result).toEqual(summary)
    })

    it('支持 site_id 参数', async () => {
      mockGet.mockResolvedValue({ total: 5, online: 3, offline: 2 })

      await getGatewaySummary({ site_id: 1 })
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/summary', { params: { site_id: 1 } })
    })
  })

  // ==================== getGatewayDetail ====================

  describe('getGatewayDetail', () => {
    it('根据 ID 获取网关详情', async () => {
      const detail = {
        id: 1,
        gateway_id: 'GW-001',
        name: '测试网关',
        status: 'online',
        datasource_count: 3,
        point_count: 50,
      }
      mockGet.mockResolvedValue(detail)

      const result = await getGatewayDetail(1)
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/1')
      expect(result.gateway_id).toBe('GW-001')
    })
  })

  // ==================== getGatewayEvents ====================

  describe('getGatewayEvents', () => {
    it('获取网关事件历史', async () => {
      const events = { items: [{ id: 1, event_type: 'status_change' }], total: 1 }
      mockGet.mockResolvedValue(events)

      const result = await getGatewayEvents(1)
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/1/events', { params: undefined })
      expect(result.items).toHaveLength(1)
    })

    it('支持事件类型筛选', async () => {
      mockGet.mockResolvedValue({ items: [], total: 0 })

      await getGatewayEvents(1, { event_type: 'heartbeat' })
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/1/events', {
        params: { event_type: 'heartbeat' },
      })
    })
  })

  // ==================== pushGatewayConfig ====================

  describe('pushGatewayConfig', () => {
    it('下发配置到指定网关', async () => {
      const response = { id: 1, gateway_id: 'GW-001', status: 'pending', error_message: null }
      mockPost.mockResolvedValue(response)

      const result = await pushGatewayConfig(1)
      expect(mockPost).toHaveBeenCalledWith('/v1/gateways/1/push-config')
      expect(result.status).toBe('pending')
    })

    it('下发失败时抛出异常', async () => {
      mockPost.mockRejectedValue(new Error('网关离线'))
      await expect(pushGatewayConfig(99)).rejects.toThrow('网关离线')
    })
  })

  // ==================== getConfigHistory ====================

  describe('getConfigHistory', () => {
    it('获取配置下发历史', async () => {
      const history = { items: [{ id: 1, status: 'delivered' }], total: 1 }
      mockGet.mockResolvedValue(history)

      const result = await getConfigHistory(1)
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/1/config-history', { params: undefined })
      expect(result.items).toHaveLength(1)
    })

    it('支持分页参数', async () => {
      mockGet.mockResolvedValue({ items: [], total: 0 })

      await getConfigHistory(1, { page: 2, page_size: 5 })
      expect(mockGet).toHaveBeenCalledWith('/v1/gateways/1/config-history', {
        params: { page: 2, page_size: 5 },
      })
    })
  })
})
