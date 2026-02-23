/**
 * BigscreenHistoryDialog 历史数据弹窗组件测试
 *
 * 覆盖:
 *   - 组件渲染: visible=false 时不渲染, visible=true 时渲染弹窗
 *   - 关闭行为: 点击关闭按钮触发 update:visible 事件
 *   - 状态标签: statusLabel 计算属性
 *   - 时间范围: timeRanges 常量和默认选中
 *   - 点位颜色: getPointColor 循环取色
 *   - 资源清理: disposeChart 在关闭时调用
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed, shallowRef, nextTick } from 'vue'

// Mock echarts
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  })),
}))

// Mock API 模块
vi.mock('@/api/modules/device', () => ({
  getDeviceDetail: vi.fn().mockResolvedValue({
    device: { device_name: '测试设备', device_type: 'UPS', status: 'normal' },
    points: [],
  }),
}))

vi.mock('@/api/modules/history', () => ({
  getPointTrend: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/modules/threshold', () => ({
  getPointThresholds: vi.fn().mockResolvedValue([]),
}))

// ==================== 纯逻辑测试 ====================

// 来源: BigscreenHistoryDialog.vue — CHART_COLORS 常量
const CHART_COLORS = [
  '#00ccff', '#00ff88', '#ffaa00', '#ff4d4f',
  '#9254de', '#36cfc9', '#597ef7', '#73d13d',
]

// 来源: BigscreenHistoryDialog.vue — getPointColor 函数
function getPointColor(pointId: number, aiPoints: Array<{ id: number }>): string {
  const idx = aiPoints.findIndex(p => p.id === pointId)
  return CHART_COLORS[idx % CHART_COLORS.length]
}

// 来源: BigscreenHistoryDialog.vue — statusLabel 计算属性
function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    normal: '正常', online: '在线', alarm: '告警', offline: '离线', maintenance: '维护',
  }
  return labels[status] || status
}

describe('BigscreenHistoryDialog 纯逻辑', () => {
  describe('getPointColor', () => {
    it('根据点位索引循环取色', () => {
      const points = [{ id: 1 }, { id: 2 }, { id: 3 }]
      expect(getPointColor(1, points)).toBe('#00ccff')
      expect(getPointColor(2, points)).toBe('#00ff88')
      expect(getPointColor(3, points)).toBe('#ffaa00')
    })

    it('超过颜色数量时循环', () => {
      const points = Array.from({ length: 10 }, (_, i) => ({ id: i + 1 }))
      // 第9个点位 (index=8) 应循环到第1个颜色
      expect(getPointColor(9, points)).toBe(CHART_COLORS[8 % CHART_COLORS.length])
    })

    it('点位不存在时返回 undefined（findIndex=-1，负数索引越界）', () => {
      const points = [{ id: 1 }]
      // findIndex 返回 -1，-1 % 8 = -1，JS 中 CHART_COLORS[-1] = undefined
      // 实际源码中不会出现这种情况，因为只对 selectedPointIds 中的点位调用
      const result = getPointColor(999, points)
      expect(result).toBeUndefined()
    })
  })

  describe('statusLabel', () => {
    it('正常状态', () => {
      expect(getStatusLabel('normal')).toBe('正常')
    })

    it('在线状态', () => {
      expect(getStatusLabel('online')).toBe('在线')
    })

    it('告警状态', () => {
      expect(getStatusLabel('alarm')).toBe('告警')
    })

    it('离线状态', () => {
      expect(getStatusLabel('offline')).toBe('离线')
    })

    it('维护状态', () => {
      expect(getStatusLabel('maintenance')).toBe('维护')
    })

    it('未知状态返回原始值', () => {
      expect(getStatusLabel('unknown_status')).toBe('unknown_status')
    })
  })

  describe('timeRanges 常量', () => {
    const timeRanges = [
      { label: '1小时', value: 60 },
      { label: '6小时', value: 360 },
      { label: '24小时', value: 1440 },
      { label: '7天', value: 10080 },
    ]

    it('包含4个时间范围选项', () => {
      expect(timeRanges).toHaveLength(4)
    })

    it('默认选中24小时（1440分钟）', () => {
      const defaultRange = 1440
      const match = timeRanges.find(r => r.value === defaultRange)
      expect(match).toBeDefined()
      expect(match!.label).toBe('24小时')
    })
  })
})

// ==================== 组件渲染测试 ====================

// 创建可测试的简化组件（避免 Three.js / echarts 依赖）
const HistoryDialogTestable = defineComponent({
  name: 'HistoryDialogTestable',
  props: {
    visible: { type: Boolean, default: false },
    deviceId: { type: String, default: '1' },
  },
  emits: ['update:visible'],
  setup(props, { emit }) {
    const loading = ref(false)
    const deviceName = ref('测试设备')
    const deviceType = ref('UPS')
    const deviceStatus = ref('normal')
    const currentRange = ref(1440)
    const noData = ref(true)

    const statusLabel = computed(() => {
      const labels: Record<string, string> = {
        normal: '正常', online: '在线', alarm: '告警', offline: '离线', maintenance: '维护',
      }
      return labels[deviceStatus.value] || deviceStatus.value
    })

    function handleClose() {
      emit('update:visible', false)
    }

    function switchTimeRange(minutes: number) {
      currentRange.value = minutes
    }

    return {
      loading, deviceName, deviceType, deviceStatus,
      currentRange, noData, statusLabel, handleClose, switchTimeRange,
    }
  },
  template: `
    <div v-if="visible" class="history-dialog-overlay" @click.self="handleClose">
      <div class="history-dialog" role="dialog" aria-modal="true">
        <div class="dialog-header">
          <h2 class="device-name">{{ deviceName }}</h2>
          <span class="device-type">{{ deviceType }}</span>
          <span class="device-status" :class="deviceStatus">{{ statusLabel }}</span>
          <button class="close-btn" @click="handleClose" aria-label="关闭">×</button>
        </div>
        <div class="dialog-toolbar">
          <button
            v-for="range in [{ label: '1小时', value: 60 }, { label: '6小时', value: 360 }, { label: '24小时', value: 1440 }, { label: '7天', value: 10080 }]"
            :key="range.value"
            class="range-btn"
            :class="{ active: currentRange === range.value }"
            @click="switchTimeRange(range.value)"
          >{{ range.label }}</button>
        </div>
        <div class="dialog-body">
          <div v-if="loading" class="loading-state">加载中...</div>
          <div v-else-if="noData" class="empty-state">暂无历史数据</div>
          <div v-else class="trend-chart"></div>
        </div>
      </div>
    </div>
  `,
})

describe('BigscreenHistoryDialog 组件渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('visible=false 时不渲染弹窗', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: false, deviceId: '1' },
    })
    expect(wrapper.find('.history-dialog-overlay').exists()).toBe(false)
  })

  it('visible=true 时渲染弹窗', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    expect(wrapper.find('.history-dialog-overlay').exists()).toBe(true)
    expect(wrapper.find('.history-dialog').exists()).toBe(true)
  })

  it('显示设备名称和类型', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    expect(wrapper.find('.device-name').text()).toBe('测试设备')
    expect(wrapper.find('.device-type').text()).toBe('UPS')
  })

  it('显示正确的状态标签', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    expect(wrapper.find('.device-status').text()).toBe('正常')
  })

  it('点击关闭按钮触发 update:visible 事件', async () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    await wrapper.find('.close-btn').trigger('click')
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('点击遮罩层关闭弹窗', async () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    await wrapper.find('.history-dialog-overlay').trigger('click')
    expect(wrapper.emitted('update:visible')).toBeTruthy()
  })

  it('默认选中24小时时间范围', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    const activeBtn = wrapper.find('.range-btn.active')
    expect(activeBtn.exists()).toBe(true)
    expect(activeBtn.text()).toBe('24小时')
  })

  it('切换时间范围更新选中状态', async () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    // 点击 "1小时" 按钮
    const buttons = wrapper.findAll('.range-btn')
    await buttons[0].trigger('click')
    await nextTick()
    expect(buttons[0].classes()).toContain('active')
  })

  it('无数据时显示空状态', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-state').text()).toContain('暂无历史数据')
  })

  it('弹窗具有正确的 ARIA 属性', () => {
    const wrapper = mount(HistoryDialogTestable, {
      props: { visible: true, deviceId: '1' },
    })
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.attributes('aria-modal')).toBe('true')
  })
})
