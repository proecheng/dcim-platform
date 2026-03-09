<template>
  <div class="node-properties-panel">
    <el-drawer
      :model-value="visible"
      @update:model-value="(val: boolean) => emit('update:visible', val)"
      title="节点属性"
      direction="rtl"
      size="400px"
      @close="handleClose"
    >
      <el-form
        v-if="localNode"
        ref="formRef"
        :model="localNode"
        :rules="rules"
        label-width="100px"
        label-position="top"
      >
        <!-- 节点名称 -->
        <el-form-item label="节点名称" prop="label" required>
          <el-input
            v-model="localNode.label"
            placeholder="请输入节点名称"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <!-- 节点描述 -->
        <el-form-item label="节点描述" prop="description">
          <el-input
            v-model="localNode.description"
            type="textarea"
            :rows="3"
            placeholder="请输入节点描述"
            maxlength="1000"
            show-word-limit
          />
        </el-form-item>

        <!-- 门类型（仅中间节点） -->
        <el-form-item
          v-if="localNode.nodeType === 'gate'"
          label="门类型"
          prop="gateType"
          required
        >
          <el-select v-model="localNode.gateType" placeholder="请选择门类型">
            <el-option label="AND 门" value="AND" />
            <el-option label="OR 门" value="OR" />
          </el-select>
        </el-form-item>

        <!-- 先验概率（仅叶节点） -->
        <el-form-item
          v-if="localNode.nodeType === 'leaf'"
          label="先验概率"
          prop="priorProbability"
          required
        >
          <el-input-number
            v-model="localNode.priorProbability"
            :min="0"
            :max="1"
            :step="0.01"
            :precision="2"
            placeholder="0.00 - 1.00"
          />
        </el-form-item>

        <!-- 关联点位（仅叶节点） -->
        <el-form-item
          v-if="localNode.nodeType === 'leaf'"
          label="关联点位"
          prop="evidencePointId"
          required
        >
          <el-select
            v-model="localNode.evidencePointId"
            filterable
            remote
            reserve-keyword
            placeholder="请输入点位名称或编码搜索"
            :remote-method="handleSearchPoints"
            :loading="pointsLoading"
          >
            <el-option
              v-for="point in pointOptions"
              :key="point.id"
              :label="`${point.name} (${point.code})`"
              :value="point.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="handleClose">取消</el-button>
          <el-button type="primary" @click="handleSave">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { searchPoints } from '@/api/modules/fault-tree'
import type { VisNode, PointInfo } from '@/types/fault-tree'

interface Props {
  visible: boolean
  node: VisNode | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'save', node: VisNode): void
  (e: 'close'): void
}>()

const formRef = ref<FormInstance>()
const localNode = ref<VisNode | null>(null)
const pointOptions = ref<PointInfo[]>([])
const pointsLoading = ref(false)

// 表单验证规则
const rules = computed<FormRules>(() => ({
  label: [
    { required: true, message: '请输入节点名称', trigger: 'blur' },
    { max: 200, message: '节点名称最多 200 个字符', trigger: 'blur' }
  ],
  description: [
    { max: 1000, message: '节点描述最多 1000 个字符', trigger: 'blur' }
  ],
  gateType: [
    { required: true, message: '请选择门类型', trigger: 'change' }
  ],
  priorProbability: [
    { required: true, message: '请输入先验概率', trigger: 'blur' },
    { type: 'number', min: 0, max: 1, message: '先验概率范围为 0.0 - 1.0', trigger: 'blur' }
  ],
  evidencePointId: [
    { required: true, message: '请选择关联点位', trigger: 'change' }
  ]
}))

// 监听 node 变化，初始化本地副本
watch(() => props.node, (newNode) => {
  if (newNode) {
    localNode.value = { ...newNode }
    // 如果是叶节点且已有关联点位，加载点位信息
    if (newNode.nodeType === 'leaf' && newNode.evidencePointId) {
      loadPointInfo(newNode.evidencePointId)
    }
  }
}, { immediate: true })

// 加载点位信息
async function loadPointInfo(pointId: number) {
  try {
    pointsLoading.value = true
    const response = await searchPoints(String(pointId), 1)
    if (response.data.items.length > 0) {
      pointOptions.value = response.data.items
    }
  } catch (error) {
    console.error('加载点位信息失败', error)
  } finally {
    pointsLoading.value = false
  }
}

// 搜索点位
async function handleSearchPoints(query: string) {
  if (!query) {
    pointOptions.value = []
    return
  }

  try {
    pointsLoading.value = true
    const response = await searchPoints(query, 50)
    pointOptions.value = response.data.items
  } catch (error) {
    console.error('搜索点位失败', error)
    pointOptions.value = []
  } finally {
    pointsLoading.value = false
  }
}

// 保存节点属性
async function handleSave() {
  if (!formRef.value || !localNode.value) return

  try {
    await formRef.value.validate()
    emit('save', localNode.value)
    emit('update:visible', false)
  } catch (error) {
    console.error('表单验证失败', error)
  }
}

// 关闭面板
function handleClose() {
  emit('update:visible', false)
  emit('close')
}
</script>

<style scoped lang="scss">
.node-properties-panel {
  .drawer-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}
</style>
