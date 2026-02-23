/**
 * useEnergy composable 纯逻辑函数单元测试
 *
 * 覆盖: 格式化函数 (formatPower, formatEnergy, formatCost, formatPUE)
 *       PUE 等级判断、负载率状态判断
 */
import { describe, it, expect } from 'vitest'

// ============================================================
// 来源: useEnergy.ts — formatPower (line 280-286)
// ============================================================
function formatPower(power: number | undefined | null): string {
  if (power === undefined || power === null) return '-'
  if (power >= 1000) {
    return `${(power / 1000).toFixed(2)} MW`
  }
  return `${power.toFixed(2)} kW`
}

// ============================================================
// 来源: useEnergy.ts — formatEnergy (line 289-298)
// ============================================================
function formatEnergy(energy: number | undefined | null): string {
  if (energy === undefined || energy === null) return '-'
  if (energy >= 1000000) {
    return `${(energy / 1000000).toFixed(2)} GWh`
  }
  if (energy >= 1000) {
    return `${(energy / 1000).toFixed(2)} MWh`
  }
  return `${energy.toFixed(2)} kWh`
}

// ============================================================
// 来源: useEnergy.ts — formatCost (line 301-307)
// ============================================================
function formatCost(cost: number | undefined | null): string {
  if (cost === undefined || cost === null) return '-'
  if (cost >= 10000) {
    return `${(cost / 10000).toFixed(2)} 万元`
  }
  return `${cost.toFixed(2)} 元`
}

// ============================================================
// 来源: useEnergy.ts — formatPUE (line 310-313)
// ============================================================
function formatPUE(pue: number | undefined | null): string {
  if (pue === undefined || pue === null) return '-'
  return pue.toFixed(3)
}

// ============================================================
// 来源: useEnergy.ts — getPUELevel (line 316-321)
// ============================================================
function getPUELevel(pue: number): { level: string; color: string } {
  if (pue <= 1.4) return { level: '优秀', color: '#67C23A' }
  if (pue <= 1.6) return { level: '良好', color: '#409EFF' }
  if (pue <= 1.8) return { level: '一般', color: '#E6A23C' }
  return { level: '较差', color: '#F56C6C' }
}

// ============================================================
// 来源: useEnergy.ts — getLoadRateStatus (line 324-329)
// ============================================================
function getLoadRateStatus(rate: number): { status: string; color: string } {
  if (rate < 30) return { status: '低负载', color: '#909399' }
  if (rate < 60) return { status: '正常', color: '#67C23A' }
  if (rate < 80) return { status: '较高', color: '#E6A23C' }
  return { status: '高负载', color: '#F56C6C' }
}

// ============================================================
// 测试
// ============================================================

describe('useEnergy — formatPower 功率格式化', () => {
  it('正常: kW 范围', () => {
    expect(formatPower(500)).toBe('500.00 kW')
  })

  it('正常: MW 范围', () => {
    expect(formatPower(1500)).toBe('1.50 MW')
  })

  it('边界: 恰好 1000 kW → MW', () => {
    expect(formatPower(1000)).toBe('1.00 MW')
  })

  it('边界: 0 kW', () => {
    expect(formatPower(0)).toBe('0.00 kW')
  })

  it('异常: null 返回 -', () => {
    expect(formatPower(null)).toBe('-')
  })

  it('异常: undefined 返回 -', () => {
    expect(formatPower(undefined)).toBe('-')
  })
})

describe('useEnergy — formatEnergy 电量格式化', () => {
  it('正常: kWh 范围', () => {
    expect(formatEnergy(500)).toBe('500.00 kWh')
  })

  it('正常: MWh 范围', () => {
    expect(formatEnergy(5000)).toBe('5.00 MWh')
  })

  it('正常: GWh 范围', () => {
    expect(formatEnergy(2000000)).toBe('2.00 GWh')
  })

  it('边界: 恰好 1000 → MWh', () => {
    expect(formatEnergy(1000)).toBe('1.00 MWh')
  })

  it('边界: 恰好 1000000 → GWh', () => {
    expect(formatEnergy(1000000)).toBe('1.00 GWh')
  })

  it('异常: null 返回 -', () => {
    expect(formatEnergy(null)).toBe('-')
  })
})

describe('useEnergy — formatCost 电费格式化', () => {
  it('正常: 元范围', () => {
    expect(formatCost(5000)).toBe('5000.00 元')
  })

  it('正常: 万元范围', () => {
    expect(formatCost(50000)).toBe('5.00 万元')
  })

  it('边界: 恰好 10000 → 万元', () => {
    expect(formatCost(10000)).toBe('1.00 万元')
  })

  it('边界: 0 元', () => {
    expect(formatCost(0)).toBe('0.00 元')
  })

  it('异常: null 返回 -', () => {
    expect(formatCost(null)).toBe('-')
  })
})

describe('useEnergy — formatPUE', () => {
  it('正常: 3 位小数', () => {
    expect(formatPUE(1.456)).toBe('1.456')
  })

  it('正常: 整数补零', () => {
    expect(formatPUE(2)).toBe('2.000')
  })

  it('异常: null 返回 -', () => {
    expect(formatPUE(null)).toBe('-')
  })

  it('异常: undefined 返回 -', () => {
    expect(formatPUE(undefined)).toBe('-')
  })
})

describe('useEnergy — getPUELevel PUE 等级', () => {
  it('优秀: PUE <= 1.4', () => {
    expect(getPUELevel(1.2)).toEqual({ level: '优秀', color: '#67C23A' })
    expect(getPUELevel(1.4)).toEqual({ level: '优秀', color: '#67C23A' })
  })

  it('良好: 1.4 < PUE <= 1.6', () => {
    expect(getPUELevel(1.5)).toEqual({ level: '良好', color: '#409EFF' })
    expect(getPUELevel(1.6)).toEqual({ level: '良好', color: '#409EFF' })
  })

  it('一般: 1.6 < PUE <= 1.8', () => {
    expect(getPUELevel(1.7)).toEqual({ level: '一般', color: '#E6A23C' })
    expect(getPUELevel(1.8)).toEqual({ level: '一般', color: '#E6A23C' })
  })

  it('较差: PUE > 1.8', () => {
    expect(getPUELevel(2.0)).toEqual({ level: '较差', color: '#F56C6C' })
    expect(getPUELevel(3.0)).toEqual({ level: '较差', color: '#F56C6C' })
  })
})

describe('useEnergy — getLoadRateStatus 负载率状态', () => {
  it('低负载: rate < 30', () => {
    expect(getLoadRateStatus(10)).toEqual({ status: '低负载', color: '#909399' })
    expect(getLoadRateStatus(29)).toEqual({ status: '低负载', color: '#909399' })
  })

  it('正常: 30 <= rate < 60', () => {
    expect(getLoadRateStatus(30)).toEqual({ status: '正常', color: '#67C23A' })
    expect(getLoadRateStatus(59)).toEqual({ status: '正常', color: '#67C23A' })
  })

  it('较高: 60 <= rate < 80', () => {
    expect(getLoadRateStatus(60)).toEqual({ status: '较高', color: '#E6A23C' })
    expect(getLoadRateStatus(79)).toEqual({ status: '较高', color: '#E6A23C' })
  })

  it('高负载: rate >= 80', () => {
    expect(getLoadRateStatus(80)).toEqual({ status: '高负载', color: '#F56C6C' })
    expect(getLoadRateStatus(100)).toEqual({ status: '高负载', color: '#F56C6C' })
  })
})
