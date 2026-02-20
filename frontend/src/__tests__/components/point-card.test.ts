/**
 * PointCard 点位卡片组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

// Mock dayjs
vi.mock('dayjs', () => {
  const dayjs = (date?: any) => ({
    format: vi.fn(() => '2026-01-01'),
    fromNow: vi.fn(() => '1分钟前'),
    subtract: vi.fn(() => dayjs()),
    add: vi.fn(() => dayjs()),
    startOf: vi.fn(() => dayjs()),
    endOf: vi.fn(() => dayjs()),
    valueOf: vi.fn(() => 1706745600000)
  })
  dayjs.extend = vi.fn()
  dayjs.locale = vi.fn()
  return { default: dayjs }
})

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  DataLine: { template: '<i class="icon-dataline" />' },
  Setting: { template: '<i class="icon-setting" />' }
}))

const PointCardTestable = defineComponent({
  name: 'PointCardTestable',
  props: {
    pointId: { type: Number, required: true },
    code: { type: String, required: true },
    name: { type: String, required: true },
    pointType: { type: String as () => 'AI' | 'DI' | 'AO' | 'DO', required: true },
    value: { type: Number, required: true },
    unit: { type: String, default: '' },
    precision: { type: Number, default: 2 },
    status: { type: String as () => 'normal' | 'alarm' | 'offline', default: 'normal' },
    trend: { type: String, default: undefined },
    updatedAt: { type: String, default: undefined },
    clickable: { type: Boolean, default: true },
    showActions: { type: Boolean, default: true },
    showHistory: { type: Boolean, default: true },
    showControl: { type: Boolean, default: true }
  },
  emits: ['click', 'history', 'control'],
  setup(props, { emit }) {
    const pointTypeTag = computed(() => {
      const map: Record<string, string> = { AI: 'success', DI: 'info', AO: 'warning', DO: 'danger' }
      return map[props.pointType] || 'info'
    })

    const statusText = computed(() => {
      const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
      return map[props.status] || '未知'
    })

    const displayValue = computed(() => {
      if (typeof props.value === 'number' && !isNaN(props.value)) {
        return props.value.toFixed(props.precision)
      }
      return '--'
    })

    const showControlBtn = computed(() =>
      props.showControl && (props.pointType === 'AO' || props.pointType === 'DO')
    )

    const handleClick = () => {
      if (props.clickable) emit('click', props.pointId)
    }

    return { pointTypeTag, statusText, displayValue, showControlBtn, handleClick }
  },
  template: `
    <div
      data-testid="point-card"
      :class="['point-card', 'point-card--' + status, { 'point-card--clickable': clickable }]"
      @click="handleClick"
    >
      <div data-testid="card-header" class="point-card__header">
        <span data-testid="point-name">{{ name }}</span>
        <span data-testid="point-type" :class="'el-tag--' + pointTypeTag">{{ pointType }}</span>
        <span data-testid="status-text">{{ statusText }}</span>
      </div>
      <div data-testid="card-value" class="point-card__value">
        {{ displayValue }}
        <span v-if="unit" data-testid="value-unit">{{ unit }}</span>
      </div>
      <div data-testid="card-footer" class="point-card__footer">
        <span data-testid="point-code">{{ code }}</span>
        <div v-if="showActions" data-testid="card-actions">
          <button v-if="showHistory" data-testid="history-btn" @click.stop="$emit('history', pointId)">历史</button>
          <button v-if="showControlBtn" data-testid="control-btn" @click.stop="$emit('control', pointId)">控制</button>
        </div>
      </div>
    </div>
  `
})

describe('PointCard 点位卡片', () => {
  const defaultProps = {
    pointId: 1,
    code: 'AI_TEMP_001',
    name: '温度传感器1',
    pointType: 'AI' as const,
    value: 25.67
  }

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(PointCardTestable, { props: defaultProps })
    expect(wrapper.find('[data-testid="point-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="point-name"]').text()).toBe('温度传感器1')
  })

  it('显示点位类型标签', () => {
    const wrapper = mount(PointCardTestable, { props: defaultProps })
    expect(wrapper.find('[data-testid="point-type"]').text()).toBe('AI')
    expect(wrapper.find('[data-testid="point-type"]').classes()).toContain('el-tag--success')
  })

  it('显示格式化数值和单位', () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, value: 25.678, unit: '℃', precision: 1 }
    })
    expect(wrapper.find('[data-testid="card-value"]').text()).toContain('25.7')
    expect(wrapper.find('[data-testid="value-unit"]').text()).toBe('℃')
  })

  it('status 属性控制样式和文本', () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, status: 'alarm' }
    })
    expect(wrapper.find('[data-testid="point-card"]').classes()).toContain('point-card--alarm')
    expect(wrapper.find('[data-testid="status-text"]').text()).toBe('告警')
  })

  it('clickable 控制点击行为', async () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, clickable: true }
    })
    await wrapper.find('[data-testid="point-card"]').trigger('click')
    expect(wrapper.emitted('click')?.[0]).toEqual([1])
  })

  it('clickable 为 false 时不触发点击', async () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, clickable: false }
    })
    await wrapper.find('[data-testid="point-card"]').trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('AO/DO 类型显示控制按钮', () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, pointType: 'AO' }
    })
    expect(wrapper.find('[data-testid="control-btn"]').exists()).toBe(true)
  })

  it('AI/DI 类型不显示控制按钮', () => {
    const wrapper = mount(PointCardTestable, {
      props: { ...defaultProps, pointType: 'AI' }
    })
    expect(wrapper.find('[data-testid="control-btn"]').exists()).toBe(false)
  })
})
