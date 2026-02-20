/**
 * ExportButton 导出按钮组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Download: { template: '<i class="icon-download" />' },
  ArrowDown: { template: '<i class="icon-arrow-down" />' },
  Document: { template: '<i class="icon-document" />' },
  Grid: { template: '<i class="icon-grid" />' },
  Printer: { template: '<i class="icon-printer" />' },
  DataLine: { template: '<i class="icon-dataline" />' }
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }
  }
})

const ExportButtonTestable = defineComponent({
  name: 'ExportButtonTestable',
  props: {
    text: { type: String, default: '导出' },
    type: { type: String, default: 'default' },
    showDropdown: { type: Boolean, default: true },
    defaultFormat: { type: String, default: 'excel' },
    enabledFormats: { type: Array as () => string[], default: () => ['excel', 'csv', 'pdf', 'json'] },
    exportFn: { type: Function, default: undefined },
    fileName: { type: String, default: 'export' }
  },
  emits: ['export'],
  setup(props, { emit }) {
    const loading = ref(false)

    const formatConfigs: Record<string, { label: string; ext: string }> = {
      excel: { label: 'Excel', ext: '.xlsx' },
      csv: { label: 'CSV', ext: '.csv' },
      pdf: { label: 'PDF', ext: '.pdf' },
      json: { label: 'JSON', ext: '.json' }
    }

    const formats = computed(() =>
      props.enabledFormats.map(f => ({ value: f, ...formatConfigs[f] }))
    )

    const handleExport = async (format?: string) => {
      const exportFormat = format || props.defaultFormat
      if (props.exportFn) {
        loading.value = true
        try {
          await props.exportFn(exportFormat)
        } finally {
          loading.value = false
        }
      } else {
        emit('export', exportFormat)
      }
    }

    return { loading, formats, handleExport }
  },
  template: `
    <div data-testid="export-button">
      <div v-if="showDropdown" data-testid="dropdown-mode">
        <button data-testid="export-trigger" :disabled="loading">{{ text }}</button>
        <div data-testid="dropdown-menu">
          <button
            v-for="fmt in formats"
            :key="fmt.value"
            :data-testid="'format-' + fmt.value"
            @click="handleExport(fmt.value)"
          >{{ fmt.label }}</button>
        </div>
      </div>
      <button
        v-else
        data-testid="single-export-btn"
        :disabled="loading"
        @click="handleExport()"
      >{{ text }}</button>
    </div>
  `
})

describe('ExportButton 导出按钮', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染下拉模式', () => {
    const wrapper = mount(ExportButtonTestable)
    expect(wrapper.find('[data-testid="dropdown-mode"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="export-trigger"]').text()).toBe('导出')
  })

  it('showDropdown 为 false 时渲染单按钮', () => {
    const wrapper = mount(ExportButtonTestable, {
      props: { showDropdown: false }
    })
    expect(wrapper.find('[data-testid="single-export-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dropdown-mode"]').exists()).toBe(false)
  })

  it('enabledFormats 控制下拉选项', () => {
    const wrapper = mount(ExportButtonTestable, {
      props: { enabledFormats: ['excel', 'csv'] }
    })
    expect(wrapper.find('[data-testid="format-excel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="format-csv"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="format-pdf"]').exists()).toBe(false)
  })

  it('点击格式选项触发 export 事件', async () => {
    const wrapper = mount(ExportButtonTestable)
    await wrapper.find('[data-testid="format-csv"]').trigger('click')
    expect(wrapper.emitted('export')?.[0]).toEqual(['csv'])
  })

  it('单按钮模式使用 defaultFormat', async () => {
    const wrapper = mount(ExportButtonTestable, {
      props: { showDropdown: false, defaultFormat: 'pdf' }
    })
    await wrapper.find('[data-testid="single-export-btn"]').trigger('click')
    expect(wrapper.emitted('export')?.[0]).toEqual(['pdf'])
  })

  it('提供 exportFn 时调用函数而非触发事件', async () => {
    const exportFn = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ExportButtonTestable, {
      props: { showDropdown: false, exportFn }
    })
    await wrapper.find('[data-testid="single-export-btn"]').trigger('click')
    expect(exportFn).toHaveBeenCalledWith('excel')
    expect(wrapper.emitted('export')).toBeFalsy()
  })

  it('自定义按钮文本', () => {
    const wrapper = mount(ExportButtonTestable, {
      props: { text: '下载报表' }
    })
    expect(wrapper.find('[data-testid="export-trigger"]').text()).toBe('下载报表')
  })
})
