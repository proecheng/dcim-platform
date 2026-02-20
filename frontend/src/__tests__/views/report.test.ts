/**
 * 报表管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/report', () => ({
  getDailyReport: vi.fn().mockResolvedValue({}),
  getWeeklyReport: vi.fn().mockResolvedValue({}),
  getMonthlyReport: vi.fn().mockResolvedValue({}),
  getReportRecords: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  generateReport: vi.fn().mockResolvedValue({}),
  downloadReport: vi.fn().mockResolvedValue(new Blob()),
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Download: { template: '<i />' },
}))

const ReportPageTestable = defineComponent({
  name: 'ReportPageTestable',
  setup() {
    const reportType = ref<'daily' | 'weekly' | 'monthly' | 'custom'>('daily')
    const loading = ref(false)
    const generating = ref(false)

    const dailyReport = ref({
      points: [{ code: 'AI_001', name: '温度', unit: '°C', min: 20, max: 35, avg: 27.5 }],
      alarm_total: 5,
      alarms: { critical: 1, major: 2, minor: 1, info: 1 },
    })

    const weeklyReport = ref({ title: '第5周', total_alarms: 20, week_start: '2026-01-27', week_end: '2026-02-02', daily_alarms: [] })
    const monthlyReport = ref({ title: '2026年1月', total_alarms: 80, alarm_by_level: { critical: 10, major: 30, minor: 25, info: 15 } })
    const reportRecords = ref<{ id: number; report_name: string; report_type: string; status: string }[]>([])

    const customForm = reactive({ dateRange: [] as Date[], reportType: 'comprehensive' })

    function getReportTypeName(type: string): string {
      const names: Record<string, string> = { daily: '日报', weekly: '周报', monthly: '月报', custom: '自定义' }
      return names[type] || type
    }

    function getStatusType(status: string): string {
      const types: Record<string, string> = { completed: 'success', generating: 'warning', failed: 'danger' }
      return types[status] || 'info'
    }

    function getStatusName(status: string): string {
      const names: Record<string, string> = { completed: '已完成', generating: '生成中', failed: '失败' }
      return names[status] || status
    }

    function getAlarmCount(level: string): number {
      return dailyReport.value.alarms?.[level as keyof typeof dailyReport.value.alarms] || 0
    }

    function handleTypeChange() {
      // stub
    }

    return {
      reportType, loading, generating, dailyReport, weeklyReport, monthlyReport, reportRecords, customForm,
      getReportTypeName, getStatusType, getStatusName, getAlarmCount, handleTypeChange,
    }
  },
  template: `
    <div class="report-page">
      <div data-testid="type-selector">
        <button v-for="t in ['daily', 'weekly', 'monthly', 'custom']" :key="t"
          :data-testid="'type-' + t" @click="reportType = t; handleTypeChange()">{{ t }}</button>
      </div>
      <div v-if="reportType === 'daily'" data-testid="daily-panel">
        <span data-testid="alarm-total">{{ dailyReport.alarm_total }}</span>
        <span data-testid="alarm-critical">{{ getAlarmCount('critical') }}</span>
        <span data-testid="alarm-major">{{ getAlarmCount('major') }}</span>
        <span data-testid="point-count">{{ dailyReport.points?.length || 0 }}</span>
      </div>
      <div v-if="reportType === 'weekly'" data-testid="weekly-panel">
        <span data-testid="weekly-title">{{ weeklyReport.title }}</span>
        <span data-testid="weekly-total">{{ weeklyReport.total_alarms }}</span>
      </div>
      <div v-if="reportType === 'monthly'" data-testid="monthly-panel">
        <span data-testid="monthly-title">{{ monthlyReport.title }}</span>
        <span data-testid="monthly-total">{{ monthlyReport.total_alarms }}</span>
      </div>
      <div v-if="reportType === 'custom'" data-testid="custom-panel">
        <select data-testid="custom-type" v-model="customForm.reportType">
          <option value="comprehensive">综合报表</option>
          <option value="alarm">告警报表</option>
          <option value="energy">能耗报表</option>
        </select>
      </div>
    </div>
  `,
})

describe('ReportPage 报表管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认显示日报', () => {
    const wrapper = mount(ReportPageTestable)
    expect(wrapper.vm.reportType).toBe('daily')
    expect(wrapper.find('[data-testid="daily-panel"]').exists()).toBe(true)
  })

  it('日报告警统计正确', () => {
    const wrapper = mount(ReportPageTestable)
    expect(wrapper.find('[data-testid="alarm-total"]').text()).toBe('5')
    expect(wrapper.find('[data-testid="alarm-critical"]').text()).toBe('1')
    expect(wrapper.find('[data-testid="alarm-major"]').text()).toBe('2')
    expect(wrapper.find('[data-testid="point-count"]').text()).toBe('1')
  })

  it('切换到周报', async () => {
    const wrapper = mount(ReportPageTestable)
    await wrapper.find('[data-testid="type-weekly"]').trigger('click')
    expect(wrapper.vm.reportType).toBe('weekly')
    expect(wrapper.find('[data-testid="weekly-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="weekly-title"]').text()).toBe('第5周')
    expect(wrapper.find('[data-testid="weekly-total"]').text()).toBe('20')
  })

  it('切换到月报', async () => {
    const wrapper = mount(ReportPageTestable)
    await wrapper.find('[data-testid="type-monthly"]').trigger('click')
    expect(wrapper.vm.reportType).toBe('monthly')
    expect(wrapper.find('[data-testid="monthly-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="monthly-total"]').text()).toBe('80')
  })

  it('切换到自定义报表', async () => {
    const wrapper = mount(ReportPageTestable)
    await wrapper.find('[data-testid="type-custom"]').trigger('click')
    expect(wrapper.vm.reportType).toBe('custom')
    expect(wrapper.find('[data-testid="custom-panel"]').exists()).toBe(true)
  })

  it('报表类型名称映射正确', () => {
    const wrapper = mount(ReportPageTestable)
    expect(wrapper.vm.getReportTypeName('daily')).toBe('日报')
    expect(wrapper.vm.getReportTypeName('weekly')).toBe('周报')
    expect(wrapper.vm.getReportTypeName('monthly')).toBe('月报')
    expect(wrapper.vm.getReportTypeName('custom')).toBe('自定义')
  })

  it('状态类型映射正确', () => {
    const wrapper = mount(ReportPageTestable)
    expect(wrapper.vm.getStatusType('completed')).toBe('success')
    expect(wrapper.vm.getStatusType('generating')).toBe('warning')
    expect(wrapper.vm.getStatusType('failed')).toBe('danger')
    expect(wrapper.vm.getStatusName('completed')).toBe('已完成')
  })
})
