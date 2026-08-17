import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Reports from './Reports.vue'

const diagnosisApi = vi.hoisted(() => ({
  getMisdiagnosisReports: vi.fn(),
  getMisdiagnosisReport: vi.fn(),
  generateMisdiagnosisReport: vi.fn(),
  exportMisdiagnosisReport: vi.fn()
}))

vi.mock('@/api/modules/diagnosis', () => diagnosisApi)

describe('diagnosis reports persisted Markdown path', () => {
  beforeEach(() => {
    diagnosisApi.getMisdiagnosisReports.mockResolvedValue({ items: [], total: 0 })
    diagnosisApi.getMisdiagnosisReport.mockResolvedValue({
      id: 39,
      report_type: 'misdiagnosis',
      report_period: '2026-08',
      report_version: '1',
      content: '# 安全标题\n\n<img src=x onerror="window.__reportXss = true">',
      summary: null,
      generated_at: '2026-08-14T00:00:00Z',
      generated_by: 'system',
      deleted_at: null,
      updated_at: '2026-08-14T00:00:00Z'
    })
  })

  it('sanitizes the report returned by the detail API before rendering', async () => {
    const wrapper = mount(Reports, {
      global: {
        stubs: {
          ElDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          ElDescriptions: { template: '<div><slot /></div>' },
          ElDescriptionsItem: { template: '<div><slot /></div>' },
          ElDatePicker: { template: '<input />' },
          ElTableColumn: { template: '<div />' }
        },
        directives: { loading: () => undefined }
      }
    })
    await flushPromises()

    await (wrapper.vm as unknown as {
      handleView: (report: { id: number; report_period: string }) => Promise<void>
    }).handleView({ id: 39, report_period: '2026-08' })
    await flushPromises()

    expect(diagnosisApi.getMisdiagnosisReport).toHaveBeenCalledWith('2026-08')
    expect(wrapper.find('.safe-rich-text h1').text()).toBe('安全标题')
    expect(wrapper.find('.safe-rich-text img').exists()).toBe(false)
    expect(wrapper.find('.safe-rich-text [onerror]').exists()).toBe(false)
    expect((globalThis as typeof globalThis & { __reportXss?: boolean }).__reportXss).not.toBe(true)
  })

  it('formats missing summary percentages without crashing the table', async () => {
    const wrapper = mount(Reports, {
      global: {
        stubs: {
          ElDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          ElDescriptions: { template: '<div><slot /></div>' },
          ElDescriptionsItem: { template: '<div><slot /></div>' },
          ElDatePicker: { template: '<input />' },
          ElTableColumn: { template: '<div />' }
        },
        directives: { loading: () => undefined }
      }
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as { formatPercent: (value: unknown) => string }
    expect(vm.formatPercent(null)).toBe('N/A')
    expect(vm.formatPercent(undefined)).toBe('N/A')
    expect(vm.formatPercent(0.875)).toBe('87.5%')
  })
})
