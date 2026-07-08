<template>
  <div class="shift-opportunity-detail">
    <el-page-header @back="handleBack" title="返回列表">
      <template #content>
        <span class="page-title">机会详情</span>
      </template>
    </el-page-header>

    <el-card class="detail-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>{{ opportunity.opportunity_name }}</span>
          <el-tag :type="getStatusType(opportunity.status)">
            {{ getStatusLabel(opportunity.status) }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="机会编号">
          {{ opportunity.opportunity_code }}
        </el-descriptions-item>
        <el-descriptions-item label="分析日期">
          {{ opportunity.analysis_date }}
        </el-descriptions-item>
        <el-descriptions-item label="转移方向">
          <el-tag>{{ opportunity.recommended_shift_from }}</el-tag>
          <el-icon style="margin: 0 8px"><Right /></el-icon>
          <el-tag type="success">{{ opportunity.recommended_shift_to }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="推荐功率">
          <span class="highlight-value">{{ opportunity.recommended_shift_power?.toFixed(1) }} kW</span>
        </el-descriptions-item>
        <el-descriptions-item label="预期成本节省">
          <span class="highlight-value success">¥{{ opportunity.predicted_cost_saving?.toFixed(2) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="预期节能量">
          <span class="highlight-value">{{ opportunity.predicted_energy_saving?.toFixed(1) }} kWh</span>
        </el-descriptions-item>
        <el-descriptions-item label="置信度">
          <el-progress
            :percentage="(opportunity.confidence_score || 0) * 100"
            :color="getConfidenceColor(opportunity.confidence_score)"
            :stroke-width="10"
            style="width: 200px"
          />
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="getPriorityType(opportunity.priority)">
            {{ getPriorityLabel(opportunity.priority) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="推荐原因" :span="2">
          {{ opportunity.reason || '基于历史数据分析，该时段具有较大的峰谷差异' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h3>推荐设备列表</h3>
      <el-table :data="opportunity.recommended_devices" border stripe>
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="device_type" label="设备类型" width="120" />
        <el-table-column prop="rated_power" label="额定功率(kW)" width="120" align="right">
          <template #default="{ row }">
            {{ row.rated_power?.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column prop="shiftable_power" label="可转移功率(kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.shiftable_power?.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column prop="flexibility_factor" label="柔性系数" width="100" align="center">
          <template #default="{ row }">
            {{ (row.flexibility_factor * 100).toFixed(0) }}%
          </template>
        </el-table-column>
      </el-table>

      <el-divider />

      <h3>分析数据</h3>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="电价差">
          {{ opportunity.analysis_data?.price_diff?.toFixed(2) }} 元/kWh
        </el-descriptions-item>
        <el-descriptions-item label="回溯天数">
          {{ opportunity.analysis_data?.lookback_days }} 天
        </el-descriptions-item>
        <el-descriptions-item label="推荐设备数">
          {{ opportunity.analysis_data?.device_count }} 台
        </el-descriptions-item>
      </el-descriptions>

      <div class="action-buttons">
        <el-button
          type="primary"
          size="large"
          @click="handleConvert"
          :disabled="opportunity.status !== 'pending'"
        >
          转换为转移计划
        </el-button>
        <el-button
          type="danger"
          size="large"
          plain
          @click="handleReject"
          :disabled="opportunity.status !== 'pending'"
        >
          拒绝此机会
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOpportunityDetail, convertOpportunityToPlan, type ShiftOpportunity } from '@/api/modules/shift'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const opportunity = ref<ShiftOpportunity>({
  id: 0,
  opportunity_code: '',
  opportunity_name: '',
  recommended_devices: [],
  analysis_data: {},
  status: 'pending',
  priority: 'medium'
})

onMounted(() => {
  fetchOpportunityDetail()
})

const fetchOpportunityDetail = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await getOpportunityDetail(id)
    opportunity.value = res
  } catch {
    ElMessage.error('获取机会详情失败')
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  router.back()
}

const handleConvert = async () => {
  try {
    await ElMessageBox.confirm(
      `确认将机会 "${opportunity.value.opportunity_name}" 转换为转移计划？`,
      '转换确认',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await convertOpportunityToPlan(opportunity.value.id)
    ElMessage.success('转换成功')
    router.push(`/energy/shift/detail/${res.id}`)
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('转换失败')
    }
  }
}

const handleReject = async () => {
  try {
    await ElMessageBox.confirm(
      '确认拒绝此机会？拒绝后将无法再转换为计划。',
      '拒绝确认',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // TODO: 实现拒绝接口
    ElMessage.success('已拒绝')
    fetchOpportunityDetail()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const getConfidenceColor = (score: number) => {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getPriorityType = (priority: string): TagType => {
  const map: Record<string, TagType> = {
    high: 'danger',
    medium: 'warning',
    low: 'info'
  }
  return map[priority] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return map[priority] || priority
}

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    converted: 'success',
    rejected: 'danger',
    expired: 'info'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    converted: '已转换',
    rejected: '已拒绝',
    expired: '已过期'
  }
  return map[status] || status
}
</script>

<style scoped lang="scss">
.shift-opportunity-detail {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 500;
  }

  .detail-card {
    margin-top: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .highlight-value {
      font-size: 16px;
      font-weight: 600;
      color: #409eff;

      &.success {
        color: #67c23a;
      }
    }

    h3 {
      margin: 20px 0 15px;
      font-size: 16px;
      font-weight: 500;
    }

    .action-buttons {
      margin-top: 30px;
      text-align: center;

      .el-button {
        min-width: 180px;
      }
    }
  }
}
</style>
