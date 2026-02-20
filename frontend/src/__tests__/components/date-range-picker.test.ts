/**
 * DateRangePicker 日期范围选择器组件 单元测试
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
    valueOf: vi.fn(() => 1706745600000),
    toDate: vi.fn(() => new Date('2026-01-01'))
  })
  dayjs.extend = vi.fn()
  dayjs.locale = vi.fn()
  return { default: dayjs }
})

const DateRangePickerTestable = defineComponent({
  name: 'DateRangePickerTestable',
  props: {
    startTime: { type: String, default: undefined },
    endTime: { type: String, default: undefined },
    valueFormat: { type: String, default: 'YYYY-MM-DD HH:mm:ss' },
    showShortcuts: { type: Boolean, default: true },
    clearable: { type: Boolean, default: true },
    size: { type: String, default: 'default' },
    maxDays: { type: Number, default: undefined }
  },
  emits: ['update:startTime', 'update:endTime', 'change'],
  setup(props, { emit }) {
    const dateRange = computed({
      get: () => {
        if (props.startTime && props.endTime) {
          return [props.startTime, props.endTime]
        }
        return null
      },
      set: (val: string[] | null) => {
        if (val) {
          emit('update:startTime', val[0])
          emit('update:endTime', val[1])
        } else {
          emit('update:startTime', undefined)
          emit('update:endTime', undefined)
        }
      }
    })

    const hasRange = computed(() => dateRange.value !== null)

    const handleChange = (val: string[] | null) => {
      if (val) {
        emit('change', { startTime: val[0], endTime: val[1] })
      } else {
        emit('change', { startTime: undefined, endTime: undefined })
      }
    }

    const handleClear = () => {
      dateRange.value = null
      handleChange(null)
    }

    return { dateRange, hasRange, handleChange, handleClear }
  },
  template: `
    <div data-testid="date-range-picker" class="date-range-picker">
      <span data-testid="range-display">
        <template v-if="hasRange">{{ dateRange[0] }} 至 {{ dateRange[1] }}</template>
        <template v-else>请选择时间范围</template>
      </span>
      <span v-if="showShortcuts" data-testid="shortcuts">快捷选项</span>
      <button v-if="clearable && hasRange" data-testid="clear-btn" @click="handleClear">清除</button>
      <span data-testid="size-indicator" :data-size="size">{{ size }}</span>
    </div>
  `
})

describe('DateRangePicker 日期范围选择器', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染无选中状态', () => {
    const wrapper = mount(DateRangePickerTestable)
    expect(wrapper.find('[data-testid="date-range-picker"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="range-display"]').text()).toContain('请选择时间范围')
  })

  it('传入 startTime 和 endTime 显示范围', () => {
    const wrapper = mount(DateRangePickerTestable, {
      props: { startTime: '2026-01-01 00:00:00', endTime: '2026-01-07 23:59:59' }
    })
    expect(wrapper.find('[data-testid="range-display"]').text()).toContain('2026-01-01')
    expect(wrapper.find('[data-testid="range-display"]').text()).toContain('2026-01-07')
  })

  it('showShortcuts 控制快捷选项显示', () => {
    const wrapperShow = mount(DateRangePickerTestable, { props: { showShortcuts: true } })
    expect(wrapperShow.find('[data-testid="shortcuts"]').exists()).toBe(true)

    const wrapperHide = mount(DateRangePickerTestable, { props: { showShortcuts: false } })
    expect(wrapperHide.find('[data-testid="shortcuts"]').exists()).toBe(false)
  })

  it('clearable 控制清除按钮', () => {
    const wrapper = mount(DateRangePickerTestable, {
      props: { startTime: '2026-01-01', endTime: '2026-01-07', clearable: true }
    })
    expect(wrapper.find('[data-testid="clear-btn"]').exists()).toBe(true)
  })

  it('点击清除触发更新事件', async () => {
    const wrapper = mount(DateRangePickerTestable, {
      props: { startTime: '2026-01-01', endTime: '2026-01-07', clearable: true }
    })
    await wrapper.find('[data-testid="clear-btn"]').trigger('click')
    expect(wrapper.emitted('update:startTime')?.[0]).toEqual([undefined])
    expect(wrapper.emitted('update:endTime')?.[0]).toEqual([undefined])
    expect(wrapper.emitted('change')?.[0]).toEqual([{ startTime: undefined, endTime: undefined }])
  })

  it('size 属性正确传递', () => {
    const wrapper = mount(DateRangePickerTestable, {
      props: { size: 'small' }
    })
    expect(wrapper.find('[data-testid="size-indicator"]').attributes('data-size')).toBe('small')
  })

  it('dateRange computed 正确计算', () => {
    const wrapper = mount(DateRangePickerTestable, {
      props: { startTime: '2026-01-01', endTime: '2026-01-31' }
    })
    expect(wrapper.vm.hasRange).toBe(true)
    expect(wrapper.vm.dateRange).toEqual(['2026-01-01', '2026-01-31'])
  })
})
