/**
 * vis-network 配置文件
 * Story 25.8: 故障树图形化编辑器
 */

import type { Options } from 'vis-network'

/**
 * 默认 vis-network 配置
 */
export const defaultNetworkOptions: Options = {
  // 节点配置
  nodes: {
    shape: 'box',
    margin: 10,
    widthConstraint: {
      minimum: 100,
      maximum: 200
    },
    font: {
      size: 14,
      face: 'Arial'
    },
    borderWidth: 2,
    shadow: true
  },

  // 边配置
  edges: {
    arrows: {
      to: {
        enabled: true,
        scaleFactor: 1
      }
    },
    smooth: {
      enabled: true,
      type: 'cubicBezier',
      roundness: 0.5
    },
    width: 2,
    color: {
      color: '#848484',
      highlight: '#2B7CE9',
      hover: '#2B7CE9'
    }
  },

  // 布局配置 - 分层布局（根节点在顶部）
  layout: {
    hierarchical: {
      enabled: true,
      direction: 'UD', // Up-Down: 从上到下
      sortMethod: 'directed', // 按有向边排序
      nodeSpacing: 150,
      levelSeparation: 200,
      treeSpacing: 200,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true
    }
  },

  // 物理引擎配置 - 默认禁用（大型故障树性能优化）
  physics: {
    enabled: false
  },

  // 交互配置
  interaction: {
    dragNodes: true,
    dragView: true,
    zoomView: true,
    selectable: true,
    selectConnectedEdges: false,
    hover: true,
    hoverConnectedEdges: false,
    keyboard: {
      enabled: false // 禁用 vis-network 内置键盘快捷键，使用自定义快捷键
    },
    navigationButtons: false,
    tooltipDelay: 300
  },

  // 操作配置
  manipulation: {
    enabled: false // 禁用内置编辑模式，使用自定义编辑逻辑
  }
}

/**
 * 小型故障树配置（<= 100 节点）
 * 启用物理引擎以获得更好的视觉效果
 */
export const smallTreeOptions: Options = {
  ...defaultNetworkOptions,
  physics: {
    enabled: true,
    stabilization: {
      enabled: true,
      iterations: 100,
      updateInterval: 25
    },
    barnesHut: {
      gravitationalConstant: -2000,
      centralGravity: 0.3,
      springLength: 150,
      springConstant: 0.04,
      damping: 0.09,
      avoidOverlap: 0.5
    }
  }
}

/**
 * 大型故障树配置（> 100 节点）
 * 禁用物理引擎以提升性能
 */
export const largeTreeOptions: Options = {
  ...defaultNetworkOptions,
  physics: {
    enabled: false
  },
  layout: {
    hierarchical: {
      enabled: true,
      direction: 'UD',
      sortMethod: 'directed',
      nodeSpacing: 120, // 减小间距以适应更多节点
      levelSeparation: 150,
      treeSpacing: 150,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true
    }
  }
}

/**
 * 节点颜色配置
 */
export const nodeColors = {
  root: '#FF6B6B', // 红色 - 根节点
  andGate: '#4ECDC4', // 蓝色 - AND 门
  orGate: '#FFE66D', // 橙色 - OR 门
  leaf: '#95E1D3', // 绿色 - 叶节点
  error: '#FF0000', // 错误高亮
  selected: '#2B7CE9' // 选中状态
}

/**
 * 节点形状配置
 */
export const nodeShapes = {
  root: 'diamond',
  gate: 'box',
  leaf: 'ellipse'
}
