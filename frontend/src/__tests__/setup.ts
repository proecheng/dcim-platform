/**
 * Vitest 全局 setup
 * - 模拟 localStorage
 * - 模拟 Element Plus 组件
 */
import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// 模拟 localStorage
const store: Record<string, string> = {}
const localStorageMock = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value }),
  removeItem: vi.fn((key: string) => { delete store[key] }),
  clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]) }),
  get length() { return Object.keys(store).length },
  key: vi.fn((i: number) => Object.keys(store)[i] ?? null)
}
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// 模拟 Element Plus 消息组件
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn()
    }
  }
})

// 全局 stubs — 避免 Element Plus 组件渲染问题
config.global.stubs = {
  ElIcon: { template: '<span><slot /></span>' },
  ElButton: { template: '<button><slot /></button>' },
  ElCard: { template: '<div class="el-card"><slot /></div>' },
  ElRow: { template: '<div class="el-row"><slot /></div>' },
  ElCol: { template: '<div class="el-col"><slot /></div>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div class="el-form-item"><slot /></div>' },
  ElInput: { template: '<input />' },
  ElTable: { template: '<table><slot /></table>' },
  ElTableColumn: { template: '<td><slot /></td>' },
  ElTag: { template: '<span class="el-tag"><slot /></span>' },
  ElSelect: { template: '<select><slot /></select>' },
  ElOption: { template: '<option><slot /></option>' },
  ElPagination: { template: '<div class="el-pagination" />' },
  ElTabs: { template: '<div class="el-tabs"><slot /></div>' },
  ElTabPane: { template: '<div class="el-tab-pane"><slot /></div>' },
  ElSwitch: { template: '<input type="checkbox" />' },
  ElEmpty: { template: '<div class="el-empty" />' },
  ElTooltip: { template: '<span><slot /></span>' }
}
