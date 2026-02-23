/**
 * 复合条件组编辑器组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))

// ── 条件树类型 ──
interface ConditionItem {
  id: string
  type: 'condition'
  pointId: number | undefined
  pointName: string
  operator: '>' | '<' | '=' | '>=' | '<='
  threshold: number | undefined
}

interface ConditionGroup {
  id: string
  type: 'group'
  logic: 'AND' | 'OR'
  children: (ConditionItem | ConditionGroup)[]
}

// ── 从 CompoundConditionGroup.vue 提取的操作逻辑 ──
function addConditionToGroup(group: ConditionGroup): ConditionGroup {
  return {
    ...group,
    children: [
      ...group.children,
      { id: 'new-cond', type: 'condition', pointId: undefined, pointName: '', operator: '>' as const, threshold: undefined }
    ]
  }
}

function addSubGroupToGroup(group: ConditionGroup, depth: number, maxDepth: number): ConditionGroup {
  if (depth >= maxDepth) return group
  return {
    ...group,
    children: [
      ...group.children,
      { id: 'new-group', type: 'group', logic: 'AND' as const, children: [] }
    ]
  }
}

function removeChildFromGroup(group: ConditionGroup, idx: number): ConditionGroup {
  return {
    ...group,
    children: group.children.filter((_, i) => i !== idx)
  }
}

function updateChildCondition(group: ConditionGroup, idx: number, field: string, val: unknown, pointOptions: Array<{ id: number; point_name: string }>): ConditionGroup {
  const child = group.children[idx]
  if (child.type !== 'condition') return group
  const updated = { ...child }
  if (field === 'pointId') {
    updated.pointId = val as number
    const point = pointOptions.find(p => p.id === val)
    updated.pointName = point?.point_name || ''
  } else if (field === 'operator') {
    updated.operator = val as ConditionItem['operator']
  } else if (field === 'threshold') {
    updated.threshold = val as number | undefined
  }
  const newChildren = [...group.children]
  newChildren[idx] = updated
  return { ...group, children: newChildren }
}

function updateLogic(group: ConditionGroup, logic: 'AND' | 'OR'): ConditionGroup {
  return { ...group, logic }
}

// ── 可测试的条件组编辑器组件 ──
const ConditionGroupTestable = defineComponent({
  name: 'ConditionGroupTestable',
  setup() {
    const group = ref<ConditionGroup>({
      id: 'root',
      type: 'group',
      logic: 'AND',
      children: [
        { id: 'c1', type: 'condition', pointId: 1, pointName: '温度A', operator: '>', threshold: 30 },
        { id: 'c2', type: 'condition', pointId: 2, pointName: '湿度B', operator: '<', threshold: 80 },
      ]
    })
    const depth = ref(0)
    const maxDepth = ref(2)
    const pointOptions = ref([
      { id: 1, point_name: '温度A' },
      { id: 2, point_name: '湿度B' },
      { id: 3, point_name: '电压C' },
    ])

    const childCount = computed(() => group.value.children.length)
    const conditionCount = computed(() => group.value.children.filter(c => c.type === 'condition').length)
    const groupCount = computed(() => group.value.children.filter(c => c.type === 'group').length)
    const canAddSubGroup = computed(() => depth.value < maxDepth.value)

    function doAddCondition() { group.value = addConditionToGroup(group.value) }
    function doAddSubGroup() { group.value = addSubGroupToGroup(group.value, depth.value, maxDepth.value) }
    function doRemoveChild(idx: number) { group.value = removeChildFromGroup(group.value, idx) }
    function doUpdateLogic(logic: 'AND' | 'OR') { group.value = updateLogic(group.value, logic) }

    return { group, depth, maxDepth, pointOptions, childCount, conditionCount, groupCount, canAddSubGroup, doAddCondition, doAddSubGroup, doRemoveChild, doUpdateLogic }
  },
  template: `<div class="condition-group-editor">
    <div class="header">
      <span class="logic" data-testid="logic">{{ group.logic }}</span>
      <span class="child-count" data-testid="child-count">{{ childCount }}</span>
      <span class="cond-count" data-testid="cond-count">{{ conditionCount }}</span>
      <span class="group-count" data-testid="group-count">{{ groupCount }}</span>
      <span class="can-add-sub" data-testid="can-add-sub">{{ canAddSubGroup }}</span>
    </div>
    <div class="children">
      <div v-for="(child, idx) in group.children" :key="child.id" :data-testid="'child-' + idx" class="child">
        <span v-if="idx > 0" class="connector">{{ group.logic }}</span>
        <template v-if="child.type === 'condition'">
          <span class="point-name">{{ child.pointName }}</span>
          <span class="operator">{{ child.operator }}</span>
          <span class="threshold">{{ child.threshold ?? '-' }}</span>
        </template>
        <template v-else>
          <span class="sub-group">[子组: {{ child.logic }}]</span>
        </template>
      </div>
      <div v-if="!group.children.length" class="empty" data-testid="empty">点击上方按钮添加条件或子条件组</div>
    </div>
  </div>`
})

describe('复合条件组编辑器组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 渲染 ──
  it('渲染条件组逻辑类型', () => {
    expect(mount(ConditionGroupTestable).find('[data-testid="logic"]').text()).toBe('AND')
  })

  it('渲染子节点数量', () => {
    expect(mount(ConditionGroupTestable).find('[data-testid="child-count"]').text()).toBe('2')
  })

  it('渲染条件节点', () => {
    const w = mount(ConditionGroupTestable)
    expect(w.find('[data-testid="child-0"] .point-name').text()).toBe('温度A')
    expect(w.find('[data-testid="child-0"] .operator').text()).toBe('>')
    expect(w.find('[data-testid="child-0"] .threshold').text()).toBe('30')
  })

  it('渲染逻辑连接符', () => {
    const w = mount(ConditionGroupTestable)
    expect(w.find('[data-testid="child-1"] .connector').text()).toBe('AND')
  })

  // ── 添加条件 ──
  it('添加条件后子节点数增加', async () => {
    const w = mount(ConditionGroupTestable)
    expect(w.vm.childCount).toBe(2)
    w.vm.doAddCondition()
    await w.vm.$nextTick()
    expect(w.vm.childCount).toBe(3)
    expect(w.find('[data-testid="cond-count"]').text()).toBe('3')
  })

  // ── 添加子组 ──
  it('添加子组后组数增加', async () => {
    const w = mount(ConditionGroupTestable)
    expect(w.vm.groupCount).toBe(0)
    w.vm.doAddSubGroup()
    await w.vm.$nextTick()
    expect(w.vm.groupCount).toBe(1)
    expect(w.vm.childCount).toBe(3)
  })

  it('超过最大深度时不能添加子组', () => {
    const w = mount(ConditionGroupTestable)
    w.vm.depth = 2
    w.vm.maxDepth = 2
    const before = w.vm.childCount
    w.vm.doAddSubGroup()
    expect(w.vm.childCount).toBe(before)
  })

  // ── 删除子节点 ──
  it('删除子节点后数量减少', async () => {
    const w = mount(ConditionGroupTestable)
    expect(w.vm.childCount).toBe(2)
    w.vm.doRemoveChild(0)
    await w.vm.$nextTick()
    expect(w.vm.childCount).toBe(1)
    expect(w.find('[data-testid="child-0"] .point-name').text()).toBe('湿度B')
  })

  // ── 切换逻辑 ──
  it('切换逻辑类型', async () => {
    const w = mount(ConditionGroupTestable)
    expect(w.vm.group.logic).toBe('AND')
    w.vm.doUpdateLogic('OR')
    await w.vm.$nextTick()
    expect(w.find('[data-testid="logic"]').text()).toBe('OR')
  })

  // ── 空状态 ──
  it('无子节点时显示空提示', async () => {
    const w = mount(ConditionGroupTestable)
    w.vm.doRemoveChild(1)
    w.vm.doRemoveChild(0)
    await w.vm.$nextTick()
    expect(w.find('[data-testid="empty"]').exists()).toBe(true)
    expect(w.find('[data-testid="empty"]').text()).toContain('添加条件')
  })

  // ── 辅助函数单元测试 ──
  it('updateChildCondition 更新点位', () => {
    const group: ConditionGroup = {
      id: 'g', type: 'group', logic: 'AND',
      children: [{ id: 'c1', type: 'condition', pointId: 1, pointName: '温度A', operator: '>', threshold: 30 }]
    }
    const pts = [{ id: 3, point_name: '电压C' }]
    const updated = updateChildCondition(group, 0, 'pointId', 3, pts)
    const child = updated.children[0] as ConditionItem
    expect(child.pointId).toBe(3)
    expect(child.pointName).toBe('电压C')
  })

  it('updateChildCondition 更新运算符', () => {
    const group: ConditionGroup = {
      id: 'g', type: 'group', logic: 'AND',
      children: [{ id: 'c1', type: 'condition', pointId: 1, pointName: 'P', operator: '>', threshold: 10 }]
    }
    const updated = updateChildCondition(group, 0, 'operator', '<=', [])
    expect((updated.children[0] as ConditionItem).operator).toBe('<=')
  })

  it('updateChildCondition 更新阈值', () => {
    const group: ConditionGroup = {
      id: 'g', type: 'group', logic: 'AND',
      children: [{ id: 'c1', type: 'condition', pointId: 1, pointName: 'P', operator: '>', threshold: 10 }]
    }
    const updated = updateChildCondition(group, 0, 'threshold', 99, [])
    expect((updated.children[0] as ConditionItem).threshold).toBe(99)
  })
})
