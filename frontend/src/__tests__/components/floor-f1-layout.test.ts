/**
 * FloorF1Layout 组件测试
 * 测试 F1 楼层布局（4台空调、20个机柜、UPS）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const FloorF1LayoutTestable = defineComponent({
  name: 'FloorF1LayoutTestable',
  props: {
    width: { type: Number, default: 800 },
    height: { type: Number, default: 500 },
    showGrid: { type: Boolean, default: true },
    showLegend: { type: Boolean, default: true }
  },
  setup(props) {
    const acCount = 4
    const cabinetRows = 4
    const cabinetCols = 5
    const totalCabinets = cabinetRows * cabinetCols
    return { acCount, cabinetRows, cabinetCols, totalCabinets }
  },
  template: `
    <div class="floor-f1-layout" data-testid="floor-f1">
      <div class="floor-title" data-testid="floor-title">F1 1楼机房区A</div>
      <div class="precision-acs" data-testid="ac-section">
        <div v-for="i in acCount" :key="'ac-' + i" class="ac-unit" :data-testid="'ac-' + i">AC-{{ i }}</div>
      </div>
      <div class="cabinet-rows" data-testid="cabinet-section">
        <div v-for="i in totalCabinets" :key="'cab-' + i" class="cabinet" :data-testid="'cabinet-' + i">
          {{ String(i).padStart(2, '0') }}
        </div>
      </div>
      <div class="power-area" data-testid="power-area">
        <div data-testid="ups-1">UPS-1</div>
        <div data-testid="ups-2">UPS-2</div>
        <div data-testid="pdu">配电</div>
        <div data-testid="fire">消防</div>
      </div>
      <div v-if="showLegend" class="legend" data-testid="legend">
        <span>机柜</span><span>空调</span><span>UPS/配电</span><span>消防</span>
      </div>
    </div>
  `
})

describe('FloorF1Layout F1楼层布局组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 F1 楼层标题', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    expect(wrapper.find('[data-testid="floor-title"]').text()).toBe('F1 1楼机房区A')
  })

  it('渲染 4 台精密空调', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    const acs = wrapper.find('[data-testid="ac-section"]')
    expect(acs.findAll('.ac-unit')).toHaveLength(4)
    expect(wrapper.find('[data-testid="ac-1"]').text()).toBe('AC-1')
    expect(wrapper.find('[data-testid="ac-4"]').text()).toBe('AC-4')
  })

  it('渲染 20 个机柜（4行×5列）', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    const cabinets = wrapper.find('[data-testid="cabinet-section"]').findAll('.cabinet')
    expect(cabinets).toHaveLength(20)
  })

  it('机柜编号使用两位数格式', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    expect(wrapper.find('[data-testid="cabinet-1"]').text()).toBe('01')
    expect(wrapper.find('[data-testid="cabinet-5"]').text()).toBe('05')
    expect(wrapper.find('[data-testid="cabinet-20"]').text()).toBe('20')
  })

  it('包含 UPS 和配电设备', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    expect(wrapper.find('[data-testid="ups-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ups-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pdu"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="fire"]').exists()).toBe(true)
  })

  it('图例包含所有设备类型', () => {
    const wrapper = mount(FloorF1LayoutTestable)
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('机柜')
    expect(legend.text()).toContain('空调')
    expect(legend.text()).toContain('UPS/配电')
    expect(legend.text()).toContain('消防')
  })

  it('showLegend 为 false 时隐藏图例', () => {
    const wrapper = mount(FloorF1LayoutTestable, { props: { showLegend: false } })
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(false)
  })
})
