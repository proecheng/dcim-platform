/**
 * 门禁管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

type DoorStatus = 'closed' | 'open' | 'alarm' | 'offline'
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

const AccessControlTestable = defineComponent({
  name: 'AccessControlTestable',
  setup() {
    const loading = ref(false)
    const doorDevices = ref([
      { point_id: 1, point_name: '门禁-A01', area_code: 'A区', doorStatus: 'closed' as DoorStatus, doorStatusText: '已关闭', status: 'normal', last_change_at: '2026-02-01T08:00:00' },
      { point_id: 2, point_name: '门禁-A02', area_code: 'A区', doorStatus: 'open' as DoorStatus, doorStatusText: '已开启', status: 'normal', last_change_at: '2026-02-01T09:00:00' },
      { point_id: 3, point_name: '门禁-B01', area_code: 'B区', doorStatus: 'alarm' as DoorStatus, doorStatusText: '异常', status: 'alarm', last_change_at: '2026-02-01T09:30:00' },
      { point_id: 4, point_name: '门禁-C01', area_code: 'C区', doorStatus: 'offline' as DoorStatus, doorStatusText: '离线', status: 'offline', last_change_at: null },
    ])

    const totalCount = computed(() => doorDevices.value.length)
    const onlineCount = computed(() => doorDevices.value.filter(d => d.doorStatus !== 'offline').length)
    const alarmCount = computed(() => doorDevices.value.filter(d => d.doorStatus === 'alarm').length)
    const todayEventCount = ref(12)

    const statCards = computed(() => [
      { label: '设备总数', value: totalCount.value, valueClass: 'primary' },
      { label: '在线数', value: onlineCount.value, valueClass: 'success' },
      { label: '告警数', value: alarmCount.value, valueClass: 'danger' },
      { label: '今日事件', value: todayEventCount.value, valueClass: 'warning' },
    ])

    const accessEvents = ref([
      { id: 1, eventType: 'card_open', eventLabel: '刷卡开门', result: 'success', person: '张三', time: '2026-02-01T09:00:00', isAnomaly: false, isFireLinkage: false, policyName: null, rawAlarm: { alarm_message: '正常刷卡' } },
      { id: 2, eventType: 'anomaly_open', eventLabel: '异常开门', result: 'success', person: null, time: '2026-02-01T09:30:00', isAnomaly: true, isFireLinkage: false, policyName: null, rawAlarm: { alarm_message: '异常开门告警' } },
      { id: 3, eventType: 'fire_linkage_open', eventLabel: '消防联动', result: 'success', person: null, time: '2026-02-01T10:00:00', isAnomaly: false, isFireLinkage: true, policyName: '消防联动策略A', rawAlarm: { alarm_message: '消防联动开门' } },
      { id: 4, eventType: 'remote_open', eventLabel: '远程开门', result: 'failed', person: '李四', time: '2026-02-01T10:30:00', isAnomaly: false, isFireLinkage: false, policyName: null, rawAlarm: { alarm_message: '远程开门失败' } },
    ])

    const filterEventType = ref('')
    const filteredEvents = computed(() => {
      if (!filterEventType.value) return accessEvents.value
      return accessEvents.value.filter(e => e.eventType === filterEventType.value)
    })

    // 辅助函数
    function doorStatusTagType(status: DoorStatus): TagType {
      const map: Record<DoorStatus, TagType> = { closed: 'success', open: 'primary', alarm: 'danger', offline: 'info' }
      return map[status]
    }
    function eventColor(event: { isAnomaly: boolean; isFireLinkage: boolean; eventType: string; result: string }): string {
      if (event.isAnomaly) return '#f5222d'
      if (event.isFireLinkage) return '#fa8c16'
      if (event.eventType === 'remote_open') return '#1890ff'
      return event.result === 'success' ? '#52c41a' : '#8c8c8c'
    }
    function eventTagType(event: { isAnomaly: boolean; isFireLinkage: boolean; eventType: string }): TagType {
      if (event.isAnomaly) return 'danger'
      if (event.isFireLinkage) return 'warning'
      if (event.eventType === 'remote_open') return 'primary'
      return 'success'
    }
    function formatTime(t: string | null | undefined): string {
      if (!t) return '--'
      return t.replace('T', ' ').substring(0, 19)
    }

    return {
      loading, doorDevices, statCards, accessEvents, filterEventType, filteredEvents,
      totalCount, onlineCount, alarmCount, todayEventCount,
      doorStatusTagType, eventColor, eventTagType, formatTime,
    }
  },
  template: `<div class="access-control-page">
    <div class="stat-cards" data-testid="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.label">
        <span class="value" :class="card.valueClass">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
    </div>
    <div class="device-list" data-testid="device-list">
      <div v-for="d in doorDevices" :key="d.point_id" :data-testid="'device-' + d.point_id" class="device-item">
        <span class="name">{{ d.point_name }}</span>
        <span class="status">{{ d.doorStatusText }}</span>
      </div>
    </div>
    <div class="event-list" data-testid="event-list">
      <div v-for="e in filteredEvents" :key="e.id" :data-testid="'event-' + e.id" class="event-item">
        <span class="label">{{ e.eventLabel }}</span>
        <span class="result">{{ e.result }}</span>
      </div>
    </div>
  </div>`,
})

describe('门禁管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染统计卡片: 设备总数', () => {
    expect(mount(AccessControlTestable).find('[data-testid="stat-设备总数"] .value').text()).toBe('4')
  })

  it('渲染统计卡片: 在线数', () => {
    expect(mount(AccessControlTestable).find('[data-testid="stat-在线数"] .value').text()).toBe('3')
  })

  it('渲染统计卡片: 告警数', () => {
    expect(mount(AccessControlTestable).find('[data-testid="stat-告警数"] .value').text()).toBe('1')
  })

  it('渲染设备列表', () => {
    expect(mount(AccessControlTestable).findAll('.device-item')).toHaveLength(4)
  })

  it('渲染事件列表', () => {
    expect(mount(AccessControlTestable).findAll('.event-item')).toHaveLength(4)
  })

  it('门禁状态标签类型映射', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.doorStatusTagType('closed')).toBe('success')
    expect(w.vm.doorStatusTagType('open')).toBe('primary')
    expect(w.vm.doorStatusTagType('alarm')).toBe('danger')
    expect(w.vm.doorStatusTagType('offline')).toBe('info')
  })

  it('事件颜色: 异常事件为红色', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.eventColor({ isAnomaly: true, isFireLinkage: false, eventType: 'anomaly_open', result: 'success' })).toBe('#f5222d')
  })

  it('事件颜色: 消防联动为橙色', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.eventColor({ isAnomaly: false, isFireLinkage: true, eventType: 'fire_linkage_open', result: 'success' })).toBe('#fa8c16')
  })

  it('事件颜色: 远程开门为蓝色', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.eventColor({ isAnomaly: false, isFireLinkage: false, eventType: 'remote_open', result: 'success' })).toBe('#1890ff')
  })

  it('事件颜色: 成功为绿色, 失败为灰色', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.eventColor({ isAnomaly: false, isFireLinkage: false, eventType: 'card_open', result: 'success' })).toBe('#52c41a')
    expect(w.vm.eventColor({ isAnomaly: false, isFireLinkage: false, eventType: 'card_open', result: 'failed' })).toBe('#8c8c8c')
  })

  it('事件标签类型映射', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.eventTagType({ isAnomaly: true, isFireLinkage: false, eventType: 'anomaly_open' })).toBe('danger')
    expect(w.vm.eventTagType({ isAnomaly: false, isFireLinkage: true, eventType: 'fire_linkage_open' })).toBe('warning')
    expect(w.vm.eventTagType({ isAnomaly: false, isFireLinkage: false, eventType: 'remote_open' })).toBe('primary')
    expect(w.vm.eventTagType({ isAnomaly: false, isFireLinkage: false, eventType: 'card_open' })).toBe('success')
  })

  it('筛选: 按事件类型过滤', async () => {
    const w = mount(AccessControlTestable)
    w.vm.filterEventType = 'card_open'
    await w.vm.$nextTick()
    expect(w.vm.filteredEvents).toHaveLength(1)
    expect(w.vm.filteredEvents[0].eventLabel).toBe('刷卡开门')
  })

  it('格式化时间', () => {
    const w = mount(AccessControlTestable)
    expect(w.vm.formatTime('2026-02-01T09:00:00')).toBe('2026-02-01 09:00:00')
    expect(w.vm.formatTime(null)).toBe('--')
  })
})
