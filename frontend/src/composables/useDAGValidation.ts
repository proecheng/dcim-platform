/**
 * DAG 校验 Composable
 * Story 25.8: 故障树图形化编辑器
 */

import { ref, type Ref } from 'vue'
import type { DataSet } from 'vis-data'
import type { VisNode, VisEdge, DAGValidationResult, DAGValidationError } from '@/types/fault-tree'
import { nodeColors } from '@/config/vis-network.config'

export function useDAGValidation(
  nodes: Ref<DataSet<VisNode>>,
  edges: Ref<DataSet<VisEdge>>
) {
  const validationErrors = ref<DAGValidationError[]>([])

  /**
   * 执行 DAG 校验
   */
  function validateDAG(): DAGValidationResult {
    const errors: DAGValidationError[] = []
    const allNodes = nodes.value.get()
    const allEdges = edges.value.get()

    // 1. 检测自环
    const selfLoops = allEdges.filter(edge => edge.from === edge.to)
    if (selfLoops.length > 0) {
      errors.push({
        type: 'self_loop',
        message: '检测到自环边',
        edgeIds: selfLoops.map(e => e.id)
      })
    }

    // 2. 检测单一根节点（入度为 0 的节点必须唯一）
    const inDegree = new Map<number | string, number>()
    allNodes.forEach(node => inDegree.set(node.id, 0))
    allEdges.forEach(edge => {
      const currentDegree = inDegree.get(edge.to) || 0
      inDegree.set(edge.to, currentDegree + 1)
    })

    const rootNodes = allNodes.filter(node => (inDegree.get(node.id) || 0) === 0)
    if (rootNodes.length === 0) {
      errors.push({
        type: 'no_root',
        message: '未检测到根节点（入度为 0 的节点）',
        nodeIds: []
      })
    } else if (rootNodes.length > 1) {
      errors.push({
        type: 'multiple_roots',
        message: `检测到多个根节点（${rootNodes.length} 个）`,
        nodeIds: rootNodes.map(n => n.id)
      })
    }

    // 3. 检测环路（使用 Kahn 算法拓扑排序）
    const hasCycle = detectCycle(allNodes, allEdges)
    if (hasCycle) {
      errors.push({
        type: 'cycle',
        message: '检测到环路',
        nodeIds: [] // 环路节点需要更复杂的算法检测，这里简化处理
      })
    }

    // 4. 检测不可达节点（从根节点 BFS，标记所有可达节点）
    if (rootNodes.length === 1) {
      const unreachableNodes = detectUnreachableNodes(rootNodes[0].id, allNodes, allEdges)
      if (unreachableNodes.length > 0) {
        errors.push({
          type: 'unreachable',
          message: `检测到 ${unreachableNodes.length} 个不可达节点`,
          nodeIds: unreachableNodes
        })
      }
    }

    validationErrors.value = errors

    return {
      valid: errors.length === 0,
      errors
    }
  }

  /**
   * 使用 Kahn 算法检测环路
   */
  function detectCycle(allNodes: VisNode[], allEdges: VisEdge[]): boolean {
    // 计算入度
    const inDegree = new Map<number | string, number>()
    const adjList = new Map<number | string, (number | string)[]>()

    allNodes.forEach(node => {
      inDegree.set(node.id, 0)
      adjList.set(node.id, [])
    })

    allEdges.forEach(edge => {
      const currentDegree = inDegree.get(edge.to) || 0
      inDegree.set(edge.to, currentDegree + 1)

      const neighbors = adjList.get(edge.from) || []
      neighbors.push(edge.to)
      adjList.set(edge.from, neighbors)
    })

    // Kahn 算法
    const queue: (number | string)[] = []
    allNodes.forEach(node => {
      if ((inDegree.get(node.id) || 0) === 0) {
        queue.push(node.id)
      }
    })

    let processedCount = 0

    while (queue.length > 0) {
      const current = queue.shift()!
      processedCount++

      const neighbors = adjList.get(current) || []
      neighbors.forEach(neighbor => {
        const degree = (inDegree.get(neighbor) || 0) - 1
        inDegree.set(neighbor, degree)
        if (degree === 0) {
          queue.push(neighbor)
        }
      })
    }

    // 如果处理的节点数少于总节点数，说明存在环路
    return processedCount < allNodes.length
  }

  /**
   * 检测不可达节点（从根节点 BFS）
   */
  function detectUnreachableNodes(
    rootId: number | string,
    allNodes: VisNode[],
    allEdges: VisEdge[]
  ): (number | string)[] {
    // 构建邻接表
    const adjList = new Map<number | string, (number | string)[]>()
    allNodes.forEach(node => adjList.set(node.id, []))
    allEdges.forEach(edge => {
      const neighbors = adjList.get(edge.from) || []
      neighbors.push(edge.to)
      adjList.set(edge.from, neighbors)
    })

    // BFS 标记可达节点
    const reachable = new Set<number | string>()
    const queue: (number | string)[] = [rootId]
    reachable.add(rootId)

    while (queue.length > 0) {
      const current = queue.shift()!
      const neighbors = adjList.get(current) || []

      neighbors.forEach(neighbor => {
        if (!reachable.has(neighbor)) {
          reachable.add(neighbor)
          queue.push(neighbor)
        }
      })
    }

    // 找出不可达节点
    return allNodes
      .filter(node => !reachable.has(node.id))
      .map(node => node.id)
  }

  /**
   * 高亮错误节点和边
   */
  function highlightErrors(errors: DAGValidationError[]) {
    errors.forEach(error => {
      // 高亮节点
      if (error.nodeIds && error.nodeIds.length > 0) {
        const updates = error.nodeIds.map(nodeId => {
          const node = nodes.value.get(nodeId)
          if (node) {
            return {
              ...node,
              color: {
                background: nodeColors.error,
                border: nodeColors.error,
                highlight: {
                  background: nodeColors.error,
                  border: nodeColors.error
                }
              }
            }
          }
          return null
        }).filter(Boolean) as VisNode[]

        if (updates.length > 0) {
          nodes.value.update(updates)
        }
      }

      // 高亮边
      if (error.edgeIds && error.edgeIds.length > 0) {
        const updates = error.edgeIds.map(edgeId => {
          const edge = edges.value.get(edgeId)
          if (edge) {
            return {
              ...edge,
              color: {
                color: nodeColors.error,
                highlight: nodeColors.error
              }
            }
          }
          return null
        }).filter(Boolean) as VisEdge[]

        if (updates.length > 0) {
          edges.value.update(updates)
        }
      }
    })
  }

  /**
   * 清除错误高亮
   */
  function clearHighlights() {
    // 重置所有节点颜色
    const allNodes = nodes.value.get()
    const updates = allNodes.map(node => {
      let color: string
      if (node.nodeType === 'root') {
        color = nodeColors.root
      } else if (node.nodeType === 'gate') {
        color = node.gateType === 'AND' ? nodeColors.andGate : nodeColors.orGate
      } else {
        color = nodeColors.leaf
      }

      return {
        ...node,
        color
      }
    })

    nodes.value.update(updates)

    // 重置所有边颜色
    const allEdges = edges.value.get()
    const edgeUpdates = allEdges.map(edge => ({
      ...edge,
      color: undefined // 使用默认颜色
    }))

    edges.value.update(edgeUpdates)

    validationErrors.value = []
  }

  return {
    validationErrors,
    validateDAG,
    highlightErrors,
    clearHighlights
  }
}
