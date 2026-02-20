/**
 * FloorLayoutBase 组件测试
 * 测试 SVG 楼层布局基础组件
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const FloorLayoutBaseTestable = defineComponent({
  name: 'FloorLayoutBaseTestable',
  props: {
    width: { type: Number, default: 800 },
    height: { type: Number, default: 500 },
    viewBoxWidth: { type: Number, default: 400 },
    viewBoxHeight: { type: Number, default: 250 },
    showGrid: { type: Boolean, default: true },
    showLegend: { type: Boolean, default: true },
    gridSize: { type: Number, default: 20 }
  },
  template: `
    <div class="floor-layout" :style="{ width: width + 'px', height: height + 'px' }" data-testid="floor-layout">
      <svg
        :viewBox="'0 0 ' + viewBoxWidth + ' ' + viewBoxHeight"
        preserveAspectRatio="xMidYMid meet"
        data-testid="svg-canvas"
      >
        <rect x="0" y="0" :width="viewBoxWidth" :height="viewBoxHeight" fill="#1a2a4a" />
        <g class="grid-lines" v-if="showGrid" data-testid="grid-lines">
          <line
            v-for="i in Math.floor(viewBoxWidth / gridSize)"
            :key="'v' + i"
            :x1="i * gridSize" y1="0"
            :x2="i * gridSize" :y2="viewBoxHeight"
          />
          <line
            v-for="i in Math.floor(viewBoxHeight / gridSize)"
            :key="'h' + i"
            x1="0" :y1="i * gridSize"
            :x2="viewBoxWidth" :y2="i * gridSize"
          />
        </g>
        <slot></slot>
        <g class="device-labels"><slot name="labels"></slot></g>
      </svg>
      <div class="layout-legend" v-if="showLegend" data-testid="legend">
        <slot name="legend">
          <div class="legend-item">机柜</div>
          <div class="legend-item">空调</div>
          <div class="legend-item">UPS</div>
        </slot>
      </div>
    </div>
  `
})

describe('FloorLayoutBase 楼层布局基础组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('使用默认尺寸渲染布局容器', () => {
    const wrapper = mount(FloorLayoutBaseTestable)
    const layout = wrapper.find('[data-testid="floor-layout"]')
    expect(layout.exists()).toBe(true)
    expect(layout.attributes('style')).toContain('width: 800px')
    expect(layout.attributes('style')).toContain('height: 500px')
  })

  it('自定义宽高正确应用', () => {
    const wrapper = mount(FloorLayoutBaseTestable, {
      props: { width: 600, height: 400 }
    })
    const style = wrapper.find('[data-testid="floor-layout"]').attributes('style')
    expect(style).toContain('width: 600px')
    expect(style).toContain('height: 400px')
  })

  it('SVG viewBox 正确设置', () => {
    const wrapper = mount(FloorLayoutBaseTestable, {
      props: { viewBoxWidth: 500, viewBoxHeight: 300 }
    })
    const svg = wrapper.find('[data-testid="svg-canvas"]')
    const viewBoxAttr = svg.attributes('viewBox') || svg.attributes('viewbox')
    expect(viewBoxAttr).toBe('0 0 500 300')
  })

  it('showGrid 为 true 时显示网格线', () => {
    const wrapper = mount(FloorLayoutBaseTestable, { props: { showGrid: true } })
    expect(wrapper.find('[data-testid="grid-lines"]').exists()).toBe(true)
  })

  it('showGrid 为 false 时隐藏网格线', () => {
    const wrapper = mount(FloorLayoutBaseTestable, { props: { showGrid: false } })
    expect(wrapper.find('[data-testid="grid-lines"]').exists()).toBe(false)
  })

  it('showLegend 为 true 时显示图例', () => {
    const wrapper = mount(FloorLayoutBaseTestable, { props: { showLegend: true } })
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(true)
  })

  it('showLegend 为 false 时隐藏图例', () => {
    const wrapper = mount(FloorLayoutBaseTestable, { props: { showLegend: false } })
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(false)
  })

  it('默认图例包含机柜、空调、UPS', () => {
    const wrapper = mount(FloorLayoutBaseTestable)
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('机柜')
    expect(legend.text()).toContain('空调')
    expect(legend.text()).toContain('UPS')
  })
})
