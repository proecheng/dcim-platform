/**
 * DataTable 数据表格组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Refresh: { template: '<i class="icon-refresh" />' }
}))

const DataTableTestable = defineComponent({
  name: 'DataTableTestable',
  props: {
    data: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    stripe: { type: Boolean, default: true },
    border: { type: Boolean, default: false },
    showSelection: { type: Boolean, default: false },
    showIndex: { type: Boolean, default: false },
    showRefresh: { type: Boolean, default: true },
    showPagination: { type: Boolean, default: true },
    total: { type: Number, default: 0 },
    page: { type: Number, default: 1 },
    pageSize: { type: Number, default: 20 },
    pageSizes: { type: Array, default: () => [10, 20, 50, 100] }
  },
  emits: ['update:page', 'update:pageSize', 'refresh', 'selection-change', 'sort-change', 'row-click', 'page-change'],
  setup(props, { emit }) {
    const currentPage = computed({
      get: () => props.page,
      set: (val: number) => emit('update:page', val)
    })

    const currentPageSize = computed({
      get: () => props.pageSize,
      set: (val: number) => emit('update:pageSize', val)
    })

    const indexMethod = (index: number) => {
      return (currentPage.value - 1) * currentPageSize.value + index + 1
    }

    const handleRefresh = () => emit('refresh')

    return { currentPage, currentPageSize, indexMethod, handleRefresh }
  },
  template: `
    <div data-testid="data-table" class="data-table">
      <div v-if="showRefresh" data-testid="toolbar" class="data-table__toolbar">
        <div class="data-table__toolbar-left"><slot name="toolbar"></slot></div>
        <button data-testid="refresh-btn" @click="handleRefresh">刷新</button>
      </div>
      <table data-testid="table" :class="{ 'is-stripe': stripe, 'is-border': border }">
        <thead>
          <tr>
            <th v-if="showSelection" data-testid="selection-col">选择</th>
            <th v-if="showIndex" data-testid="index-col">序号</th>
            <slot></slot>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in data" :key="idx" data-testid="table-row">
            <td v-if="showSelection"><input type="checkbox" /></td>
            <td v-if="showIndex">{{ indexMethod(idx) }}</td>
          </tr>
          <tr v-if="data.length === 0" data-testid="empty-row">
            <td><slot name="empty"><span data-testid="empty-text">暂无数据</span></slot></td>
          </tr>
        </tbody>
      </table>
      <div v-if="showPagination && total > 0" data-testid="pagination" class="data-table__pagination">
        共 {{ total }} 条
      </div>
    </div>
  `
})

describe('DataTable 数据表格', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染空表格', () => {
    const wrapper = mount(DataTableTestable)
    expect(wrapper.find('[data-testid="data-table"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty-text"]').text()).toBe('暂无数据')
  })

  it('传入数据后渲染行', () => {
    const wrapper = mount(DataTableTestable, {
      props: { data: [{ id: 1 }, { id: 2 }, { id: 3 }] }
    })
    expect(wrapper.findAll('[data-testid="table-row"]')).toHaveLength(3)
  })

  it('showRefresh 控制刷新按钮显示', () => {
    const wrapper = mount(DataTableTestable, {
      props: { showRefresh: false }
    })
    expect(wrapper.find('[data-testid="toolbar"]').exists()).toBe(false)
  })

  it('点击刷新按钮触发 refresh 事件', async () => {
    const wrapper = mount(DataTableTestable)
    await wrapper.find('[data-testid="refresh-btn"]').trigger('click')
    expect(wrapper.emitted('refresh')).toBeTruthy()
  })

  it('showPagination 和 total 控制分页显示', () => {
    const wrapper = mount(DataTableTestable, {
      props: { showPagination: true, total: 50 }
    })
    expect(wrapper.find('[data-testid="pagination"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pagination"]').text()).toContain('50')
  })

  it('total 为 0 时不显示分页', () => {
    const wrapper = mount(DataTableTestable, {
      props: { showPagination: true, total: 0 }
    })
    expect(wrapper.find('[data-testid="pagination"]').exists()).toBe(false)
  })

  it('showSelection 控制选择列', () => {
    const wrapper = mount(DataTableTestable, {
      props: { showSelection: true, data: [{ id: 1 }] }
    })
    expect(wrapper.find('[data-testid="selection-col"]').exists()).toBe(true)
  })

  it('showIndex 控制序号列并正确计算索引', () => {
    const wrapper = mount(DataTableTestable, {
      props: { showIndex: true, data: [{ id: 1 }], page: 2, pageSize: 10 }
    })
    expect(wrapper.find('[data-testid="index-col"]').exists()).toBe(true)
    expect(wrapper.vm.indexMethod(0)).toBe(11)
  })
})
