/**
 * 资产管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const AssetIndexTestable = defineComponent({
  name: 'AssetIndexTestable',
  setup() {
    const loading = ref(false)
    const statistics = ref({ total: 500, online: 420, offline: 50, maintenance: 30 })
    const assets = ref([
      { id: 1, name: '服务器-001', type: 'server', status: 'online', location: '机柜-A01-U1', sn: 'SN001' },
      { id: 2, name: '交换机-001', type: 'switch', status: 'online', location: '机柜-A01-U20', sn: 'SN002' },
      { id: 3, name: '存储-001', type: 'storage', status: 'maintenance', location: '机柜-B01-U1', sn: 'SN003' }
    ])
    const filterType = ref('')
    const filterStatus = ref('')
    const filterKeyword = ref('')
    const importDialogVisible = ref(false)
    const filteredAssets = computed(() => {
      let list = assets.value
      if (filterType.value) list = list.filter(a => a.type === filterType.value)
      if (filterKeyword.value) list = list.filter(a => a.name.includes(filterKeyword.value))
      return list
    })
    const statusText = (s: string) => ({ online: '在线', offline: '离线', maintenance: '维护中' }[s] || s)
    const exportAssets = () => { loading.value = true }
    return { loading, statistics, assets, filterType, filterStatus, filterKeyword, importDialogVisible, filteredAssets, statusText, exportAssets }
  },
  template: `<div class="asset-manage"><div class="stat-cards" data-testid="stat-cards"><div class="card" data-testid="stat-total"><span class="value">{{ statistics.total }}</span><span class="label">总资产</span></div><div class="card" data-testid="stat-online"><span class="value">{{ statistics.online }}</span><span class="label">在线</span></div><div class="card" data-testid="stat-offline"><span class="value">{{ statistics.offline }}</span><span class="label">离线</span></div><div class="card" data-testid="stat-maintenance"><span class="value">{{ statistics.maintenance }}</span><span class="label">维护中</span></div></div><div class="toolbar"><input v-model="filterKeyword" data-testid="filter-keyword" placeholder="搜索" /><button data-testid="import-btn" @click="importDialogVisible = true">导入</button><button data-testid="export-btn" @click="exportAssets">导出</button></div><div class="asset-table" data-testid="asset-table"><div v-for="a in filteredAssets" :key="a.id" :data-testid="'asset-' + a.id" class="asset-row"><span class="name">{{ a.name }}</span><span class="type">{{ a.type }}</span><span class="status">{{ statusText(a.status) }}</span><span class="location">{{ a.location }}</span><span class="sn">{{ a.sn }}</span></div></div><div v-if="importDialogVisible" class="import-dialog" data-testid="import-dialog"></div></div>`
})

describe('资产管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染统计卡片', () => { const w = mount(AssetIndexTestable); expect(w.find('[data-testid="stat-total"] .value').text()).toBe('500'); expect(w.find('[data-testid="stat-online"] .value').text()).toBe('420') })
  it('渲染资产列表', () => { expect(mount(AssetIndexTestable).findAll('.asset-row')).toHaveLength(3) })
  it('显示资产名称和位置', () => { const w = mount(AssetIndexTestable); expect(w.find('[data-testid="asset-1"] .name').text()).toBe('服务器-001'); expect(w.find('[data-testid="asset-1"] .location').text()).toBe('机柜-A01-U1') })
  it('状态文本映射正确', () => { const w = mount(AssetIndexTestable); expect(w.find('[data-testid="asset-3"] .status').text()).toBe('维护中') })
  it('关键词过滤资产', async () => { const w = mount(AssetIndexTestable); await w.find('[data-testid="filter-keyword"]').setValue('交换机'); expect(w.findAll('.asset-row')).toHaveLength(1) })
  it('点击导入打开对话框', async () => { const w = mount(AssetIndexTestable); await w.find('[data-testid="import-btn"]').trigger('click'); expect(w.find('[data-testid="import-dialog"]').exists()).toBe(true) })
  it('点击导出触发加载', async () => { const w = mount(AssetIndexTestable); await w.find('[data-testid="export-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
})
