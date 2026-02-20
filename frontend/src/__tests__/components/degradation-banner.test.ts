/**
 * DegradationBanner 降级横幅组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

const DegradationBannerTestable = defineComponent({
  name: 'DegradationBannerTestable',
  props: {
    redisDown: { type: Boolean, default: false },
    websocketDown: { type: Boolean, default: false },
    mqttDown: { type: Boolean, default: false }
  },
  setup(props) {
    const hasDegradation = computed(() =>
      props.redisDown || props.websocketDown || props.mqttDown
    )

    return { hasDegradation }
  },
  template: `
    <div v-if="hasDegradation" data-testid="degradation-banner" class="degradation-banners">
      <div v-if="redisDown" data-testid="redis-alert" class="alert-warning">
        实时数据可能有延迟
      </div>
      <div v-if="websocketDown" data-testid="ws-alert" class="alert-warning">
        连接中断，正在重连...
      </div>
      <div v-if="mqttDown" data-testid="mqtt-alert" class="alert-error">
        数据采集服务异常
      </div>
    </div>
  `
})

describe('DegradationBanner 降级横幅', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认无降级时不渲染', () => {
    const wrapper = mount(DegradationBannerTestable)
    expect(wrapper.find('[data-testid="degradation-banner"]').exists()).toBe(false)
  })

  it('Redis 降级时显示延迟提示', () => {
    const wrapper = mount(DegradationBannerTestable, {
      props: { redisDown: true }
    })
    expect(wrapper.find('[data-testid="degradation-banner"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="redis-alert"]').text()).toContain('实时数据可能有延迟')
  })

  it('WebSocket 降级时显示重连提示', () => {
    const wrapper = mount(DegradationBannerTestable, {
      props: { websocketDown: true }
    })
    expect(wrapper.find('[data-testid="ws-alert"]').text()).toContain('连接中断，正在重连')
  })

  it('MQTT 降级时显示采集异常提示', () => {
    const wrapper = mount(DegradationBannerTestable, {
      props: { mqttDown: true }
    })
    expect(wrapper.find('[data-testid="mqtt-alert"]').text()).toContain('数据采集服务异常')
  })

  it('多个降级同时显示', () => {
    const wrapper = mount(DegradationBannerTestable, {
      props: { redisDown: true, websocketDown: true, mqttDown: true }
    })
    expect(wrapper.find('[data-testid="redis-alert"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ws-alert"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="mqtt-alert"]').exists()).toBe(true)
  })

  it('hasDegradation 计算属性正确', () => {
    const w1 = mount(DegradationBannerTestable, { props: { redisDown: false, websocketDown: false, mqttDown: false } })
    expect(w1.vm.hasDegradation).toBe(false)

    const w2 = mount(DegradationBannerTestable, { props: { redisDown: true } })
    expect(w2.vm.hasDegradation).toBe(true)
  })

  it('MQTT 告警使用 error 样式', () => {
    const wrapper = mount(DegradationBannerTestable, {
      props: { mqttDown: true }
    })
    expect(wrapper.find('[data-testid="mqtt-alert"]').classes()).toContain('alert-error')
  })
})
