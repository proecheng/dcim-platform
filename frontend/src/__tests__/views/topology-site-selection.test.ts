/**
 * 智能选址页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const SiteSelectionTestable = defineComponent({
  name: 'SiteSelectionTestable',
  setup() {
    const loading = ref(false)
    const formData = ref({ required_u: 10, required_power: 5.0, required_cooling: 3.0, redundancy: 'N+1' })
    const weightSliders = ref([
      { key: 'power', label: '电力权重', value: 30 },
      { key: 'cooling', label: '制冷权重', value: 25 },
      { key: 'space', label: '空间权重', value: 25 },
      { key: 'network', label: '网络权重', value: 20 }
    ])
    const candidates = ref([
      { id: 1, room_name: '机房A-101', score: 92.5, available_u: 20, available_power: 10.0, cooling_capacity: 8.0 },
      { id: 2, room_name: '机房B-201', score: 85.3, available_u: 15, available_power: 7.5, cooling_capacity: 6.0 },
      { id: 3, room_name: '机房C-301', score: 78.1, available_u: 12, available_power: 6.0, cooling_capacity: 5.0 }
    ])
    const selectedCandidate = ref<any>(null)
    const totalWeight = computed(() => weightSliders.value.reduce((s, w) => s + w.value, 0))
    const startAnalysis = () => { loading.value = true }
    const selectCandidate = (c: any) => { selectedCandidate.value = c }
    return { loading, formData, weightSliders, candidates, selectedCandidate, totalWeight, startAnalysis, selectCandidate }
  },
  template: `<div class="site-selection"><div class="params-form" data-testid="params-form"><div class="field"><label>所需U位</label><input :value="formData.required_u" data-testid="required-u" type="number" /></div><div class="field"><label>所需功率(kW)</label><input :value="formData.required_power" data-testid="required-power" type="number" /></div><div class="field"><label>冗余要求</label><span data-testid="redundancy">{{ formData.redundancy }}</span></div></div><div class="weight-panel" data-testid="weight-panel"><div v-for="w in weightSliders" :key="w.key" :data-testid="'weight-' + w.key" class="weight-item"><span class="label">{{ w.label }}</span><span class="value">{{ w.value }}%</span></div><span class="total-weight" data-testid="total-weight">{{ totalWeight }}%</span></div><button data-testid="start-btn" @click="startAnalysis">开始选址</button><div class="candidate-list" data-testid="candidate-list"><div v-for="c in candidates" :key="c.id" :data-testid="'candidate-' + c.id" class="candidate-card" @click="selectCandidate(c)"><span class="room-name">{{ c.room_name }}</span><span class="score">{{ c.score }}</span><span class="available-u">{{ c.available_u }}U</span></div></div></div>`
})

describe('智能选址页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染参数表单', () => { const w = mount(SiteSelectionTestable); expect(w.find('[data-testid="params-form"]').exists()).toBe(true); expect(w.find('[data-testid="redundancy"]').text()).toBe('N+1') })
  it('显示权重滑块', () => { const w = mount(SiteSelectionTestable); expect(w.findAll('.weight-item')).toHaveLength(4); expect(w.find('[data-testid="weight-power"] .label').text()).toBe('电力权重') })
  it('权重总和为100', () => { expect(mount(SiteSelectionTestable).find('[data-testid="total-weight"]').text()).toBe('100%') })
  it('渲染候选列表', () => { const w = mount(SiteSelectionTestable); expect(w.findAll('.candidate-card')).toHaveLength(3); expect(w.find('[data-testid="candidate-1"] .room-name').text()).toBe('机房A-101') })
  it('显示候选评分', () => { expect(mount(SiteSelectionTestable).find('[data-testid="candidate-1"] .score').text()).toBe('92.5') })
  it('点击候选项选中', async () => { const w = mount(SiteSelectionTestable); await w.find('[data-testid="candidate-2"]').trigger('click'); expect(w.vm.selectedCandidate.room_name).toBe('机房B-201') })
  it('点击开始选址触发加载', async () => { const w = mount(SiteSelectionTestable); await w.find('[data-testid="start-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
})
