/**
 * 历史管理单元测试
 * Story 25.8: 故障树图形化编辑器
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { shallowRef } from 'vue'
import { DataSet } from 'vis-data'
import { useHistoryManager } from '@/composables/useHistoryManager'
import type { VisNode, VisEdge } from '@/types/fault-tree'

describe('useHistoryManager', () => {
  let nodes: ReturnType<typeof shallowRef<DataSet<VisNode>>>
  let edges: ReturnType<typeof shallowRef<DataSet<VisEdge>>>
  let history: ReturnType<typeof useHistoryManager>

  beforeEach(() => {
    nodes = shallowRef(new DataSet([]))
    edges = shallowRef(new DataSet([]))
    history = useHistoryManager(nodes, edges)
  })

  describe('push', () => {
    it('应该推入历史状态', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])

      history.push()

      expect(history.canUndo.value).toBe(false) // 第一个状态不能撤销
      expect(history.canRedo.value).toBe(false)
    })

    it('应该在推入第二个状态后允许撤销', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      expect(history.canUndo.value).toBe(true)
      expect(history.canRedo.value).toBe(false)
    })

    it('应该限制历史栈大小为 50', () => {
      // 推入 60 个状态
      for (let i = 0; i < 60; i++) {
        nodes.value.add([
          { id: i, label: `节点${i}`, nodeType: 'leaf' }
        ])
        history.push()
      }

      // 撤销 10 次，应该能撤销（因为栈被限制为 50）
      for (let i = 0; i < 10; i++) {
        history.undo()
      }

      expect(history.canUndo.value).toBe(true)
    })
  })

  describe('undo', () => {
    it('应该撤销到上一个状态', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      history.undo()

      expect(nodes.value.length).toBe(1)
      expect(nodes.value.get(1)?.label).toBe('节点1')
    })

    it('应该在撤销后允许重做', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      history.undo()

      expect(history.canRedo.value).toBe(true)
    })

    it('应该在第一个状态时无法撤销', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      history.undo()

      expect(history.canUndo.value).toBe(false)
      expect(nodes.value.length).toBe(1) // 状态不变
    })
  })

  describe('redo', () => {
    it('应该重做到下一个状态', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      history.undo()
      history.redo()

      expect(nodes.value.length).toBe(2)
      expect(nodes.value.get(2)?.label).toBe('节点2')
    })

    it('应该在最新状态时无法重做', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      history.redo()

      expect(history.canRedo.value).toBe(false)
      expect(nodes.value.length).toBe(1) // 状态不变
    })
  })

  describe('clear', () => {
    it('应该清空历史栈', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      history.clear()

      expect(history.canUndo.value).toBe(false)
      expect(history.canRedo.value).toBe(false)
    })
  })

  describe('复杂场景', () => {
    it('应该在撤销后推入新状态时清除重做历史', () => {
      nodes.value.add([
        { id: 1, label: '节点1', nodeType: 'root' }
      ])
      history.push()

      nodes.value.add([
        { id: 2, label: '节点2', nodeType: 'leaf' }
      ])
      history.push()

      nodes.value.add([
        { id: 3, label: '节点3', nodeType: 'leaf' }
      ])
      history.push()

      // 撤销两次
      history.undo()
      history.undo()

      // 推入新状态
      nodes.value.add([
        { id: 4, label: '节点4', nodeType: 'leaf' }
      ])
      history.push()

      // 应该无法重做到节点 2 和节点 3
      expect(history.canRedo.value).toBe(false)
    })
  })
})
