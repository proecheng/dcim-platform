/**
 * 告警列表组件测试
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

// 告警级别映射函数（从 alarm/index.vue 提取）
function getLevelTagType(level: string): string {
  const map: Record<string, string> = {
    critical: 'danger',
    major: 'warning',
    minor: 'primary',
    info: 'info'
  }
  return map[level] || 'info'
}

function getLevelText(level: string): string {
  const map: Record<string, string> = {
    critical: '紧急',
    major: '重要',
    minor: '一般',
    info: '提示'
  }
  return map[level] || level
}

function getStatusText(status: string): string {
  const map: Record<string, string> = {
    active: '活动',
    acknowledged: '已确认',
    resolved: '已解决'
  }
  return map[status] || status
}

// 可测试的告警列表组件
const AlarmListTestable = defineComponent({
  name: 'AlarmListTestable',
  setup() {
    const alarms = ref([
      { id: 1, alarm_level: 'critical', point_code: 'T001', point_name: '温度1', alarm_message: '温度过高', status: 'active', created_at: '2026-01-01' },
      { id: 2, alarm_level: 'major', point_code: 'H001', point_name: '湿度1', alarm_message: '湿度过高', status: 'acknowledged', created_at: '2026-01-01' },
      { id: 3, alarm_level: 'minor', point_code: 'V001', point_name: '电压1', alarm_message: '电压偏低', status: 'active', created_at: '2026-01-01' },
      { id: 4, alarm_level: 'info', point_code: 'P001', point_name: '功率1', alarm_message: '功率波动', status: 'resolved', created_at: '2026-01-01' }
    ])

    return { alarms, getLevelTagType, getLevelText, getStatusText }
  },
  template: `
    <div class="alarm-page">
      <table>
        <tbody>
          <tr v-for="alarm in alarms" :key="alarm.id" :data-testid="'alarm-' + alarm.id">
            <td class="level">
              <span :class="'tag-' + getLevelTagType(alarm.alarm_level)">{{ getLevelText(alarm.alarm_level) }}</span>
            </td>
            <td class="code">{{ alarm.point_code }}</td>
            <td class="name">{{ alarm.point_name }}</td>
            <td class="message">{{ alarm.alarm_message }}</td>
            <td class="status">{{ getStatusText(alarm.status) }}</td>
            <td class="actions">
              <button v-if="alarm.status === 'active'" class="btn-ack">确认</button>
              <button v-if="alarm.status === 'active' || alarm.status === 'acknowledged'" class="btn-process">处理</button>
              <button v-if="alarm.status !== 'resolved'" class="btn-resolve">解除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `
})

describe('告警列表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染所有告警行', () => {
    const wrapper = mount(AlarmListTestable)
    const rows = wrapper.findAll('tr')
    expect(rows).toHaveLength(4)
  })

  it('显示告警级别标签', () => {
    const wrapper = mount(AlarmListTestable)
    const firstRow = wrapper.find('[data-testid="alarm-1"]')
    expect(firstRow.find('.level span').text()).toBe('紧急')
    expect(firstRow.find('.level span').classes()).toContain('tag-danger')
  })

  it('各级别标签类型正确', () => {
    expect(getLevelTagType('critical')).toBe('danger')
    expect(getLevelTagType('major')).toBe('warning')
    expect(getLevelTagType('minor')).toBe('primary')
    expect(getLevelTagType('info')).toBe('info')
    expect(getLevelTagType('unknown')).toBe('info')
  })

  it('各级别文本正确', () => {
    expect(getLevelText('critical')).toBe('紧急')
    expect(getLevelText('major')).toBe('重要')
    expect(getLevelText('minor')).toBe('一般')
    expect(getLevelText('info')).toBe('提示')
  })

  it('状态文本正确', () => {
    expect(getStatusText('active')).toBe('活动')
    expect(getStatusText('acknowledged')).toBe('已确认')
    expect(getStatusText('resolved')).toBe('已解决')
  })

  it('活动告警显示确认/处理/解除按钮', () => {
    const wrapper = mount(AlarmListTestable)
    const activeRow = wrapper.find('[data-testid="alarm-1"]')
    expect(activeRow.find('.btn-ack').exists()).toBe(true)
    expect(activeRow.find('.btn-process').exists()).toBe(true)
    expect(activeRow.find('.btn-resolve').exists()).toBe(true)
  })

  it('已确认告警不显示确认按钮', () => {
    const wrapper = mount(AlarmListTestable)
    const ackedRow = wrapper.find('[data-testid="alarm-2"]')
    expect(ackedRow.find('.btn-ack').exists()).toBe(false)
    expect(ackedRow.find('.btn-process').exists()).toBe(true)
    expect(ackedRow.find('.btn-resolve').exists()).toBe(true)
  })

  it('已解决告警不显示操作按钮', () => {
    const wrapper = mount(AlarmListTestable)
    const resolvedRow = wrapper.find('[data-testid="alarm-4"]')
    expect(resolvedRow.find('.btn-ack').exists()).toBe(false)
    expect(resolvedRow.find('.btn-process').exists()).toBe(false)
    expect(resolvedRow.find('.btn-resolve').exists()).toBe(false)
  })

  it('显示点位编码和名称', () => {
    const wrapper = mount(AlarmListTestable)
    const row = wrapper.find('[data-testid="alarm-1"]')
    expect(row.find('.code').text()).toBe('T001')
    expect(row.find('.name').text()).toBe('温度1')
  })
})
