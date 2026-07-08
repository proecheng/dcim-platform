<template>
  <div class="fault-tree-editor">
    <div class="editor-header">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/strategy/diagnosis/rules' }">故障树管理</el-breadcrumb-item>
        <el-breadcrumb-item>{{ faultTree?.name || loadError?.title || '加载中...' }}</el-breadcrumb-item>
      </el-breadcrumb>

      <div v-if="!loadError" class="header-actions">
        <el-button @click="handleSave" type="primary" :loading="saving" :disabled="loading || !canSave">
          保存
        </el-button>
        <el-button @click="handleCancel">取消</el-button>
      </div>
    </div>

    <el-result
      v-if="loadError"
      class="editor-result"
      icon="warning"
      :title="loadError.title"
      :sub-title="loadError.description"
    >
      <template #extra>
        <el-button type="primary" @click="router.push('/strategy/diagnosis/rules')">返回诊断规则</el-button>
        <el-button @click="loadFaultTree">重试</el-button>
      </template>
    </el-result>

    <div v-else-if="loading" class="editor-loading">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-else class="editor-content">
      <!-- 左侧工具面板 -->
      <NodeToolbar @add-node="handleAddNode" />

      <!-- 中间画布区域 -->
      <FaultTreeCanvas
        ref="canvasRef"
        :tree-id="treeId"
        @node-double-click="handleNodeDoubleClick"
        @validation-change="handleValidationChange"
        @unsaved-change="handleUnsavedChange"
      />

      <!-- 右侧属性面板 -->
      <NodePropertiesPanel
        v-model:visible="propertiesPanelVisible"
        :node="selectedNode"
        @save="handleNodePropertiesSave"
        @close="propertiesPanelVisible = false"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import NodeToolbar from '@/components/diagnosis/NodeToolbar.vue'
import FaultTreeCanvas from '@/components/diagnosis/FaultTreeCanvas.vue'
import NodePropertiesPanel from '@/components/diagnosis/NodePropertiesPanel.vue'
import { getFaultTree } from '@/api/modules/fault-tree'
import type { FaultTree, VisNode } from '@/types/fault-tree'

const route = useRoute()
const router = useRouter()

const treeId = computed(() => Number(route.params.id))
const faultTree = ref<FaultTree | null>(null)
const canvasRef = ref<InstanceType<typeof FaultTreeCanvas> | null>(null)
const propertiesPanelVisible = ref(false)
const selectedNode = ref<VisNode | null>(null)
const canSave = ref(true)
const saving = ref(false)
const hasUnsavedChanges = ref(false)
const loading = ref(true)
const loadError = ref<{ title: string; description: string } | null>(null)

// 加载故障树数据
async function loadFaultTree() {
  const id = treeId.value
  if (!Number.isInteger(id) || id <= 0) {
    faultTree.value = null
    canSave.value = false
    loadError.value = {
      title: '故障树 ID 无效',
      description: '当前地址中的故障树 ID 不合法，请返回诊断规则重新选择。'
    }
    return
  }

  loading.value = true
  loadError.value = null
  try {
    const response = await getFaultTree(id, { silentError: true })
    faultTree.value = response
    canSave.value = true
  } catch (error: any) {
    faultTree.value = null
    canSave.value = false
    const status = error?.response?.status
    loadError.value = status === 404
      ? {
          title: '未找到故障树',
          description: `故障树 ${id} 不存在，可能已被删除或您当前无权查看。`
        }
      : {
          title: '故障树加载失败',
          description: '暂时无法获取故障树数据，请稍后重试。'
        }
  } finally {
    loading.value = false
  }
}

// 添加节点
function handleAddNode(nodeType: string) {
  canvasRef.value?.addNode(nodeType)
}

// 双击节点打开属性面板
function handleNodeDoubleClick(node: VisNode) {
  selectedNode.value = node
  propertiesPanelVisible.value = true
}

// 保存节点属性
function handleNodePropertiesSave(updatedNode: VisNode) {
  canvasRef.value?.updateNode(updatedNode)
  propertiesPanelVisible.value = false
}

// 校验状态变化
function handleValidationChange(valid: boolean) {
  canSave.value = valid
}

// 未保存更改标记
function handleUnsavedChange(changed: boolean) {
  hasUnsavedChanges.value = changed
}

// 保存故障树
async function handleSave() {
  if (!canvasRef.value) return

  saving.value = true
  try {
    await canvasRef.value.save()
    hasUnsavedChanges.value = false
    ElMessage.success('保存成功')
  } catch (error: any) {
    if (error.message === 'VERSION_CONFLICT') {
      ElMessage.error('故障树已被其他用户修改，请刷新后重试')
    } else {
      ElMessage.error('保存失败')
    }
    console.error(error)
  } finally {
    saving.value = false
  }
}

// 取消编辑
function handleCancel() {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('您有未保存的更改，确定要离开吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      router.push('/strategy/diagnosis/rules')
    }).catch(() => {
      // 用户取消
    })
  } else {
    router.push('/strategy/diagnosis/rules')
  }
}

// 路由守卫 - 离开前检查未保存更改
onBeforeRouteLeave((to, from, next) => {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('您有未保存的更改，确定要离开吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      next()
    }).catch(() => {
      next(false)
    })
  } else {
    next()
  }
})

// beforeunload 事件 - 浏览器关闭/刷新前提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  loadFaultTree()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped lang="scss">
.fault-tree-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: #fff;
    border-bottom: 1px solid #e4e7ed;

    .header-actions {
      display: flex;
      gap: 12px;
    }
  }

  .editor-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .editor-loading,
  .editor-result {
    flex: 1;
    background: #fff;
  }

  .editor-loading {
    padding: 40px;
  }
}
</style>
