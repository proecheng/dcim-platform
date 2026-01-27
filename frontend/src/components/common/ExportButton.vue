<template>
  <el-dropdown
    v-if="showDropdown"
    trigger="click"
    @command="handleCommand"
  >
    <el-button :type="type" :icon="Download" :loading="loading">
      {{ text }}
      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="format in formats"
          :key="format.value"
          :command="format.value"
        >
          <el-icon><component :is="format.icon" /></el-icon>
          {{ format.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-button
    v-else
    :type="type"
    :icon="Download"
    :loading="loading"
    @click="() => handleExport()"
  >
    {{ text }}
  </el-button>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Download, ArrowDown, Document, Grid, Printer, DataLine } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  text?: string
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'default'
  showDropdown?: boolean
  defaultFormat?: 'excel' | 'csv' | 'pdf' | 'json'
  enabledFormats?: ('excel' | 'csv' | 'pdf' | 'json')[]
  exportFn?: (format: string) => Promise<Blob | void>
  fileName?: string
}

const props = withDefaults(defineProps<Props>(), {
  text: '导出',
  type: 'default',
  showDropdown: true,
  defaultFormat: 'excel',
  enabledFormats: () => ['excel', 'csv', 'pdf', 'json'],
  fileName: 'export'
})

const emit = defineEmits<{
  (e: 'export', format: string): void
}>()

const loading = ref(false)

const formatConfigs = {
  excel: { label: 'Excel', icon: Grid, ext: '.xlsx', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  csv: { label: 'CSV', icon: Document, ext: '.csv', mime: 'text/csv' },
  pdf: { label: 'PDF', icon: Printer, ext: '.pdf', mime: 'application/pdf' },
  json: { label: 'JSON', icon: DataLine, ext: '.json', mime: 'application/json' }
}

const formats = computed(() => {
  return props.enabledFormats.map(format => ({
    value: format,
    ...formatConfigs[format]
  }))
})

const downloadFile = (blob: Blob, format: string) => {
  const config = formatConfigs[format as keyof typeof formatConfigs]
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${props.fileName}_${new Date().toISOString().slice(0, 10)}${config.ext}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const handleExport = async (format?: string) => {
  const exportFormat = format || props.defaultFormat

  if (props.exportFn) {
    loading.value = true
    try {
      const result = await props.exportFn(exportFormat)
      if (result instanceof Blob) {
        downloadFile(result, exportFormat)
        ElMessage.success('导出成功')
      }
    } catch (error) {
      console.error('导出失败:', error)
      ElMessage.error('导出失败')
    } finally {
      loading.value = false
    }
  } else {
    emit('export', exportFormat)
  }
}

const handleCommand = (format: string) => {
  handleExport(format)
}
</script>

<style lang="scss" scoped>
</style>
