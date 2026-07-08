<template>
  <div class="deployment-phase-view">
    <el-page-header @back="$router.back()">
      <template #content>
        <span>部署管理</span>
      </template>
    </el-page-header>

    <!-- 部署阶段进度 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header-row">
          <span>部署阶段</span>
          <div>
            <el-tag v-if="phaseInfo" type="primary" effect="dark" size="large" style="margin-right: 12px">
              {{ phaseInfo.phase_name }}
            </el-tag>
            <el-button
              v-if="userStore.isAdmin"
              type="primary"
              size="small"
              @click="showSwitchDialog = true"
            >切换阶段</el-button>
          </div>
        </div>
      </template>

      <div v-loading="phaseLoading" style="padding: 20px 40px">
        <el-steps :active="(phaseInfo?.current_phase ?? 1) - 1" finish-status="success" align-center>
          <el-step title="THM 模式" description="仅使用 THM 估算，不执行预冷" />
          <el-step title="校准模式" description="运行 RC 校准，对比 THM 与 TCL 结果" />
          <el-step title="TCL 上线" description="使用校准后的 TCL 模型执行预冷" />
          <el-step title="VPP 接入" description="开放 VPP 接口" />
        </el-steps>
        <div v-if="phaseInfo?.updated_at" style="text-align: center; margin-top: 12px; color: #909399; font-size: 12px">
          最后更新: {{ formatTime(phaseInfo.updated_at) }}
        </div>
      </div>
    </el-card>

    <!-- 区域校准状态 -->
    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        <div class="card-header-row">
          <span>区域校准状态</span>
          <el-button :icon="Refresh" size="small" @click="loadData">刷新</el-button>
        </div>
      </template>

      <el-table :data="zoneRows" v-loading="tableLoading" stripe style="width: 100%">
        <el-table-column prop="zone_name" label="区域名称" min-width="120" />
        <el-table-column label="当前模式" width="100">
          <template #default="{ row }">
            <el-tag :type="row.model_mode === 'TCL' ? 'success' : 'info'" size="small">
              {{ row.model_mode }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="R 值" width="100">
          <template #default="{ row }">
            {{ row.calibration?.thermal_R != null ? row.calibration.thermal_R.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="C 值" width="100">
          <template #default="{ row }">
            {{ row.calibration?.thermal_C != null ? row.calibration.thermal_C.toFixed(1) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="R²" width="80">
          <template #default="{ row }">
            <span :style="{ color: getR2Color(row.calibration?.fitting_r_squared) }">
              {{ row.calibration?.fitting_r_squared != null ? row.calibration.fitting_r_squared.toFixed(3) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="校准方法" width="100">
          <template #default="{ row }">
            {{ methodLabel(row.calibration?.fitting_method) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="calibrationStatusType(row)" size="small">
              {{ calibrationStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              :loading="row.calibrating"
              :disabled="!userStore.isOperator"
              @click="handleCalibrate(row)"
            >校准</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 阶段切换对话框 -->
    <el-dialog v-model="showSwitchDialog" title="切换部署阶段" width="440px">
      <el-form label-width="80px">
        <el-form-item label="目标阶段">
          <el-select v-model="switchForm.phase" style="width: 100%">
            <el-option :value="1" label="Phase 1 — THM 模式" />
            <el-option :value="2" label="Phase 2 — 校准模式" />
            <el-option :value="3" label="Phase 3 — TCL 上线" />
            <el-option :value="4" label="Phase 4 — VPP 接入" />
          </el-select>
        </el-form-item>
        <el-form-item label="强制切换">
          <el-checkbox v-model="switchForm.force">跳过前置检查（仅紧急情况使用）</el-checkbox>
        </el-form-item>
      </el-form>

      <!-- 前置条件失败详情 -->
      <el-alert
        v-if="switchError"
        :title="switchError.message"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      >
        <template #default>
          <ul v-if="switchError.details?.length" style="margin: 4px 0 0; padding-left: 20px">
            <li v-for="(d, i) in switchError.details" :key="i">{{ d }}</li>
          </ul>
        </template>
      </el-alert>

      <template #footer>
        <el-button @click="showSwitchDialog = false">取消</el-button>
        <el-button type="primary" :loading="switching" @click="handleSwitch">确认切换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  getDeploymentPhase,
  updateDeploymentPhase,
  getDashboard,
  triggerCalibration,
  getCalibrationHistory,
} from '@/api/modules/precool'
import type { DeploymentPhaseInfo, CalibrationHistoryItem, DashboardZone } from '@/api/modules/precool'

const userStore = useUserStore()

// ========== 部署阶段 ==========
const phaseInfo = ref<DeploymentPhaseInfo | null>(null)
const phaseLoading = ref(false)

async function fetchPhase() {
  phaseLoading.value = true
  try {
    const res = await getDeploymentPhase()
    const body = (res as any).data
    const data = body?.data ?? body
    if (body?.code === 200 || data?.current_phase) {
      phaseInfo.value = data
    }
  } catch (e) {
    console.error('获取部署阶段失败:', e)
  } finally {
    phaseLoading.value = false
  }
}

// ========== 区域校准状态 ==========
interface ZoneRow extends DashboardZone {
  calibration: CalibrationHistoryItem | null
  calibrating: boolean
}

const zoneRows = ref<ZoneRow[]>([])
const tableLoading = ref(false)

async function fetchZones() {
  tableLoading.value = true
  try {
    const res = await getDashboard()
    const body = (res as any).data
    const dashData = body?.data ?? body
    const zones = dashData?.zones || []
    const rows: ZoneRow[] = zones.map((z: DashboardZone) => ({
      ...z,
      calibration: null,
      calibrating: false,
    }))

    // 并行获取每个 zone 的最新校准记录
    await Promise.allSettled(
      rows.map(async (row) => {
        try {
          const hRes = await getCalibrationHistory(row.zone_id, { limit: 1 })
          const hBody = (hRes as any).data
          const hData = hBody?.data ?? hBody
          if (hData?.items?.length) {
            row.calibration = hData.items[0]
          }
        } catch {
          // 忽略单个 zone 查询失败
        }
      })
    )

    zoneRows.value = rows
  } catch (e) {
    console.error('获取区域列表失败:', e)
  } finally {
    tableLoading.value = false
  }
}

// ========== 校准 ==========
async function handleCalibrate(row: ZoneRow) {
  row.calibrating = true
  try {
    const res = await triggerCalibration(row.zone_id)
    const body = (res as any).data
    const code = body?.code
    const data = body?.data ?? body
    const msg = body?.message
    if (code === 200) {
      ElMessage.success(`区域 ${row.zone_name} 校准完成 (R²=${data?.r_squared?.toFixed(3)})`)
      // 刷新该 zone 的校准记录
      const hRes = await getCalibrationHistory(row.zone_id, { limit: 1 })
      const hBody = (hRes as any).data
      const hData = hBody?.data ?? hBody
      if (hData?.items?.length) {
        row.calibration = hData.items[0]
      }
    } else if (code === 503) {
      ElMessage.error('scipy 未安装，校准功能不可用')
    } else if (code === 422) {
      ElMessage.warning(`校准失败: ${data?.error || msg}`)
    } else {
      ElMessage.error(msg || '校准失败')
    }
  } catch {
    ElMessage.error('校准请求异常')
  } finally {
    row.calibrating = false
  }
}

// ========== 阶段切换 ==========
const showSwitchDialog = ref(false)
const switching = ref(false)
const switchForm = reactive({ phase: 1, force: false })
const switchError = ref<{ message: string; details?: string[] } | null>(null)

async function handleSwitch() {
  switching.value = true
  switchError.value = null
  try {
    const res = await updateDeploymentPhase({
      phase: switchForm.phase,
      force: switchForm.force,
    })
    const body = (res as any).data
    const code = body?.code
    const data = body?.data ?? body
    const msg = body?.message
    if (code === 200) {
      ElMessage.success('阶段切换成功')
      showSwitchDialog.value = false
      await fetchPhase()
    } else if (code === 422) {
      switchError.value = {
        message: '前置条件不满足',
        details: data?.details || [],
      }
    } else {
      switchError.value = {
        message: typeof data?.details === 'string' ? data.details : (msg || '切换失败'),
      }
    }
  } catch {
    switchError.value = { message: '请求异常' }
  } finally {
    switching.value = false
  }
}

// ========== 辅助函数 ==========
function formatTime(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function getR2Color(r2: number | null | undefined): string {
  if (r2 == null) return '#909399'
  if (r2 >= 0.85) return '#67c23a'
  if (r2 >= 0.7) return '#e6a23c'
  return '#f56c6c'
}

function methodLabel(method: string | null | undefined): string {
  if (!method) return '-'
  const map: Record<string, string> = {
    auto_fit: '自动校准',
    manual: '手动设置',
    default: '默认值',
    demo: '演示',
  }
  return map[method] || method
}

function calibrationStatusType(row: ZoneRow): 'success' | 'warning' | 'info' | 'danger' {
  if (row.calibrating) return 'warning'
  if (!row.calibration) return 'info'
  const cal = row.calibration
  if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared >= 0.85) {
    return 'success'
  }
  if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared < 0.85) {
    return 'warning'
  }
  return 'info'
}

function calibrationStatusLabel(row: ZoneRow): string {
  if (row.calibrating) return '校准中'
  if (!row.calibration) return '待校准'
  const cal = row.calibration
  if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared >= 0.85) {
    return '已校准'
  }
  if (cal.fitting_method === 'auto_fit' && cal.fitting_r_squared != null && cal.fitting_r_squared < 0.85) {
    return 'R²不足'
  }
  if (cal.fitting_method === 'manual') return '手动设置'
  return '待校准'
}

// ========== 初始化 ==========
async function loadData() {
  await Promise.all([fetchPhase(), fetchZones()])
}

onMounted(() => {
  loadData()
  // 初始化切换表单为当前阶段
  if (phaseInfo.value) {
    switchForm.phase = phaseInfo.value.current_phase
  }
})
</script>

<style scoped>
.deployment-phase-view {
  padding: 16px;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
