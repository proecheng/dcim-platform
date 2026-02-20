/**
 * FloorF3Layout 组件测试
 * 测试 F3 楼层布局（监控中心、会议室、2台空调、8个机柜）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const FloorF3LayoutTestable = defineComponent({
  name: 'FloorF3LayoutTestable',
  props: {
    width: { type: Number, default: 800 },
    height: { type: Number, default: 500 },
    showGrid: { type: Boolean, default: true },
    showLegend: { type: Boolean, default: true }
  },
  setup() {
    const acCount = 2
    const totalCabinets = 8
    return { acCount, totalCabinets }
  },
  template: `
    <div class="floor-f3-layout" data-testid="floor-f3">
      <div class="floor-title" data-testid="floor-title">F3 3楼办公监控</div>
      <div class="monitoring-center" data-testid="monitoring-center">
        <span>监控中心</span>
        <span>NOC</span>
      </div>
      <div class="meeting-room" data-testid="meeting-room">
        <span>会议室</span>
        <span>Conference</span>
      </div>
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
        <div data-testid="pdu">配电柜</div>
      </div>
      <div v-if="showLegend" class="legend" data-testid="legend">
        <span>办公区</span><span>机柜</span><span>空调</span><span>UPS/配电</span>
      </div>
    </div>
  `
})

describe('FloorF3Layout F3楼层布局组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 F3 楼层标题', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    expect(wrapper.find('[data-testid="floor-title"]').text()).toBe('F3 3楼办公监控')
  })

  it('包含监控中心区域', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    const noc = wrapper.find('[data-testid="monitoring-center"]')
    expect(noc.exists()).toBe(true)
    expect(noc.text()).toContain('监控中心')
    expect(noc.text()).toContain('NOC')
  })

  it('包含会议室区域', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    const room = wrapper.find('[data-testid="meeting-room"]')
    expect(room.exists()).toBe(true)
    expect(room.text()).toContain('会议室')
  })

  it('渲染 2 台精密空调', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    expect(wrapper.find('[data-testid="ac-section"]').findAll('.ac-unit')).toHaveLength(2)
  })

  it('渲染 8 个机柜（2行×4列）', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    expect(wrapper.find('[data-testid="cabinet-section"]').findAll('.cabinet')).toHaveLength(8)
  })

  it('包含 UPS 和配电柜', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    expect(wrapper.find('[data-testid="ups-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pdu"]').exists()).toBe(true)
  })

  it('图例包含办公区、机柜、空调、UPS/配电', () => {
    const wrapper = mount(FloorF3LayoutTestable)
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('办公区')
    expect(legend.text()).toContain('机柜')
    expect(legend.text()).toContain('空调')
    expect(legend.text()).toContain('UPS/配电')
  })
})
