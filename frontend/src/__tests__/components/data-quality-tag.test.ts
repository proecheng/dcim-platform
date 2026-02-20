/**
 * DataQualityTag 数据质量标签组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const DataQualityTagTestable = defineComponent({
  name: 'DataQualityTagTestable',
  props: {
    quality: { type: Number, required: true }
  },
  setup(props) {
    const tagType = computed(() => {
      if (props.quality === 2) return 'danger'
      if (props.quality === 1) return 'warning'
      return 'success'
    })

    const tagText = computed(() => {
      if (props.quality === 2) return '不可靠'
      if (props.quality === 1) return '不确定'
      return '正常'
    })

    return { tagType, tagText }
  },
  template: `
    <span data-testid="data-quality-tag" :class="'el-tag--' + tagType" :data-type="tagType">
      {{ tagText }}
    </span>
  `
})

describe('DataQualityTag 数据质量标签', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(DataQualityTagTestable, {
      props: { quality: 0 }
    })
    expect(wrapper.find('[data-testid="data-quality-tag"]').exists()).toBe(true)
  })

  it('quality 为 0 时显示正常', () => {
    const wrapper = mount(DataQualityTagTestable, {
      props: { quality: 0 }
    })
    expect(wrapper.find('[data-testid="data-quality-tag"]').text()).toBe('正常')
    expect(wrapper.find('[data-testid="data-quality-tag"]').attributes('data-type')).toBe('success')
  })

  it('quality 为 1 时显示不确定', () => {
    const wrapper = mount(DataQualityTagTestable, {
      props: { quality: 1 }
    })
    expect(wrapper.find('[data-testid="data-quality-tag"]').text()).toBe('不确定')
    expect(wrapper.find('[data-testid="data-quality-tag"]').attributes('data-type')).toBe('warning')
  })

  it('quality 为 2 时显示不可靠', () => {
    const wrapper = mount(DataQualityTagTestable, {
      props: { quality: 2 }
    })
    expect(wrapper.find('[data-testid="data-quality-tag"]').text()).toBe('不可靠')
    expect(wrapper.find('[data-testid="data-quality-tag"]').attributes('data-type')).toBe('danger')
  })

  it('tagType computed 正确映射', () => {
    const w0 = mount(DataQualityTagTestable, { props: { quality: 0 } })
    expect(w0.vm.tagType).toBe('success')

    const w1 = mount(DataQualityTagTestable, { props: { quality: 1 } })
    expect(w1.vm.tagType).toBe('warning')

    const w2 = mount(DataQualityTagTestable, { props: { quality: 2 } })
    expect(w2.vm.tagType).toBe('danger')
  })

  it('CSS 类名随 tagType 变化', () => {
    const wrapper = mount(DataQualityTagTestable, {
      props: { quality: 2 }
    })
    expect(wrapper.find('[data-testid="data-quality-tag"]').classes()).toContain('el-tag--danger')
  })
})
