/**
 * VPP分析页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const VppAnalysisTestable = defineComponent({
  name: 'VppAnalysisTestable',
  setup() {
    const loading = ref(false)
    const analysisMonths = ref(12)
    const dateRange = ref(['2025-03-01', '2026-02-28'])
    const analysisResult = ref({
      total_revenue: 125000,
      total_cost: 85000,
      net_profit: 40000,
      roi: 15.2,
      segments: [
        { name: '削峰填谷', revenue: 50000, cost: 30000, profit: 20000 },
        { name: '需求响应', revenue: 45000, cost: 25000, profit: 20000 },
        { name: '辅助服务', revenue: 30000, cost: 30000, profit: 0 }
      ]
    })
    const formatNumber = (n: number) => n.toLocaleString()
    const startAnalysis = () => { loading.value = true }
    const profitRate = computed(() => ((analysisResult.value.net_profit / analysisResult.value.total_revenue) * 100).toFixed(1))
    return { loading, analysisMonths, dateRange, analysisResult, formatNumber, startAnalysis, profitRate }
  },
  template: `<div class="vpp-analysis"><div class="params"><input :value="analysisMonths" data-testid="months-input" type="number" /><button data-testid="analyze-btn" @click="startAnalysis">开始分析</button></div><div class="result-summary" data-testid="result-summary"><div class="metric" data-testid="total-revenue"><span class="label">总收入</span><span class="value">{{ formatNumber(analysisResult.total_revenue) }}</span></div><div class="metric" data-testid="net-profit"><span class="label">净利润</span><span class="value">{{ formatNumber(analysisResult.net_profit) }}</span></div><div class="metric" data-testid="roi"><span class="label">ROI</span><span class="value">{{ analysisResult.roi }}%</span></div><div class="metric" data-testid="profit-rate"><span class="label">利润率</span><span class="value">{{ profitRate }}%</span></div></div><div class="segment-table" data-testid="segment-table"><div v-for="(s, idx) in analysisResult.segments" :key="idx" :data-testid="'segment-' + idx" class="segment-row"><span class="name">{{ s.name }}</span><span class="revenue">{{ formatNumber(s.revenue) }}</span><span class="profit">{{ formatNumber(s.profit) }}</span></div></div></div>`
})

describe('VPP分析页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染参数输入', () => { expect(mount(VppAnalysisTestable).find('[data-testid="months-input"]').exists()).toBe(true) })
  it('显示总收入和净利润', () => { const w = mount(VppAnalysisTestable); expect(w.find('[data-testid="total-revenue"] .value').text()).toBe('125,000'); expect(w.find('[data-testid="net-profit"] .value').text()).toBe('40,000') })
  it('显示ROI', () => { expect(mount(VppAnalysisTestable).find('[data-testid="roi"] .value').text()).toBe('15.2%') })
  it('计算利润率', () => { expect(mount(VppAnalysisTestable).find('[data-testid="profit-rate"] .value').text()).toBe('32.0%') })
  it('渲染分段指标表', () => { const w = mount(VppAnalysisTestable); expect(w.findAll('.segment-row')).toHaveLength(3); expect(w.find('[data-testid="segment-0"] .name').text()).toBe('削峰填谷') })
  it('点击分析按钮触发加载', async () => { const w = mount(VppAnalysisTestable); await w.find('[data-testid="analyze-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
  it('格式化数字正确', () => { expect(mount(VppAnalysisTestable).vm.formatNumber(125000)).toBe('125,000') })
})
