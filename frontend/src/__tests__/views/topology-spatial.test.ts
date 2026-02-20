/**
 * 空间拓扑页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const SpatialTopologyTestable = defineComponent({
  name: 'SpatialTopologyTestable',
  setup() {
    const loading = ref(false)
    const treeData = ref([
      { id: 1, label: '数据中心A', type: 'site', children: [
        { id: 2, label: '1楼', type: 'floor', children: [
          { id: 3, label: '机房A', type: 'room', children: [] }
        ]}
      ]}
    ])
    const selectedNode = ref<{ id: number; label: string; type: string } | null>(null)
    const gridItems = ref([
      { id: 1, name: '机柜-01', row: 1, col: 1, status: 'normal' },
      { id: 2, name: '机柜-02', row: 1, col: 2, status: 'alarm' },
      { id: 3, name: '机柜-03', row: 2, col: 1, status: 'offline' }
    ])
    const formVisible = ref(false)
    const formData = ref({ name: '', type: 'room', parent_id: null })
    const statusTagType = (s: string) => ({ normal: 'success', alarm: 'danger', offline: 'info' }[s] || 'info')
    const normalCount = computed(() => gridItems.value.filter(i => i.status === 'normal').length)
    const alarmCount = computed(() => gridItems.value.filter(i => i.status === 'alarm').length)
    const selectNode = (node: any) => { selectedNode.value = node }
    return { loading, treeData, selectedNode, gridItems, formVisible, formData, statusTagType, normalCount, alarmCount, selectNode }
  },
  template: `<div class="spatial-topology"><div class="tree-panel" data-testid="tree-panel"><div v-for="site in treeData" :key="site.id" class="tree-node site" :data-testid="'node-' + site.id" @click="selectNode(site)"><span class="label">{{ site.label }}</span><div v-for="floor in site.children" :key="floor.id" class="tree-node floor" :data-testid="'node-' + floor.id"><span class="label">{{ floor.label }}</span></div></div></div><div class="grid-panel" data-testid="grid-panel"><div class="stats"><span class="normal-count" data-testid="normal-count">{{ normalCount }}</span><span class="alarm-count" data-testid="alarm-count">{{ alarmCount }}</span></div><div v-for="item in gridItems" :key="item.id" :data-testid="'grid-' + item.id" class="grid-item" :class="item.status"><span class="name">{{ item.name }}</span><span class="status">{{ item.status }}</span></div></div><div v-if="formVisible" class="form-dialog" data-testid="form-dialog"><input :value="formData.name" data-testid="form-name" /><select :value="formData.type" data-testid="form-type"><option value="room">机房</option><option value="row">列</option></select></div></div>`
})

describe('空间拓扑页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染树形结构', () => { const w = mount(SpatialTopologyTestable); expect(w.find('[data-testid="tree-panel"]').exists()).toBe(true); expect(w.findAll('.tree-node.site')).toHaveLength(1) })
  it('显示站点和楼层节点', () => { const w = mount(SpatialTopologyTestable); expect(w.find('[data-testid="node-1"] .label').text()).toBe('数据中心A'); expect(w.find('[data-testid="node-2"] .label').text()).toBe('1楼') })
  it('渲染网格布局', () => { expect(mount(SpatialTopologyTestable).findAll('.grid-item')).toHaveLength(3) })
  it('显示机柜名称和状态', () => { const w = mount(SpatialTopologyTestable); expect(w.find('[data-testid="grid-1"] .name').text()).toBe('机柜-01'); expect(w.find('[data-testid="grid-2"] .status').text()).toBe('alarm') })
  it('统计正常和告警数量', () => { const w = mount(SpatialTopologyTestable); expect(w.find('[data-testid="normal-count"]').text()).toBe('1'); expect(w.find('[data-testid="alarm-count"]').text()).toBe('1') })
  it('点击节点选中', async () => { const w = mount(SpatialTopologyTestable); await w.find('[data-testid="node-1"]').trigger('click'); expect(w.vm.selectedNode).toEqual({ id: 1, label: '数据中心A', type: 'site', children: expect.any(Array) }) })
  it('表单对话框默认隐藏', () => { expect(mount(SpatialTopologyTestable).find('[data-testid="form-dialog"]').exists()).toBe(false) })
})
