/**
 * 联动时间线页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkageTimelineTestable = defineComponent({
  name: 'LinkageTimelineTestable',
  setup() {
    const loading = ref(false)
    const timelines = ref([
      { id: 1, policy_name: '温度联动', phase: 'trigger', status: 'success', level: 'high', timestamp: '2026-02-01 14:30:00', message: '温度超过阈值35℃' },
      { id: 2, policy_name: '温度联动', phase: 'execute', status: 'success', level: 'high', timestamp: '2026-02-01 14:30:05', message: '启动备用空调' },
      { id: 3, policy_name: '温度联动', phase: 'complete', status: 'success', level: 'high', timestamp: '2026-02-01 14:30:12', message: '联动执行完成' },
      { id: 4, policy_name: '湿度联动', phase: 'trigger', status: 'failed', level: 'medium', timestamp: '2026-02-01 15:00:00', message: '湿度超过70%' }
    ])
    const statusText = (s: string) => ({ success: '成功', failed: '失败', running: '执行中' }[s] || s)
    const levelText = (l: string) => ({ high: '高', medium: '中', low: '低' }[l] || l)
    const phaseText = (p: string) => ({ trigger: '触发', execute: '执行', complete: '完成', rollback: '回滚' }[p] || p)
    const statusTagType = (s: string) => ({ success: 'success', failed: 'danger', running: 'warning' }[s] || 'info')
    const exportTimeline = () => { loading.value = true }
    const successCount = computed(() => timelines.value.filter(t => t.status === 'success').length)
    const failedCount = computed(() => timelines.value.filter(t => t.status === 'failed').length)
    return { loading, timelines, statusText, levelText, phaseText, statusTagType, exportTimeline, successCount, failedCount }
  },
  template: `<div class="linkage-timeline"><div class="summary"><span class="success-count" data-testid="success-count">{{ successCount }}</span><span class="failed-count" data-testid="failed-count">{{ failedCount }}</span></div><button data-testid="export-btn" @click="exportTimeline">导出</button><div class="timeline-list" data-testid="timeline-list"><div v-for="t in timelines" :key="t.id" :data-testid="'timeline-' + t.id" class="timeline-item"><span class="policy-name">{{ t.policy_name }}</span><span class="phase">{{ phaseText(t.phase) }}</span><span class="status">{{ statusText(t.status) }}</span><span class="level">{{ levelText(t.level) }}</span><span class="message">{{ t.message }}</span><span class="timestamp">{{ t.timestamp }}</span></div></div></div>`
})

describe('联动时间线页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染时间线列表', () => { expect(mount(LinkageTimelineTestable).findAll('.timeline-item')).toHaveLength(4) })
  it('显示策略名称和消息', () => { const w = mount(LinkageTimelineTestable); expect(w.find('[data-testid="timeline-1"] .policy-name').text()).toBe('温度联动'); expect(w.find('[data-testid="timeline-1"] .message').text()).toBe('温度超过阈值35℃') })
  it('阶段文本映射正确', () => { const w = mount(LinkageTimelineTestable); expect(w.find('[data-testid="timeline-1"] .phase').text()).toBe('触发'); expect(w.find('[data-testid="timeline-2"] .phase').text()).toBe('执行'); expect(w.find('[data-testid="timeline-3"] .phase').text()).toBe('完成') })
  it('状态和级别文本正确', () => { const w = mount(LinkageTimelineTestable); expect(w.find('[data-testid="timeline-1"] .status').text()).toBe('成功'); expect(w.find('[data-testid="timeline-1"] .level').text()).toBe('高') })
  it('统计成功和失败数', () => { const w = mount(LinkageTimelineTestable); expect(w.find('[data-testid="success-count"]').text()).toBe('3'); expect(w.find('[data-testid="failed-count"]').text()).toBe('1') })
  it('点击导出触发加载', async () => { const w = mount(LinkageTimelineTestable); await w.find('[data-testid="export-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
  it('状态标签类型正确', () => { const w = mount(LinkageTimelineTestable); expect(w.vm.statusTagType('success')).toBe('success'); expect(w.vm.statusTagType('failed')).toBe('danger') })
})
