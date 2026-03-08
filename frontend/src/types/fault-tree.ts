/**
 * 故障树类型定义
 * Story 25.8: 故障树图形化编辑器
 */

/**
 * 节点类型
 */
export type NodeType = 'root' | 'gate' | 'leaf'

/**
 * 门类型
 */
export type GateType = 'AND' | 'OR'

/**
 * 故障树节点（后端格式）
 */
export interface FaultTreeNode {
  id: number | string // 支持临时 ID（字符串）和真实 ID（数字）
  tree_id: number
  node_type: NodeType
  gate_type?: GateType
  name: string
  description?: string
  prior_probability?: number
  evidence_point_id?: number
  position_x?: number
  position_y?: number
  created_at?: string
  updated_at?: string
}

/**
 * 故障树边（后端格式）
 */
export interface FaultTreeEdge {
  id: number | string
  tree_id: number
  from_node_id: number | string
  to_node_id: number | string
  created_at?: string
}

/**
 * 故障树完整数据
 */
export interface FaultTree {
  id: number
  name: string
  description?: string
  version: number
  is_active: boolean
  nodes: FaultTreeNode[]
  edges: FaultTreeEdge[]
  created_at: string
  updated_at: string
}

/**
 * vis-network 节点格式
 */
export interface VisNode {
  id: number | string
  label: string
  title?: string // Tooltip
  color?: string | { background: string; border: string; highlight: { background: string; border: string } }
  shape?: string
  font?: { color: string }
  x?: number
  y?: number
  fixed?: boolean | { x: boolean; y: boolean } // 节点是否固定位置
  // 自定义数据
  nodeType: NodeType
  gateType?: GateType
  priorProbability?: number
  evidencePointId?: number
  description?: string
}

/**
 * vis-network 边格式
 */
export interface VisEdge {
  id: number | string
  from: number | string
  to: number | string
  arrows?: string | { to: boolean }
  color?: string | { color: string; highlight: string }
}

/**
 * DAG 校验结果
 */
export interface DAGValidationResult {
  valid: boolean
  errors: DAGValidationError[]
}

/**
 * DAG 校验错误
 */
export interface DAGValidationError {
  type: 'cycle' | 'unreachable' | 'multiple_roots' | 'no_root' | 'self_loop'
  message: string
  nodeIds?: (number | string)[]
  edgeIds?: (number | string)[]
}

/**
 * 操作历史记录
 */
export interface HistoryState {
  nodes: VisNode[]
  edges: VisEdge[]
  timestamp: number
}

/**
 * 点位信息（用于叶节点关联）
 */
export interface PointInfo {
  id: number
  code: string
  name: string
  unit?: string
}

/**
 * 保存故障树的请求体
 */
export interface SaveFaultTreePayload {
  name: string
  description?: string
  nodes: Array<{
    id?: number
    node_type: NodeType
    gate_type?: GateType
    name: string
    description?: string
    prior_probability?: number
    evidence_point_id?: number
    position_x?: number
    position_y?: number
  }>
  edges: Array<{
    id?: number
    from_node_id: number
    to_node_id: number
  }>
}
