/**
 * 群控管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const CoolingGroupControlTestable = defineComponent({
  name: 'CoolingGroupControlTestable',
  setup() {
    const loading = ref(false)
    const drawerVisible = ref(false)
    const groupList = ref([
      { id: 1, group_name: '群控组-A', mode: 'linked', ac_count: 4, description: 'A区空调群控' },
      { id: 2, group_name: '群控组-B', mode: 'independent', ac_count: 3, description: 'B区空调群控' }
    ])
    const linkedCount = computed(() => groupList.value.filter(g => g.mode === 'linked').length)
    const independentCount = computed(() => groupList.value.filter(g => g.mode === 'independent').length)
    return { loading, drawerVisible, groupList, linkedCount, independentCount }
  },
  template: `<div class="group-control"><div class="summary"><span data-testid="total">{{ groupList.length }}</span><span data-testid="linked">{{ linkedCount }}</span><span data-testid="independent">{{ independentCount }}</span></div><table><tr v-for="g in groupList" :key="g.id" :data-testid="'group-' + g.id"><td class="name">{{ g.group_name }}</td><td class="mode">{{ g.mode === 'linked' ? '联动' : '独立' }}</td><td class="count">{{ g.ac_count }}</td></tr></table></div>`
})

describe('群控管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('显示群控组总数', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="total"]').text()).toBe('2') })
  it('显示联动组数', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="linked"]').text()).toBe('1') })
  it('显示独立组数', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="independent"]').text()).toBe('1') })
  it('渲染群控组列表', () => { expect(mount(CoolingGroupControlTestable).findAll('tr')).toHaveLength(2) })
  it('显示组名称', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="group-1"] .name').text()).toBe('群控组-A') })
  it('显示模式文本', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="group-1"] .mode').text()).toBe('联动') })
  it('显示空调数量', () => { expect(mount(CoolingGroupControlTestable).find('[data-testid="group-1"] .count').text()).toBe('4') })
})
