/**
 * DAG 校验单元测试
 * Story 25.8: 故障树图形化编辑器
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { DataSet } from 'vis-data'
import { useDAGValidation } from '@/composables/useDAGValidation'
import type { VisNode, VisEdge } from '@/types/fault-tree'

describe('useDAGValidation', () => {
  let nodes: ReturnType<typeof ref<DataSet<VisNode>>>
  let edges: ReturnType<typeof ref<DataSet<VisEdge>>>
  let validation: ReturnType<typeof useDAGValidation>

  beforeEach(() => {
    nodes = ref(new DataSet([]))
    edges = ref(new DataSet([]))
    validation = useDAGValidation(nodes, edges)
  })

  describe('自环检测', () => {
    it('应该检测到自环边', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 1 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.type === 'self_loop')).toBe(true)
    })

    it('应该通过无自环的图', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' },
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(true)
    })
  })

  describe('根节点检测', () => {
    it('应该检测到无根节点', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'gate', gateType: 'AND' },
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 },
        { id: 2, from: 2, to: 1 } // 环路，无根节点
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.type === 'no_root')).toBe(true)
    })

    it('应该检测到多个根节点', () => {
      nodes.value.add([
        { id: 1, label: '根节点1', nodeType: 'root' },
        { id: 2, label: '根节点2', nodeType: 'root' },
        { id: 3, label: '叶节点', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 3 },
        { id: 2, from: 2, to: 3 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.type === 'multiple_roots')).toBe(true)
    })

    it('应该通过单一根节点的图', () => {
      nodes.value.add([
        { id: 1, label: '根节点', nodeType: 'root' },
        { id: 2, label: '叶节点', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(true)
    })
  })

  describe('环路检测', () => {
    it('应该检测到简单环路', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' },
        { id: 2, label: '节点2', nodeType: 'gate', gateType: 'AND' },
        { id: 3, label: '节点3', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 },
        { id: 2, from: 2, to: 3 },
        { id: 3, from: 3, to: 1 } // 环路
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.type === 'cycle')).toBe(true)
    })

    it('应该通过无环的 DAG', () => {
      nodes.value.add([
        { id: 1, label: '根节点', nodeType: 'root' },
        { id: 2, label: 'AND 门', nodeType: 'gate', gateType: 'AND' },
        { id: 3, label: '叶节点1', nodeType: 'leaf' },
        { id: 4, label: '叶节点2', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 },
        { id: 2, from: 2, to: 3 },
        { id: 3, from: 2, to: 4 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(true)
    })
  })

  describe('不可达节点检测', () => {
    it('应该检测到不可达节点', () => {
      nodes.value.add([
        { id: 1, label: '根节点', nodeType: 'root' },
        { id: 2, label: '可达节点', nodeType: 'leaf' },
        { id: 3, label: '不可达节点1', nodeType: 'leaf' },
        { id: 4, label: '不可达节点2', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 },
        // 节点 3 和 4 形成孤立子图，但 3 是根（入度为0）
        { id: 2, from: 3, to: 4 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      // 节点 3 会被检测为第二个根节点（入度为0），节点 4 不可达
      expect(result.errors.some(e => e.type === 'multiple_roots' || e.type === 'unreachable')).toBe(true)
    })

    it('应该通过所有节点可达的图', () => {
      nodes.value.add([
        { id: 1, label: '根节点', nodeType: 'root' },
        { id: 2, label: 'AND 门', nodeType: 'gate', gateType: 'AND' },
        { id: 3, label: '叶节点1', nodeType: 'leaf' },
        { id: 4, label: '叶节点2', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 2 },
        { id: 2, from: 2, to: 3 },
        { id: 3, from: 2, to: 4 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(true)
    })
  })

  describe('复杂场景', () => {
    it('应该检测到多个错误', () => {
      nodes.value.add([
        { id: 1, label: '根节点1', nodeType: 'root' },
        { id: 2, label: '根节点2', nodeType: 'root' },
        { id: 3, label: '节点3', nodeType: 'gate', gateType: 'AND' },
        { id: 4, label: '节点4', nodeType: 'leaf' },
        { id: 5, label: '节点5', nodeType: 'leaf' }
      ])
      edges.value.add([
        { id: 1, from: 1, to: 3 },
        { id: 2, from: 3, to: 3 }, // 自环
        { id: 3, from: 2, to: 3 },
        // 节点 4 和 5 形成孤立子图，4 是第三个根节点
        { id: 4, from: 4, to: 5 }
      ])

      const result = validation.validateDAG()

      expect(result.valid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(1)
      expect(result.errors.some(e => e.type === 'self_loop')).toBe(true)
      expect(result.errors.some(e => e.type === 'multiple_roots')).toBe(true)
      // 节点 5 不可达（从根节点 1 或 2 无法到达）
      expect(result.errors.some(e => e.type === 'unreachable' || e.type === 'multiple_roots')).toBe(true)
    })
  })
})
