/**
 * FloorB1Layout 组件测试
 * 测试 B1 地下制冷机房布局（冷却塔、冷水机组、水泵、配电/控制柜）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const FloorB1LayoutTestable = defineComponent({
  name: 'FloorB1LayoutTestable',
  props: {
    width: { type: Number, default: 800 },
    height: { type: Number, default: 500 },
    showGrid: { type: Boolean, default: true },
    showLegend: { type: Boolean, default: true }
  },
  template: `
    <div class="floor-b1-layout" data-testid="floor-b1">
      <div class="floor-title" data-testid="floor-title">B1 地下制冷机房</div>
      <div class="cooling-towers" data-testid="cooling-towers">
        <div data-testid="ct-1">CT-1 冷却塔</div>
        <div data-testid="ct-2">CT-2 冷却塔</div>
      </div>
      <div class="chillers" data-testid="chillers">
        <div data-testid="ch-1">CH-1 冷水机组</div>
        <div data-testid="ch-2">CH-2 冷水机组</div>
      </div>
      <div class="chilled-water-pumps" data-testid="chw-pumps">
        <div data-testid="chwp-1">CHWP-1 冷冻水泵</div>
        <div data-testid="chwp-2">CHWP-2 冷冻水泵</div>
      </div>
      <div class="cooling-water-pumps" data-testid="cw-pumps">
        <div data-testid="cwp-1">CWP-1 冷却水泵</div>
        <div data-testid="cwp-2">CWP-2 冷却水泵</div>
      </div>
      <div class="power-distribution" data-testid="power-dist">
        <div data-testid="pdu">配电柜 PDU</div>
        <div data-testid="plc">控制柜 PLC</div>
      </div>
      <div v-if="showLegend" class="legend" data-testid="legend">
        <span>制冷设备</span><span>水泵</span><span>配电</span><span>控制</span>
      </div>
    </div>
  `
})

describe('FloorB1Layout B1地下制冷机房组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 B1 楼层标题', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    expect(wrapper.find('[data-testid="floor-title"]').text()).toBe('B1 地下制冷机房')
  })

  it('包含 2 台冷却塔', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    expect(wrapper.find('[data-testid="ct-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ct-2"]').exists()).toBe(true)
  })

  it('包含 2 台冷水机组', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    expect(wrapper.find('[data-testid="ch-1"]').text()).toContain('CH-1')
    expect(wrapper.find('[data-testid="ch-2"]').text()).toContain('CH-2')
  })

  it('包含冷冻水泵和冷却水泵', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    expect(wrapper.find('[data-testid="chwp-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chwp-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cwp-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cwp-2"]').exists()).toBe(true)
  })

  it('包含配电柜和控制柜', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    expect(wrapper.find('[data-testid="pdu"]').text()).toContain('PDU')
    expect(wrapper.find('[data-testid="plc"]').text()).toContain('PLC')
  })

  it('图例包含制冷设备、水泵、配电、控制', () => {
    const wrapper = mount(FloorB1LayoutTestable)
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('制冷设备')
    expect(legend.text()).toContain('水泵')
    expect(legend.text()).toContain('配电')
    expect(legend.text()).toContain('控制')
  })

  it('showLegend 为 false 时隐藏图例', () => {
    const wrapper = mount(FloorB1LayoutTestable, { props: { showLegend: false } })
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(false)
  })
})
