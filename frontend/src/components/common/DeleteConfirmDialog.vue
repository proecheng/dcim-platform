<template>
  <el-dialog
    :model-value="visible"
    title="删除确认"
    width="600px"
    @update:model-value="$emit('update:visible', $event)"
    @open="handleOpen"
    append-to-body
    destroy-on-close
  >
    <div v-loading="loading" class="delete-dialog-body">
      <!-- 基本提示 -->
      <div class="delete-header">
        <el-icon class="warning-icon" color="var(--el-color-danger)" :size="24"><WarningFilled /></el-icon>
        <span class="warning-text">
          确定要删除设备 <strong>{{ deviceName }}</strong> 吗？
        </span>
      </div>

      <!-- 错误状态 -->
      <el-alert
        v-if="error"
        title="获取影响分析失败"
        :description="error"
        type="error"
        show-icon
        class="mt-4"
        :closable="false"
      />

      <!-- 影响分析展示 -->
      <div v-else-if="impactData" class="impact-container mt-4">
        <!-- 阻断原因 -->
        <el-alert
          v-if="blockingReasons.length > 0"
          title="无法删除该设备（存在阻断依赖）"
          type="error"
          show-icon
          :closable="false"
          class="mb-3"
        >
          <ul class="reason-list">
            <li v-for="(item, index) in blockingReasons" :key="index">
              {{ item.display_name }} ({{ item.count }} 项)
            </li>
          </ul>
        </el-alert>

        <!-- 级联删除 -->
        <el-alert
          v-if="cascadeDeletes.length > 0"
          title="将同步删除以下级联数据（不可恢复）"
          type="warning"
          show-icon
          :closable="false"
          class="mb-3"
        >
          <ul class="reason-list">
            <li v-for="(item, index) in cascadeDeletes" :key="index">
              {{ item.display_name }} ({{ item.count }} 项)
            </li>
          </ul>
        </el-alert>

        <!-- 解除关联 -->
        <el-alert
          v-if="unbindOperations.length > 0"
          title="将解除以下数据的关联"
          type="warning"
          show-icon
          :closable="false"
          class="mb-3 custom-alert-yellow"
        >
          <ul class="reason-list">
            <li v-for="(item, index) in unbindOperations" :key="index">
              {{ item.display_name }} ({{ item.count }} 项)
            </li>
          </ul>
        </el-alert>

        <!-- 软引用警告 -->
        <el-alert
          v-if="softReferences.length > 0"
          title="以下数据仍有引用记录，建议先处理"
          type="info"
          show-icon
          :closable="false"
          class="mb-3"
        >
          <ul class="reason-list">
            <li v-for="(item, index) in softReferences" :key="index">
              {{ item.display_name }} ({{ item.count }} 项)
            </li>
          </ul>
        </el-alert>

        <div v-if="totalAffected === 0 && !blockingReasons.length" class="safe-delete-notice">
          该设备没有关联数据，可以安全删除。
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog" :disabled="deleting">取消</el-button>
        <el-button 
          type="danger" 
          @click="confirmDelete" 
          :loading="deleting"
          :disabled="loading || canNotDelete || !!error"
        >
          {{ canNotDelete ? '存在阻断依赖' : '确认删除' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface ImpactItem {
  table_name: string
  display_name: string
  count: number
  action: 'block' | 'delete' | 'unlink' | 'warn'
}

interface DeleteImpact {
  device_id?: number
  power_device_id?: number
  device_code: string
  device_name: string
  impacts: ImpactItem[]
  total_affected_records: number
}

const props = defineProps<{
  visible: boolean
  deviceId: number
  deviceName: string
  // 提供一个通用的删除API，可以支持其他设备，不仅仅是 PowerDevice
  deleteApi: (id: number, force?: boolean) => Promise<any>
}>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  'deleted': [id: number]
}>()

const loading = ref(false)
const deleting = ref(false)
const error = ref('')
const impactData = ref<DeleteImpact | null>(null)

// 分类展示数据
const blockingReasons = computed(() => {
  if (!impactData.value) return []
  return impactData.value.impacts.filter(i => i.action === 'block')
})

const cascadeDeletes = computed(() => {
  if (!impactData.value) return []
  return impactData.value.impacts.filter(i => i.action === 'delete')
})

const unbindOperations = computed(() => {
  if (!impactData.value) return []
  return impactData.value.impacts.filter(i => i.action === 'unlink')
})

const softReferences = computed(() => {
  if (!impactData.value) return []
  return impactData.value.impacts.filter(i => i.action === 'warn')
})

const totalAffected = computed(() => {
  return impactData.value?.total_affected_records || 0
})

const canNotDelete = computed(() => {
  return blockingReasons.value.length > 0
})

// 加载影响分析
const loadImpactAnalysis = async () => {
  if (!props.deviceId) return
  
  loading.value = true
  error.value = ''
  impactData.value = null
  
  try {
    // 强制传force=false来获取影响分析
    const res = await props.deleteApi(props.deviceId, false)
    if (res.code === 200 && res.data) {
      impactData.value = res.data
    } else {
      error.value = res.message || '获取分析失败'
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || '请求失败，请检查网络或权限'
  } finally {
    loading.value = false
  }
}

const handleOpen = () => {
  loadImpactAnalysis()
}

const closeDialog = () => {
  emit('update:visible', false)
}

const confirmDelete = async () => {
  if (canNotDelete.value) return
  
  deleting.value = true
  try {
    const res = await props.deleteApi(props.deviceId, true)
    if (res.code === 200) {
      ElMessage.success('设备已成功删除')
      emit('deleted', props.deviceId)
      closeDialog()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err.message || '删除发生错误')
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.delete-dialog-body {
  padding: 0 10px;
}

.delete-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.warning-icon {
  margin-right: 12px;
}

.warning-text {
  font-size: 16px;
  line-height: 1.5;
}

.mt-4 {
  margin-top: 16px;
}

.mb-3 {
  margin-bottom: 12px;
}

.reason-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
  list-style-type: disc;
}

.reason-list li {
  margin-bottom: 4px;
}

.custom-alert-yellow {
  background-color: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}

.safe-delete-notice {
  text-align: center;
  padding: 20px;
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
  border-radius: 4px;
  margin-top: 20px;
}
</style>