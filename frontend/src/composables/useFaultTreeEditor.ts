/**
 * 故障树编辑器 Composable
 * Story 25.8: 故障树图形化编辑器
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { DataSet, Network } from 'vis-network/standalone'
import type { Data, Options, Node, Edge } from 'vis-network'
import { nanoid } from 'nanoid'
import { debounce } from 'lodash-es'
import { ElMessage } from 'element-plus'
import { getFaultTree, createFaultTreeVersion } from '@/api/modules/fault-tree'
import type {
  FaultTree,
  FaultTreeNode,
  FaultTreeEdge,
  VisNode,
  VisEdge,
  NodeType,
  GateType,
  SaveFaultTreePayload
} from '@/types/fault-tree'
import {
  defaultNetworkOptions,
  smallTreeOptions,
  largeTreeOptions,
  nodeColors,
  nodeShapes
} from '@/config/vis-network.config'
import { useDAGValidation } from './useDAGValidation'
import { useHistoryManager } from './useHistoryManager'

export function useFaultTreeEditor(treeId: number) {
  // vis-network 实例
  const network = ref<Network | null>(null)
  const container = ref<HTMLElement | null>(null)

  // 数据集
  const nodes = ref<DataSet<VisNode>>(new DataSet([]))
  const edges = ref<DataSet<VisEdge>>(new DataSet([]))

  // 故障树数据
  const faultTree = ref<FaultTree | null>(null)
  const loadedUpdatedAt = ref<string>('')

  // 状态
  const loading = ref(false)
  const hasUnsavedChanges = ref(false)
  const canSave = ref(true)

  // DAG 校验
  const { validateDAG, highlightErrors, clearHighlights } = useDAGValidation(nodes, edges)

  // 历史管理
  const { push: pushHistory, undo, redo, canUndo, canRedo, clear: clearHistory } = useHistoryManager(nodes, edges)

  // 防抖的校验和历史记录函数
  const debouncedValidate = debounce(() => {
    const validationResult = validateDAG()
    if (!validationResult.valid) {
      highlightErrors(validationResult.errors)
      canSave.value = false
    } else {
      clearHighlights()
      canSave.value = true
    }
  }, 300)

  const debouncedPushHistory = debounce(() => {
    pushHistory()
  }, 300)

  // 计算属性
  const nodeCount = computed(() => nodes.value.length)
  const isLargeTree = computed(() => nodeCount.value > 100)

  /**
   * 初始化编辑器
   */
  async function initialize(containerElement: HTMLElement) {
    container.value = containerElement

    try {
      loading.value = true

      // 加载故障树数据
      const response = await getFaultTree(treeId)
      faultTree.value = response.data
      loadedUpdatedAt.value = response.data.updated_at

      // 如果节点数 > 100，显示详细进度
      if (response.data.nodes.length > 100) {
        ElMessage.info(`正在加载 ${response.data.nodes.length} 个节点...`)
      }

      // 转换数据格式
      const visNodes = toVisNodes(response.data.nodes)
      const visEdges = toVisEdges(response.data.edges)

      nodes.value.clear()
      edges.value.clear()
      nodes.value.add(visNodes)
      edges.value.add(visEdges)

      // 创建 vis-network 实例
      const data: Data = {
        nodes: nodes.value,
        edges: edges.value
      }

      const options: Options = isLargeTree.value ? largeTreeOptions : smallTreeOptions

      network.value = new Network(containerElement, data, options)

      // 绑定事件
      bindEvents()

      // 初始化历史栈
      pushHistory()
    } catch (error) {
      console.error('初始化编辑器失败', error)
      ElMessage.error('加载故障树失败')
    } finally {
      loading.value = false
    }
  }

  /**
   * 将后端节点格式转换为 vis-network 格式
   */
  function toVisNodes(backendNodes: FaultTreeNode[]): VisNode[] {
    return backendNodes.map(node => {
      const visNode: VisNode = {
        id: node.id,
        label: node.name,
        title: node.description || node.name,
        nodeType: node.node_type,
        description: node.description,
        x: node.position_x,
        y: node.position_y,
        // 如果有保存的位置，固定节点防止自动布局移动
        fixed: node.position_x !== null && node.position_x !== undefined &&
               node.position_y !== null && node.position_y !== undefined
      }

      // 设置颜色和形状
      if (node.node_type === 'root') {
        visNode.color = nodeColors.root
        visNode.shape = nodeShapes.root
      } else if (node.node_type === 'gate') {
        visNode.gateType = node.gate_type
        visNode.color = node.gate_type === 'AND' ? nodeColors.andGate : nodeColors.orGate
        visNode.shape = nodeShapes.gate
      } else if (node.node_type === 'leaf') {
        visNode.priorProbability = node.prior_probability
        visNode.evidencePointId = node.evidence_point_id
        visNode.color = nodeColors.leaf
        visNode.shape = nodeShapes.leaf
      }

      return visNode
    })
  }

  /**
   * 将后端边格式转换为 vis-network 格式
   */
  function toVisEdges(backendEdges: FaultTreeEdge[]): VisEdge[] {
    return backendEdges.map(edge => ({
      id: edge.id,
      from: edge.from_node_id,
      to: edge.to_node_id,
      arrows: 'to'
    }))
  }

  /**
   * 将 vis-network 格式转换为后端节点格式
   */
  function fromVisNodes(visNodes: VisNode[]): SaveFaultTreePayload['nodes'] {
    return visNodes.map(node => {
      const backendNode: SaveFaultTreePayload['nodes'][0] = {
        node_type: node.nodeType,
        name: node.label,
        description: node.description,
        position_x: node.x,
        position_y: node.y
      }

      // 如果是真实 ID（数字），保留
      if (typeof node.id === 'number') {
        backendNode.id = node.id
      }

      if (node.nodeType === 'gate') {
        backendNode.gate_type = node.gateType
      } else if (node.nodeType === 'leaf') {
        backendNode.prior_probability = node.priorProbability
        backendNode.evidence_point_id = node.evidencePointId
      }

      return backendNode
    })
  }

  /**
   * 将 vis-network 格式转换为后端边格式
   */
  function fromVisEdges(visEdges: VisEdge[], visNodes: VisNode[]): SaveFaultTreePayload['edges'] {
    // 创建临时 ID 到数组索引的映射
    const tempIdToIndex = new Map<string, number>()
    visNodes.forEach((node, index) => {
      if (typeof node.id === 'string' && node.id.startsWith('temp_')) {
        tempIdToIndex.set(node.id, index)
      }
    })

    return visEdges.map(edge => {
      const backendEdge: SaveFaultTreePayload['edges'][0] = {
        from_node_id: 0,
        to_node_id: 0
      }

      // 处理 from_node_id
      if (typeof edge.from === 'number') {
        backendEdge.from_node_id = edge.from
      } else if (typeof edge.from === 'string' && edge.from.startsWith('temp_')) {
        // 临时 ID，使用数组索引
        const index = tempIdToIndex.get(edge.from)
        if (index !== undefined) {
          backendEdge.from_node_id = index
        }
      }

      // 处理 to_node_id
      if (typeof edge.to === 'number') {
        backendEdge.to_node_id = edge.to
      } else if (typeof edge.to === 'string' && edge.to.startsWith('temp_')) {
        // 临时 ID，使用数组索引
        const index = tempIdToIndex.get(edge.to)
        if (index !== undefined) {
          backendEdge.to_node_id = index
        }
      }

      if (typeof edge.id === 'number') {
        backendEdge.id = edge.id
      }

      return backendEdge
    })
  }

  /**
   * 生成临时 ID
   */
  function generateTempId(): string {
    // 优先使用 crypto.randomUUID()（现代浏览器支持）
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return `temp_${crypto.randomUUID()}`
    }
    // 降级方案：使用 nanoid
    return `temp_${nanoid()}`
  }

  /**
   * 添加节点
   */
  function addNode(nodeType: string) {
    const tempId = generateTempId()

    // 检查是否已有根节点
    const existingNodes = nodes.value.get()
    const hasRoot = existingNodes.some(n => n.nodeType === 'root')

    // 如果画布为空，第一个节点自动设为根节点
    const actualNodeType: NodeType = existingNodes.length === 0 ? 'root' : (nodeType === 'root' ? 'root' : 'gate')

    // 如果已有根节点且尝试创建第二个根节点，阻止
    if (hasRoot && actualNodeType === 'root') {
      ElMessage.warning('已存在根节点，无法创建第二个根节点')
      return
    }

    const newNode: VisNode = {
      id: tempId,
      label: nodeType === 'AND' ? 'AND 门' : nodeType === 'OR' ? 'OR 门' : nodeType === 'leaf' ? '叶节点' : '根节点',
      nodeType: actualNodeType,
      gateType: nodeType === 'AND' ? 'AND' : nodeType === 'OR' ? 'OR' : undefined,
      priorProbability: nodeType === 'leaf' ? 0.5 : undefined,
      color: actualNodeType === 'root' ? nodeColors.root :
             nodeType === 'AND' ? nodeColors.andGate :
             nodeType === 'OR' ? nodeColors.orGate :
             nodeColors.leaf,
      shape: actualNodeType === 'root' ? nodeShapes.root :
             actualNodeType === 'gate' ? nodeShapes.gate :
             nodeShapes.leaf
    }

    nodes.value.add(newNode)
    hasUnsavedChanges.value = true
    debouncedValidate()
    debouncedPushHistory()
  }

  /**
   * 更新节点
   */
  function updateNode(updatedNode: VisNode) {
    nodes.value.update(updatedNode)
    hasUnsavedChanges.value = true
    debouncedValidate()
    debouncedPushHistory()
  }

  /**
   * 删除节点
   */
  function deleteNode(nodeId: number | string) {
    // 检查是否为根节点
    const node = nodes.value.get(nodeId)
    if (node && node.nodeType === 'root') {
      // 如果只有根节点一个节点，允许删除
      const allNodes = nodes.value.get()
      if (allNodes.length === 1) {
        nodes.value.remove(nodeId)
        hasUnsavedChanges.value = true
        pushHistory()
        return
      }

      // 如果还有其他节点，不允许删除根节点
      ElMessage.warning(`根节点"${node.label}"不能删除，请先删除其他节点`)
      return
    }

    // 删除节点及相关边
    nodes.value.remove(nodeId)
    const relatedEdges = edges.value.get({
      filter: edge => edge.from === nodeId || edge.to === nodeId
    })
    edges.value.remove(relatedEdges.map(e => e.id))

    hasUnsavedChanges.value = true
    debouncedValidate()
    debouncedPushHistory()
  }

  /**
   * 添加边
   */
  function addEdge(fromId: number | string, toId: number | string) {
    // 检查自环
    if (fromId === toId) {
      ElMessage.warning('不能创建自环边')
      return
    }

    const tempId = generateTempId()
    const newEdge: VisEdge = {
      id: tempId,
      from: fromId,
      to: toId,
      arrows: 'to'
    }

    edges.value.add(newEdge)
    hasUnsavedChanges.value = true
    debouncedValidate()
    debouncedPushHistory()
  }

  /**
   * 删除边
   */
  function deleteEdge(edgeId: number | string) {
    edges.value.remove(edgeId)
    hasUnsavedChanges.value = true
    debouncedValidate()
    debouncedPushHistory()
  }

  /**
   * 保存故障树
   */
  async function save() {
    // 执行 DAG 校验
    const validationResult = validateDAG()
    if (!validationResult.valid) {
      highlightErrors(validationResult.errors)
      ElMessage.error('故障树结构不合法，请修复错误后再保存')
      throw new Error('VALIDATION_FAILED')
    }

    clearHighlights()

    // 准备保存数据
    const visNodes = nodes.value.get()
    const payload: SaveFaultTreePayload = {
      name: faultTree.value!.name,
      description: faultTree.value!.description,
      nodes: fromVisNodes(visNodes),
      edges: fromVisEdges(edges.value.get(), visNodes)
    }

    try {
      // 先检查版本冲突（保存前）
      const currentTreeResponse = await getFaultTree(treeId)
      if (currentTreeResponse.data.updated_at !== loadedUpdatedAt.value) {
        ElMessage.error('故障树已被其他用户修改，请刷新页面后重试')
        throw new Error('VERSION_CONFLICT')
      }

      const response = await createFaultTreeVersion(treeId, payload)

      // 更新 loadedUpdatedAt 为新版本的时间戳
      loadedUpdatedAt.value = response.data.updated_at

      // 映射临时 ID 到真实 ID
      await mapTempIdsToRealIds(response.data)

      hasUnsavedChanges.value = false
      ElMessage.success('保存成功')
    } catch (error: any) {
      if (error.message === 'VERSION_CONFLICT') {
        throw error
      }
      console.error('保存故障树失败', error)
      throw error
    }
  }

  /**
   * 映射临时 ID 到真实 ID
   */
  async function mapTempIdsToRealIds(savedTree: FaultTree) {
    // 记录临时 ID 到索引的映射
    const tempIdMap = new Map<string, number>()
    const currentNodes = nodes.value.get()

    currentNodes.forEach((node, index) => {
      if (typeof node.id === 'string' && node.id.startsWith('temp_')) {
        tempIdMap.set(node.id, index)
      }
    })

    // 更新前端 DataSet 中的节点 ID（使用 remove + add）
    const idMapping = new Map<string | number, number>()
    const nodesToRemove: (string | number)[] = []
    const nodesToAdd: VisNode[] = []

    tempIdMap.forEach((index, tempId) => {
      const realId = savedTree.nodes[index].id
      idMapping.set(tempId, realId)
      const oldNode = nodes.value.get(tempId)
      if (oldNode) {
        nodesToRemove.push(tempId)
        nodesToAdd.push({ ...oldNode, id: realId })
      }
    })

    if (nodesToRemove.length > 0) {
      nodes.value.remove(nodesToRemove)
      nodes.value.add(nodesToAdd)
    }

    // 更新边的端点引用
    const edgesToUpdate: VisEdge[] = []
    edges.value.get().forEach(edge => {
      const newFrom = idMapping.get(edge.from) || edge.from
      const newTo = idMapping.get(edge.to) || edge.to
      if (newFrom !== edge.from || newTo !== edge.to) {
        edgesToUpdate.push({ ...edge, from: newFrom, to: newTo })
      }
    })

    if (edgesToUpdate.length > 0) {
      edges.value.update(edgesToUpdate)
    }
  }

  /**
   * 绑定事件
   */
  function bindEvents() {
    if (!network.value) return

    // 双击节点事件
    network.value.on('doubleClick', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0]
        const node = nodes.value.get(nodeId)
        if (node) {
          // 触发外部事件
          // 由父组件处理
        }
      }
    })

    // 节点拖拽结束事件（保存位置）
    network.value.on('dragEnd', (params) => {
      if (params.nodes.length > 0) {
        const positions = network.value!.getPositions(params.nodes)
        const updates: VisNode[] = []

        params.nodes.forEach(nodeId => {
          const pos = positions[nodeId]
          const node = nodes.value.get(nodeId)
          if (node && pos) {
            updates.push({ ...node, x: pos.x, y: pos.y })
          }
        })

        if (updates.length > 0) {
          nodes.value.update(updates)
          hasUnsavedChanges.value = true
        }
      }
    })
  }

  /**
   * 适应视图
   */
  function fitView() {
    network.value?.fit()
  }

  /**
   * 销毁编辑器
   */
  function destroy() {
    network.value?.destroy()
    network.value = null
  }

  return {
    // 状态
    loading,
    hasUnsavedChanges,
    canSave,
    nodeCount,
    isLargeTree,
    canUndo,
    canRedo,

    // 方法
    initialize,
    addNode,
    updateNode,
    deleteNode,
    addEdge,
    deleteEdge,
    save,
    undo,
    redo,
    fitView,
    destroy,

    // 数据
    nodes,
    edges,
    network
  }
}
