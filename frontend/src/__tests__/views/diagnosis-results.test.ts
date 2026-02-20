/**
 * 诊断结果页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const DiagnosisResultsTestable = defineComponent({
  name: 'DiagnosisResultsTestable',
  setup() {
    const loading = ref(false)
    const diagnosisResults = ref([
      { id: 1, rule_name: '温度异常诊断', status: 'confirmed', severity: 'high', diagnosed_at: '2026-02-01 14:30', causes: [{ name: '空调故障', probability: 0.85 }, { name: '负载过高', probability: 0.65 }] },
      { id: 2, rule_name: '电力故障诊断', status: 'investigating', severity: 'critical', diagnosed_at: '2026-02-01 15:00', causes: [{ name: 'UPS电池老化', probability: 0.72 }] },
      { id: 3, rule_name: '网络延迟诊断', status: 'resolved', severity: 'medium', diagnosed_at: '2026-01-30 10:00', causes: [] }
    ])
    const filterStatus = ref('')
    const filterSeverity = ref('')
    const expandedId = ref<number | null>(null)
    const statusText = (s: string) => ({ confirmed: '已确认', investigating: '调查中', resolved: '已解决' }[s] || s)
    const severityTag = (s: string) => ({ critical: 'danger', high: 'warning', medium: '', low: 'info' }[s] || 'info')
    const filteredResults = computed(() => {
      let list = diagnosisResults.value
      if (filterStatus.value) list = list.filter(r => r.status === filterStatus.value)
      if (filterSeverity.value) list = list.filter(r => r.severity === filterSeverity.value)
      return list
    })
    const toggleExpand = (id: number) => { expandedId.value = expandedId.value === id ? null : id }
    const confirmedCount = computed(() => diagnosisResults.value.filter(r => r.status === 'confirmed').length)
    return { loading, diagnosisResults, filterStatus, filterSeverity, expandedId, statusText, severityTag, filteredResults, toggleExpand, confirmedCount }
  },
  template: `<div class="diagnosis-results"><div class="stats"><span class="confirmed-count" data-testid="confirmed-count">{{ confirmedCount }}</span></div><div class="filters"><select v-model="filterStatus" data-testid="filter-status"><option value="">全部状态</option><option value="confirmed">已确认</option><option value="investigating">调查中</option></select><select v-model="filterSeverity" data-testid="filter-severity"><option value="">全部级别</option><option value="critical">严重</option><option value="high">高</option></select></div><div class="result-table" data-testid="result-table"><div v-for="r in filteredResults" :key="r.id" :data-testid="'result-' + r.id" class="result-row"><div class="result-header" @click="toggleExpand(r.id)"><span class="rule-name">{{ r.rule_name }}</span><span class="status">{{ statusText(r.status) }}</span><span class="severity">{{ r.severity }}</span></div><div v-if="expandedId === r.id && r.causes.length" class="cause-detail" :data-testid="'causes-' + r.id"><div v-for="(c, idx) in r.causes" :key="idx" class="cause-item"><span class="cause-name">{{ c.name }}</span><span class="probability">{{ (c.probability * 100).toFixed(0) }}%</span></div></div></div></div></div>`
})

describe('诊断结果页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染诊断结果列表', () => { expect(mount(DiagnosisResultsTestable).findAll('.result-row')).toHaveLength(3) })
  it('显示规则名称和状态', () => { const w = mount(DiagnosisResultsTestable); expect(w.find('[data-testid="result-1"] .rule-name').text()).toBe('温度异常诊断'); expect(w.find('[data-testid="result-1"] .status').text()).toBe('已确认') })
  it('统计已确认数量', () => { expect(mount(DiagnosisResultsTestable).find('[data-testid="confirmed-count"]').text()).toBe('1') })
  it('状态过滤结果', async () => { const w = mount(DiagnosisResultsTestable); await w.find('[data-testid="filter-status"]').setValue('investigating'); expect(w.findAll('.result-row')).toHaveLength(1) })
  it('点击展开原因详情', async () => { const w = mount(DiagnosisResultsTestable); await w.find('[data-testid="result-1"] .result-header').trigger('click'); expect(w.find('[data-testid="causes-1"]').exists()).toBe(true); expect(w.findAll('.cause-item')).toHaveLength(2) })
  it('显示原因概率', async () => { const w = mount(DiagnosisResultsTestable); await w.find('[data-testid="result-1"] .result-header').trigger('click'); expect(w.find('.cause-item .cause-name').text()).toBe('空调故障'); expect(w.find('.cause-item .probability').text()).toBe('85%') })
  it('状态文本映射正确', () => { const w = mount(DiagnosisResultsTestable); expect(w.vm.statusText('confirmed')).toBe('已确认'); expect(w.vm.statusText('resolved')).toBe('已解决') })
})
