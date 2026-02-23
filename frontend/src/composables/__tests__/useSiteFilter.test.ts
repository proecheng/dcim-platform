/**
 * useSiteFilter composable 纯逻辑函数单元测试
 *
 * 覆盖: getSiteParams 参数生成逻辑
 * 这些函数定义在 composable 内部，复制核心逻辑进行测试。
 */
import { describe, it, expect } from 'vitest'

// ============================================================
// 来源: useSiteFilter.ts — getSiteParams (line 13-18)
// ============================================================
function getSiteParams(currentSiteId: number | null): Record<string, number> {
  if (currentSiteId !== null) {
    return { site_id: currentSiteId }
  }
  return {}
}

// ============================================================
// 测试
// ============================================================

describe('useSiteFilter — getSiteParams 站点参数生成', () => {
  it('正常: 有站点 ID 时返回 { site_id }', () => {
    expect(getSiteParams(1)).toEqual({ site_id: 1 })
  })

  it('正常: 站点 ID 为 0 时也返回', () => {
    expect(getSiteParams(0)).toEqual({ site_id: 0 })
  })

  it('正常: 大数值站点 ID', () => {
    expect(getSiteParams(9999)).toEqual({ site_id: 9999 })
  })

  it('边界: null 时返回空对象', () => {
    expect(getSiteParams(null)).toEqual({})
  })

  it('边界: 返回的空对象没有 site_id 键', () => {
    const params = getSiteParams(null)
    expect('site_id' in params).toBe(false)
  })

  it('正常: 返回对象可直接用于 API 参数展开', () => {
    const baseParams = { page: 1, page_size: 20 }
    const siteParams = getSiteParams(5)
    const merged = { ...baseParams, ...siteParams }
    expect(merged).toEqual({ page: 1, page_size: 20, site_id: 5 })
  })

  it('正常: null 时展开不影响基础参数', () => {
    const baseParams = { page: 1, page_size: 20 }
    const siteParams = getSiteParams(null)
    const merged = { ...baseParams, ...siteParams }
    expect(merged).toEqual({ page: 1, page_size: 20 })
  })
})
