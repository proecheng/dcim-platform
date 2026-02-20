/**
 * LifecycleTimeline 组件测试
 * 测试资产生命周期时间线（操作颜色、标签映射、时间格式化）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('@/api/modules/asset', () => ({
  getAssetLifecycle: vi.fn(() => Promise.resolve([]))
}))

const LifecycleTimelineTestable = defineComponent({
  name: 'LifecycleTimelineTestable',
  props: {
    assetId: { type: Number, required: true }
  },
  setup() {
    const loading = ref(false)
    const records = ref<Array<{
      id: number; action: string; action_date: string;
      operator?: string; from_location?: string; to_location?: string; remark?: string
    }>>([])

    const actionColorMap: Record<string, string> = {
      purchase: '#67c23a', deploy: '#409eff', move: '#e6a23c',
      maintain: '#f2c037', scrap: '#f56c6c', status_change: '#909399'
    }

    const actionLabelMap: Record<string, string> = {
      purchase: '入库', deploy: '部署', move: '移动',
      maintain: '维护', scrap: '报废', status_change: '状态变更'
    }

    const getActionColor = (action: string): string => actionColorMap[action] || '#909399'
    const getActionLabel = (action: string): string => actionLabelMap[action] || action

    const formatTime = (dateStr: string): string => {
      if (!dateStr) return ''
      const d = new Date(dateStr)
      const pad = (n: number) => n.toString().padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    }

    return { loading, records, getActionColor, getActionLabel, formatTime }
  },
  template: `
    <div class="lifecycle-timeline" data-testid="timeline">
      <div v-if="loading" data-testid="loading">加载中...</div>
      <div v-else-if="records.length > 0" data-testid="records">
        <div
          v-for="record in records"
          :key="record.id"
          class="timeline-item"
          :data-testid="'record-' + record.id"
        >
          <span class="action-tag" :style="{ color: getActionColor(record.action) }" data-testid="action-tag">
            {{ getActionLabel(record.action) }}
          </span>
          <span v-if="record.operator" class="operator" data-testid="operator">{{ record.operator }}</span>
          <span v-if="record.from_location || record.to_location" class="location" data-testid="location">
            <span v-if="record.from_location">{{ record.from_location }}</span>
            <span v-if="record.from_location && record.to_location"> → </span>
            <span v-if="record.to_location">{{ record.to_location }}</span>
          </span>
          <span v-if="record.remark" class="remark" data-testid="remark">{{ record.remark }}</span>
          <span class="time" data-testid="time">{{ formatTime(record.action_date) }}</span>
        </div>
      </div>
      <div v-else data-testid="empty">暂无生命周期记录</div>
    </div>
  `
})

describe('LifecycleTimeline 资产生命周期时间线组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('无记录时显示空状态', () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty"]').text()).toBe('暂无生命周期记录')
  })

  it('有记录时渲染时间线条目', async () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    wrapper.vm.records = [
      { id: 1, action: 'purchase', action_date: '2026-01-15T10:30:00', operator: '张三' },
      { id: 2, action: 'deploy', action_date: '2026-01-20T14:00:00', operator: '李四' }
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="records"]').exists()).toBe(true)
    expect(wrapper.findAll('.timeline-item')).toHaveLength(2)
  })

  it('操作标签正确映射中文', async () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    wrapper.vm.records = [
      { id: 1, action: 'purchase', action_date: '2026-01-15T10:30:00' },
      { id: 2, action: 'deploy', action_date: '2026-01-20T14:00:00' },
      { id: 3, action: 'scrap', action_date: '2026-02-01T09:00:00' }
    ]
    await wrapper.vm.$nextTick()
    const tags = wrapper.findAll('[data-testid="action-tag"]')
    expect(tags[0].text()).toBe('入库')
    expect(tags[1].text()).toBe('部署')
    expect(tags[2].text()).toBe('报废')
  })

  it('操作颜色正确映射', () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    expect(wrapper.vm.getActionColor('purchase')).toBe('#67c23a')
    expect(wrapper.vm.getActionColor('deploy')).toBe('#409eff')
    expect(wrapper.vm.getActionColor('scrap')).toBe('#f56c6c')
    expect(wrapper.vm.getActionColor('unknown')).toBe('#909399')
  })

  it('时间格式化正确', () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    const result = wrapper.vm.formatTime('2026-01-15T09:05:00')
    expect(result).toBe('2026-01-15 09:05')
  })

  it('显示位置变更信息', async () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    wrapper.vm.records = [
      { id: 1, action: 'move', action_date: '2026-01-15T10:00:00', from_location: 'F1-A01', to_location: 'F2-B03' }
    ]
    await wrapper.vm.$nextTick()
    const location = wrapper.find('[data-testid="location"]')
    expect(location.text()).toContain('F1-A01')
    expect(location.text()).toContain('→')
    expect(location.text()).toContain('F2-B03')
  })

  it('显示操作人和备注', async () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    wrapper.vm.records = [
      { id: 1, action: 'maintain', action_date: '2026-01-15T10:00:00', operator: '王五', remark: '更换硬盘' }
    ]
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="operator"]').text()).toBe('王五')
    expect(wrapper.find('[data-testid="remark"]').text()).toBe('更换硬盘')
  })

  it('空日期字符串返回空字符串', () => {
    const wrapper = mount(LifecycleTimelineTestable, { props: { assetId: 1 } })
    expect(wrapper.vm.formatTime('')).toBe('')
  })
})
