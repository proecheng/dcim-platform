/**
 * 历史管理 Composable
 * Story 25.8: 故障树图形化编辑器
 */

import { ref, computed, type Ref } from 'vue'
import type { DataSet } from 'vis-data'
import type { VisNode, VisEdge, HistoryState } from '@/types/fault-tree'

const MAX_HISTORY_SIZE = 50

export function useHistoryManager(
  nodes: Ref<DataSet<VisNode>>,
  edges: Ref<DataSet<VisEdge>>
) {
  const history = ref<HistoryState[]>([])
  const currentIndex = ref(-1)

  const canUndo = computed(() => currentIndex.value > 0)
  const canRedo = computed(() => currentIndex.value < history.value.length - 1)

  /**
   * 推入历史栈
   */
  function push() {
    const state: HistoryState = {
      nodes: nodes.value.get().map(n => ({ ...n })),
      edges: edges.value.get().map(e => ({ ...e })),
      timestamp: Date.now()
    }

    // 如果当前不在栈顶，删除后面的历史
    if (currentIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, currentIndex.value + 1)
    }

    // 推入新状态
    history.value.push(state)
    currentIndex.value++

    // 限制历史栈大小
    if (history.value.length > MAX_HISTORY_SIZE) {
      history.value.shift()
      currentIndex.value-- // 调整 currentIndex，因为数组前面移除了一个元素
    }
  }

  /**
   * 撤销
   */
  function undo() {
    if (!canUndo.value) return

    currentIndex.value--
    restoreState(history.value[currentIndex.value])
  }

  /**
   * 重做
   */
  function redo() {
    if (!canRedo.value) return

    currentIndex.value++
    restoreState(history.value[currentIndex.value])
  }

  /**
   * 恢复状态
   */
  function restoreState(state: HistoryState) {
    nodes.value.clear()
    edges.value.clear()
    nodes.value.add(state.nodes)
    edges.value.add(state.edges)
  }

  /**
   * 清空历史
   */
  function clear() {
    history.value = []
    currentIndex.value = -1
  }

  return {
    canUndo,
    canRedo,
    push,
    undo,
    redo,
    clear
  }
}
