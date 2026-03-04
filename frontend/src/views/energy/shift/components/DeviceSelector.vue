<template>
  <div class="device-selector">
    <el-input
      v-model="searchKeyword"
      placeholder="搜索设备名称或编号"
      clearable
      style="margin-bottom: 16px"
      @input="handleSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>

    <el-table
      ref="tableRef"
      :data="filteredDevices"
      @selection-change="handleSelectionChange"
      border
      max-height="400"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="id" label="设备ID" width="80" />
      <el-table-column prop="device_name" label="设备名称" min-width="180" />
      <el-table-column prop="device_type" label="设备类型" width="100" />
      <el-table-column prop="rated_power" label="额定功率 (kW)" width="130" align="right">
        <template #default="{ row }">
          {{ row.rated_power?.toFixed(1) || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="可转移" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_shiftable ? 'success' : 'info'" size="small">
            {{ row.is_shiftable ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <div class="selection-summary" v-if="selectedDevices.length">
      <span>已选 {{ selectedDevices.length }} 个设备</span>
      <span style="margin-left: 20px">
        总功率: {{ totalPower.toFixed(1) }} kW
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getShiftableDevices } from '@/api/modules/shift'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: number[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
}>()

const tableRef = ref()
const searchKeyword = ref('')
const devices = ref<any[]>([])
const selectedDevices = ref<any[]>([])

const filteredDevices = computed(() => {
  if (!searchKeyword.value) return devices.value
  const keyword = searchKeyword.value.toLowerCase()
  return devices.value.filter(
    (d) =>
      d.device_name?.toLowerCase().includes(keyword) ||
      d.device_code?.toLowerCase().includes(keyword) ||
      String(d.id).includes(keyword)
  )
})

const totalPower = computed(() => {
  return selectedDevices.value.reduce((sum, d) => sum + (d.rated_power || 0), 0)
})

const loadDevices = async () => {
  try {
    const res = await getShiftableDevices()
    devices.value = res.data || []
    // 恢复已选设备
    if (props.modelValue && props.modelValue.length) {
      const selected = devices.value.filter((d) => props.modelValue.includes(d.id))
      selectedDevices.value = selected
      selected.forEach((row) => {
        tableRef.value?.toggleRowSelection(row, true)
      })
    }
  } catch (error: any) {
    ElMessage.error(error.message || '加载设备列表失败')
  }
}

const handleSearch = () => {
  // 搜索时保持选中状态
  if (tableRef.value && selectedDevices.value.length) {
    selectedDevices.value.forEach((row) => {
      tableRef.value.toggleRowSelection(row, true)
    })
  }
}

const handleSelectionChange = (selection: any[]) => {
  selectedDevices.value = selection
  emit('update:modelValue', selection.map((d) => d.id))
}

watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal && newVal.length && devices.value.length) {
      const selected = devices.value.filter((d) => newVal.includes(d.id))
      selectedDevices.value = selected
      selected.forEach((row) => {
        tableRef.value?.toggleRowSelection(row, true)
      })
    }
  }
)

onMounted(() => {
  loadDevices()
})
</script>

<style scoped lang="scss">
.device-selector {
  .selection-summary {
    margin-top: 16px;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 4px;
    font-size: 14px;
    color: #606266;
  }
}
</style>
