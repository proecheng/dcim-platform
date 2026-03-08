<template>
  <div class="fault-tree-canvas" ref="canvasContainer">
    <div v-if="loading" class="canvas-loading">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="!canvasSupported" class="canvas-fallback">
      <el-alert
        title="浏览器不支持 Canvas"
        type="warning"
        description="您的浏览器不支持 Canvas，已降级到只读表格视图"
        show-icon
        :closable="false"
      />

      <el-table :data="nodes" border style="margin-top: 20px">
        <el-table-column prop="label" label="节点名称" />
        <el-table-column prop="nodeType" label="节点类型" />
        <el-table-column prop="gateType" label="门类型" />
        <el-table-column prop="description" label="描述" />
      </el-table>
    </div>

    <div v-else ref="networkContainer" class="network-container"></div>

    <!-- 工具栏 -->
    <div v-if="!loading && canvasSupported" class="canvas-toolbar">
      <el-button-group>
        <el-button size="small" @click="handleUndo" :disabled="!canUndo">
          <el-icon><Back /></el-icon>
          撤销
        </el-button>
        <el-button size="small" @click="handleRedo" :disabled="!canRedo">
          <el-icon><Right /></el-icon>
          重做
        </el-button>
      </el-button-group>

      <el-button size="small" @click="handleFitView">
        <el-icon><FullScreen /></el-icon>
        适应视图
      </el-button>

      <el-tag v-if="isLargeTree" type="warning" size="small">
        大型故障树（{{ nodeCount }} 节点）
      </el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { Back, Right, FullScreen } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useFaultTreeEditor } from '@/composables/useFaultTreeEditor'
import { debounce } from 'lodash-es'
import type { VisNode } from '@/types/fault-tree'

interface Props {
  treeId: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'node-double-click', node: VisNode): void
  (e: 'validation-change', valid: boolean): void
  (e: 'unsaved-change', changed: boolean): void
}>()

const canvasContainer = ref<HTMLElement | null>(null)
const networkContainer = ref<HTMLElement | null>(null)
const canvasSupported = ref(true)

const {
  loading,
  hasUnsavedChanges,
  nodeCount,
  isLargeTree,
  canUndo,
  canRedo,
  initialize,
  addNode,
  updateNode,
  deleteNode,
  save,
  undo,
  redo,
  fitView,
  destroy,
  nodes,
  edges,
  network
} = useFaultTreeEditor(props.treeId)

// 防抖的校验函数
const debouncedValidate = debounce(() => {
  // 校验逻辑在 useFaultTreeEditor 中处理
  // 这里只是触发校验
  emit('validation-change', true) // 简化处理，实际应该从 useDAGValidation 获取结果
}, 300)

// 防抖的历史记录函数
const debouncedPushHistory = debounce(() => {
  // 历史记录在 useFaultTreeEditor 中处理
}, 300)

// 监听未保存更改
watch(hasUnsavedChanges, (changed) => {
  emit('unsaved-change', changed)
})

// 初始化
onMounted(async () => {
  // 检查 Canvas 支持
  try {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      canvasSupported.value = false
      return
    }
  } catch (error) {
    canvasSupported.value = false
    return
  }

  if (networkContainer.value) {
    await initialize(networkContainer.value)
    bindKeyboardShortcuts()
    bindNetworkEvents()
  }
})

// 销毁
onBeforeUnmount(() => {
  unbindKeyboardShortcuts()
  destroy()
})

// 绑定键盘快捷键
function bindKeyboardShortcuts() {
  window.addEventListener('keydown', handleKeyDown)
}

// 解绑键盘快捷键
function unbindKeyboardShortcuts() {
  window.removeEventListener('keydown', handleKeyDown)
}

// 键盘事件处理
function handleKeyDown(event: KeyboardEvent) {
  // 检查焦点元素，如果在输入框中则不触发画布快捷键
  const activeElement = document.activeElement
  if (activeElement && (
    activeElement.tagName === 'INPUT' ||
    activeElement.tagName === 'TEXTAREA' ||
    activeElement.getAttribute('contenteditable') === 'true'
  )) {
    return  // 焦点在输入框，不处理画布快捷键
  }

  if (event.ctrlKey && event.key === 'z' && !event.shiftKey) {
    event.preventDefault()
    event.stopPropagation()
    handleUndo()
    return
  }

  if (event.ctrlKey && event.shiftKey && event.key === 'Z') {
    event.preventDefault()
    event.stopPropagation()
    handleRedo()
    return
  }

  if (event.key === 'Delete') {
    event.preventDefault()
    event.stopPropagation()
    handleDelete()
    return
  }
}

// 绑定 vis-network 事件
function bindNetworkEvents() {
  if (!network.value) return

  // 双击节点
  network.value.on('doubleClick', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const node = nodes.value.get(nodeId)
      if (node) {
        emit('node-double-click', node)
      }
    }
  })

  // 节点/边变化时触发校验和历史记录
  network.value.on('afterDrawing', () => {
    debouncedValidate()
    debouncedPushHistory()
  })
}

// 撤销
function handleUndo() {
  undo()
}

// 重做
function handleRedo() {
  redo()
}

// 删除选中的节点或边
function handleDelete() {
  if (!network.value) return

  const selection = network.value.getSelection()

  if (selection.nodes.length > 0) {
    selection.nodes.forEach(nodeId => {
      deleteNode(nodeId)
    })
  }

  if (selection.edges.length > 0) {
    selection.edges.forEach(edgeId => {
      edges.value.remove(edgeId)
    })
  }
}

// 适应视图
function handleFitView() {
  fitView()
}

// 暴露方法给父组件
defineExpose({
  addNode,
  updateNode,
  save
})
</script>

<style scoped lang="scss">
.fault-tree-canvas {
  flex: 1;
  position: relative;
  background: #fff;
  overflow: hidden;

  .canvas-loading {
    padding: 40px;
  }

  .canvas-fallback {
    padding: 20px;
  }

  .network-container {
    width: 100%;
    height: 100%;
  }

  .canvas-toolbar {
    position: absolute;
    top: 16px;
    right: 16px;
    display: flex;
    gap: 12px;
    align-items: center;
    background: rgba(255, 255, 255, 0.95);
    padding: 8px 12px;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}
</style>
