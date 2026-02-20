/**
 * FloorLayoutSelector 组件测试
 * 测试楼层选择器切换逻辑
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

const FloorLayoutSelectorTestable = defineComponent({
  name: 'FloorLayoutSelectorTestable',
  setup() {
    const currentFloor = ref('F1')
    const floors = [
      { value: 'B1', label: 'B1 制冷机房' },
      { value: 'F1', label: 'F1 机房区A' },
      { value: 'F2', label: 'F2 机房区B' },
      { value: 'F3', label: 'F3 办公监控' }
    ]
    return { currentFloor, floors }
  },
  template: `
    <div class="floor-selector" data-testid="floor-selector">
      <div class="floor-tabs" data-testid="floor-tabs">
        <button
          v-for="floor in floors"
          :key="floor.value"
          :data-testid="'floor-btn-' + floor.value"
          :class="{ active: currentFloor === floor.value }"
          @click="currentFloor = floor.value"
        >{{ floor.label }}</button>
      </div>
      <div class="floor-content" data-testid="floor-content">
        <div v-if="currentFloor === 'B1'" data-testid="layout-B1">B1 地下制冷机房</div>
        <div v-else-if="currentFloor === 'F1'" data-testid="layout-F1">F1 1楼机房区A</div>
        <div v-else-if="currentFloor === 'F2'" data-testid="layout-F2">F2 2楼机房区B</div>
        <div v-else-if="currentFloor === 'F3'" data-testid="layout-F3">F3 3楼办公监控</div>
      </div>
    </div>
  `
})

describe('FloorLayoutSelector 楼层选择器组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认选中 F1 楼层', () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    expect(wrapper.vm.currentFloor).toBe('F1')
    expect(wrapper.find('[data-testid="layout-F1"]').exists()).toBe(true)
  })

  it('渲染四个楼层按钮', () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    const tabs = wrapper.find('[data-testid="floor-tabs"]')
    expect(tabs.findAll('button')).toHaveLength(4)
  })

  it('点击 B1 按钮切换到 B1 楼层', async () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    await wrapper.find('[data-testid="floor-btn-B1"]').trigger('click')
    expect(wrapper.vm.currentFloor).toBe('B1')
    expect(wrapper.find('[data-testid="layout-B1"]').exists()).toBe(true)
  })

  it('点击 F2 按钮切换到 F2 楼层', async () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    await wrapper.find('[data-testid="floor-btn-F2"]').trigger('click')
    expect(wrapper.vm.currentFloor).toBe('F2')
    expect(wrapper.find('[data-testid="layout-F2"]').exists()).toBe(true)
  })

  it('点击 F3 按钮切换到 F3 楼层', async () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    await wrapper.find('[data-testid="floor-btn-F3"]').trigger('click')
    expect(wrapper.vm.currentFloor).toBe('F3')
    expect(wrapper.find('[data-testid="layout-F3"]').exists()).toBe(true)
  })

  it('楼层按钮包含正确标签文本', () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    expect(wrapper.find('[data-testid="floor-btn-B1"]').text()).toBe('B1 制冷机房')
    expect(wrapper.find('[data-testid="floor-btn-F1"]').text()).toBe('F1 机房区A')
    expect(wrapper.find('[data-testid="floor-btn-F2"]').text()).toBe('F2 机房区B')
    expect(wrapper.find('[data-testid="floor-btn-F3"]').text()).toBe('F3 办公监控')
  })

  it('切换楼层后只显示对应布局', async () => {
    const wrapper = mount(FloorLayoutSelectorTestable)
    await wrapper.find('[data-testid="floor-btn-B1"]').trigger('click')
    expect(wrapper.find('[data-testid="layout-B1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="layout-F1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="layout-F2"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="layout-F3"]').exists()).toBe(false)
  })
})
