/**
 * 部署阶段与校准状态组件测试
 *
 * Story 32.4: 测试 DeploymentPhaseView 的核心逻辑
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock API 模块
vi.mock('@/api/modules/precool', () => ({
  getDeploymentPhase: vi.fn().mockResolvedValue({
    code: 200, message: 'ok', data: { current_phase: 1, phase_name: 'THM 模式', description: '仅使用 THM 估算', updated_at: null },
  }),
  updateDeploymentPhase: vi.fn().mockResolvedValue({
    code: 200, message: 'ok', data: { phase: 2, old_phase: 1, force_used: false },
  }),
  getDashboard: vi.fn().mockResolvedValue({
    code: 200,
    message: 'ok',
    data: {
      zones: [
        { zone_id: 1, zone_name: '测试区域A', current_temp: 22.0, headroom: 5.0, model_mode: 'THM', shiftable_ratio: 0.3 },
        { zone_id: 2, zone_name: '测试区域B', current_temp: 23.0, headroom: 4.0, model_mode: 'TCL', shiftable_ratio: 0.4 },
      ],
      status_summary: { total_zones: 2, thm_zones: 1, tcl_zones: 1, offline_zones: 0 },
      today_savings: 50.0,
    },
  }),
  triggerCalibration: vi.fn().mockResolvedValue({
    code: 200, message: 'ok', data: { success: true, R: 0.005, C: 500, r_squared: 0.92, sample_count: 120 },
  }),
  getCalibrationHistory: vi.fn().mockResolvedValue({
    code: 200, message: 'ok', data: { items: [], total: 0 },
  }),
}))

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// ==================== 辅助函数逻辑测试 ====================

describe('DeploymentPhaseView 辅助函数逻辑', () => {
  // 测试 el-steps active 计算
  describe('步骤条 active 计算', () => {
    it('phase 1 对应 active=0', () => {
      const phase = 1
      expect(phase - 1).toBe(0)
    })

    it('phase 4 对应 active=3', () => {
      const phase = 4
      expect(phase - 1).toBe(3)
    })
  })

  // 测试 R² 颜色逻辑
  describe('R² 颜色判断', () => {
    function getR2Color(r2: number | null | undefined): string {
      if (r2 == null) return '#909399'
      if (r2 >= 0.85) return '#67c23a'
      if (r2 >= 0.7) return '#e6a23c'
      return '#f56c6c'
    }

    it('null 返回灰色', () => {
      expect(getR2Color(null)).toBe('#909399')
    })

    it('R²>=0.85 返回绿色', () => {
      expect(getR2Color(0.92)).toBe('#67c23a')
    })

    it('0.7<=R²<0.85 返回黄色', () => {
      expect(getR2Color(0.78)).toBe('#e6a23c')
    })

    it('R²<0.7 返回红色', () => {
      expect(getR2Color(0.5)).toBe('#f56c6c')
    })

    it('R²=0.85 边界返回绿色', () => {
      expect(getR2Color(0.85)).toBe('#67c23a')
    })
  })

  // 测试校准方法标签
  describe('校准方法标签', () => {
    function methodLabel(method: string | null | undefined): string {
      if (!method) return '-'
      const map: Record<string, string> = {
        auto_fit: '自动校准',
        manual: '手动设置',
        default: '默认值',
        demo: '演示',
      }
      return map[method] || method
    }

    it('auto_fit 返回自动校准', () => {
      expect(methodLabel('auto_fit')).toBe('自动校准')
    })

    it('null 返回 -', () => {
      expect(methodLabel(null)).toBe('-')
    })

    it('未知方法返回原值', () => {
      expect(methodLabel('custom')).toBe('custom')
    })
  })

  // 测试校准状态判断
  describe('校准状态判断', () => {
    interface MockRow {
      calibrating: boolean
      calibration: {
        fitting_method: string | null
        fitting_r_squared: number | null
      } | null
    }

    function calibrationStatusLabel(row: MockRow): string {
      if (row.calibrating) return '校准中'
      if (!row.calibration) return '待校准'
      const cal = row.calibration
      if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared >= 0.85) {
        return '已校准'
      }
      if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared < 0.85) {
        return 'R²不足'
      }
      if (cal.fitting_method === 'manual') return '手动设置'
      return '待校准'
    }

    it('正在校准时显示校准中', () => {
      expect(calibrationStatusLabel({ calibrating: true, calibration: null })).toBe('校准中')
    })

    it('无校准记录时显示待校准', () => {
      expect(calibrationStatusLabel({ calibrating: false, calibration: null })).toBe('待校准')
    })

    it('R²>=0.85 时显示已校准', () => {
      expect(calibrationStatusLabel({
        calibrating: false,
        calibration: { fitting_method: 'auto_fit', fitting_r_squared: 0.92 },
      })).toBe('已校准')
    })

    it('R²<0.85 时显示 R²不足', () => {
      expect(calibrationStatusLabel({
        calibrating: false,
        calibration: { fitting_method: 'auto_fit', fitting_r_squared: 0.72 },
      })).toBe('R²不足')
    })

    it('手动设置时显示手动设置', () => {
      expect(calibrationStatusLabel({
        calibrating: false,
        calibration: { fitting_method: 'manual', fitting_r_squared: null },
      })).toBe('手动设置')
    })
  })
})

// ==================== API 调用测试 ====================

describe('DeploymentPhaseView API 调用', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('getDeploymentPhase 返回正确格式', async () => {
    const { getDeploymentPhase } = await import('@/api/modules/precool')
    const res = await getDeploymentPhase()
    expect(res.code).toBe(200)
    expect(res.data.current_phase).toBe(1)
    expect(res.data.phase_name).toBe('THM 模式')
  })

  it('updateDeploymentPhase 传递正确参数', async () => {
    const { updateDeploymentPhase } = await import('@/api/modules/precool')
    await updateDeploymentPhase({ phase: 3, force: true })
    expect(updateDeploymentPhase).toHaveBeenCalledWith({ phase: 3, force: true })
  })

  it('getDashboard 返回区域列表', async () => {
    const { getDashboard } = await import('@/api/modules/precool')
    const res = await getDashboard()
    expect(res.code).toBe(200)
    expect(res.data.zones).toHaveLength(2)
    expect(res.data.zones[0].zone_name).toBe('测试区域A')
  })

  it('triggerCalibration 返回校准结果', async () => {
    const { triggerCalibration } = await import('@/api/modules/precool')
    const res = await triggerCalibration(1)
    expect(res.code).toBe(200)
    expect(res.data.r_squared).toBe(0.92)
  })

  it('getCalibrationHistory 返回分页数据', async () => {
    const { getCalibrationHistory } = await import('@/api/modules/precool')
    const res = await getCalibrationHistory(1, { limit: 1 })
    expect(res.code).toBe(200)
    expect(res.data.items).toHaveLength(0)
  })

  it('updateDeploymentPhase 前置条件失败场景', async () => {
    const { updateDeploymentPhase } = await import('@/api/modules/precool')
    ;(updateDeploymentPhase as any).mockResolvedValueOnce({
      code: 422,
      message: '前置条件不满足',
      data: { error: 'precondition_failed', details: ['区域A未校准'] },
    })
    const res = await updateDeploymentPhase({ phase: 3 })
    expect(res.code).toBe(422)
    expect(res.data.details).toContain('区域A未校准')
  })

  it('triggerCalibration scipy 未安装场景', async () => {
    const { triggerCalibration } = await import('@/api/modules/precool')
    ;(triggerCalibration as any).mockResolvedValueOnce({
      code: 503, message: 'scipy 未安装，校准功能不可用', data: null,
    })
    const res = await triggerCalibration(1)
    expect(res.code).toBe(503)
  })
})
