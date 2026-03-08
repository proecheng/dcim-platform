<template>
  <div class="diagnosis-reports">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>误诊反馈报告</span>
          <el-button type="primary" @click="handleGenerate">
            <el-icon><Plus /></el-icon>
            生成报告
          </el-button>
        </div>
      </template>

      <!-- 查询表单 -->
      <el-form :inline="true" :model="queryForm" class="query-form">
        <el-form-item label="报告周期">
          <el-date-picker
            v-model="queryForm.periodRange"
            type="monthrange"
            range-separator="至"
            start-placeholder="开始月份"
            end-placeholder="结束月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 报告列表 -->
      <el-table
        v-loading="loading"
        :data="reportList"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="report_period" label="报告周期" width="120" />
        <el-table-column label="准确率" width="100">
          <template #default="{ row }">
            <span v-if="row.summary?.accuracy_rate !== null">
              {{ (row.summary.accuracy_rate * 100).toFixed(1) }}%
            </span>
            <span v-else class="text-muted">N/A</span>
          </template>
        </el-table-column>
        <el-table-column label="误报次数" width="100">
          <template #default="{ row }">
            {{ row.summary?.false_positive_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="漏报次数" width="100">
          <template #default="{ row }">
            {{ row.summary?.false_negative_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="标注覆盖率" width="120">
          <template #default="{ row }">
            {{ (row.summary?.annotation_coverage * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.generated_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="generated_by" label="生成者" width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">
              查看
            </el-button>
            <el-button link type="primary" @click="handleExport(row)">
              导出PDF
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleQuery"
        @current-change="handleQuery"
      />
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      title="报告详情"
      width="80%"
      :close-on-click-modal="false"
    >
      <div v-if="currentReport" class="report-detail">
        <div class="report-meta">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="报告周期">
              {{ currentReport.report_period }}
            </el-descriptions-item>
            <el-descriptions-item label="生成时间">
              {{ formatDateTime(currentReport.generated_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="生成者">
              {{ currentReport.generated_by || '系统' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div class="report-content">
          <div v-html="renderedContent" />
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleExport(currentReport)">
          导出PDF
        </el-button>
      </template>
    </el-dialog>

    <!-- 生成报告对话框 -->
    <el-dialog
      v-model="generateVisible"
      title="生成误诊报告"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="generateForm" label-width="100px">
        <el-form-item label="报告周期">
          <el-date-picker
            v-model="generateForm.period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleConfirmGenerate">
          生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { marked } from 'marked'
import {
  getMisdiagnosisReports,
  getMisdiagnosisReport,
  generateMisdiagnosisReport,
  exportMisdiagnosisReport,
  type SystemReport
} from '@/api/modules/diagnosis'

// 查询表单
const queryForm = reactive({
  periodRange: [] as string[]
})

// 分页
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 报告列表
const loading = ref(false)
const reportList = ref<SystemReport[]>([])

// 报告详情
const detailVisible = ref(false)
const currentReport = ref<SystemReport | null>(null)
const renderedContent = ref('')

// 生成报告
const generateVisible = ref(false)
const generating = ref(false)
const generateForm = reactive({
  period: ''
})

// 加载报告列表
const loadReports = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size
    }

    if (queryForm.periodRange && queryForm.periodRange.length === 2) {
      params.start_period = queryForm.periodRange[0]
      params.end_period = queryForm.periodRange[1]
    }

    const response = await getMisdiagnosisReports(params)
    reportList.value = response.items
    pagination.total = response.total
  } catch (error: any) {
    ElMessage.error(error.message || '加载报告列表失败')
  } finally {
    loading.value = false
  }
}

// 查询
const handleQuery = () => {
  pagination.page = 1
  loadReports()
}

// 重置
const handleReset = () => {
  queryForm.periodRange = []
  pagination.page = 1
  loadReports()
}

// 查看报告
const handleView = async (report: SystemReport) => {
  try {
    const detail = await getMisdiagnosisReport(report.id)
    currentReport.value = detail
    renderedContent.value = marked(detail.content) as string
    detailVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.message || '加载报告详情失败')
  }
}

// 导出PDF
const handleExport = async (report: SystemReport) => {
  try {
    const blob = await exportMisdiagnosisReport(report.id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `误诊报告_${report.report_period}.pdf`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error: any) {
    ElMessage.error(error.message || '导出失败')
  }
}

// 打开生成对话框
const handleGenerate = () => {
  const now = new Date()
  const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  generateForm.period = `${lastMonth.getFullYear()}-${String(lastMonth.getMonth() + 1).padStart(2, '0')}`
  generateVisible.value = true
}

// 确认生成
const handleConfirmGenerate = async () => {
  if (!generateForm.period) {
    ElMessage.warning('请选择报告周期')
    return
  }

  generating.value = true
  try {
    const result = await generateMisdiagnosisReport(generateForm.period)

    if (result.message.includes('已存在')) {
      // 报告已存在，跳转到详情
      await ElMessageBox.confirm(
        '该周期的报告已存在，是否查看现有报告？',
        '提示',
        {
          confirmButtonText: '查看',
          cancelButtonText: '取消',
          type: 'info'
        }
      )
      const report = reportList.value.find(r => r.id === result.report_id)
      if (report) {
        handleView(report)
      } else {
        // 重新加载列表
        await loadReports()
        const newReport = reportList.value.find(r => r.id === result.report_id)
        if (newReport) {
          handleView(newReport)
        }
      }
    } else {
      ElMessage.success('报告生成成功')
      generateVisible.value = false
      loadReports()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '生成报告失败')
    }
  } finally {
    generating.value = false
  }
}

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped lang="scss">
.diagnosis-reports {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .query-form {
    margin-bottom: 20px;
  }

  .text-muted {
    color: #909399;
  }

  .report-detail {
    .report-meta {
      margin-bottom: 20px;
    }

    .report-content {
      max-height: 600px;
      overflow-y: auto;
      padding: 20px;
      background-color: #f5f7fa;
      border-radius: 4px;

      :deep(h1) {
        font-size: 24px;
        margin-bottom: 16px;
      }

      :deep(h2) {
        font-size: 20px;
        margin-top: 24px;
        margin-bottom: 12px;
      }

      :deep(h3) {
        font-size: 16px;
        margin-top: 16px;
        margin-bottom: 8px;
      }

      :deep(table) {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;

        th,
        td {
          border: 1px solid #dcdfe6;
          padding: 8px 12px;
          text-align: left;
        }

        th {
          background-color: #f2f6fc;
          font-weight: bold;
        }
      }

      :deep(ul),
      :deep(ol) {
        padding-left: 24px;
        margin: 12px 0;
      }

      :deep(p) {
        margin: 8px 0;
        line-height: 1.6;
      }

      :deep(code) {
        background-color: #f4f4f5;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
      }
    }
  }
}
</style>
