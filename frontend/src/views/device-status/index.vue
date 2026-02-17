<template>
  <div class="device-status-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ summary.total }}</div>
          <div class="stat-label">总设备数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value online">{{ summary.online }}</div>
          <div class="stat-label">在线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value offline">{{ summary.offline }}</div>
          <div class="stat-label">离线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value alarm">{{ summary.alarm }}</div>
          <div class="stat-label">告警设备</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="filters.area_code" placeholder="全部区域" clearable @change="loadData">
            <el-option v-for="a in areaOptions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="filters.device_type" placeholder="全部类型" clearable @change="loadData">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 按区域分组的设备卡片 -->
    <div v-if="groups.length > 0">
      <div v-for="group in groups" :key="`${group.area_code}_${group.device_type}`" class="device-group">
        <h4 class="group-title">{{ group.area_code }} 区 — {{ group.device_type }}</h4>
        <el-row :gutter="12">
          <el-col
            :xs="12" :sm="8" :md="6" :lg="4"
            v-for="device in group.devices"
            :key="device.id"
          >
            <el-card shadow="hover" class="device-card" @click="goDetail(device.id)">
              <div class="device-card-inner">
                <span class="status-dot" :class="device.status" />
                <span class="device-name">{{ device.device_name }}</span>
              </div>
              <el-tag size="small" class="device-type-tag">{{ group.device_type }}</el-tag>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </div>
    <el-empty v-else description="暂无匹配设备" />
  </div>
</template>

<script setup lang="ts">
import { getDeviceStatusBoard } from '@/api/modules/device'
import type { DeviceStatusGroup } from '@/api/modules/device'

const router = useRouter()

const areaOptions = ['A1', 'A2', 'B1', 'F1', 'F2', 'F3']
const typeOptions = ['UPS', 'AC', 'PDU', 'TH', 'DOOR', 'SMOKE', 'WATER']

const filters = reactive<{ area_code?: string; device_type?: string }>({})
const summary = reactive({ total: 0, online: 0, offline: 0, alarm: 0, maintenance: 0 })
const groups = ref<DeviceStatusGroup[]>([])

let timer: ReturnType<typeof setInterval> | null = null

async function loadData() {
  try {
    const params: Record<string, string> = {}
    if (filters.area_code) params.area_code = filters.area_code
    if (filters.device_type) params.device_type = filters.device_type
    const res = await getDeviceStatusBoard(params)
    Object.assign(summary, res.summary)
    groups.value = res.groups
  } catch {
    // 静默处理
  }
}

function goDetail(id: number) {
  router.push(`/device-manage/detail/${id}`)
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 30000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.device-status-page {
  @include page-dashboard(4);
  padding: 16px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-value.online {
  color: #67c23a;
}

.stat-value.offline {
  color: #f56c6c;
}

.stat-value.alarm {
  color: #e6a23c;
}

.filter-card {
  margin-bottom: 16px;
}

.device-group {
  margin-bottom: 20px;
}

.group-title {
  margin: 0 0 12px;
  font-size: 15px;
  color: #606266;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.device-card {
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.2s;
}

.device-card:hover {
  transform: translateY(-2px);
}

.device-card-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  background-color: #909399;
}

.status-dot.online {
  background-color: #67c23a;
}

.status-dot.offline {
  background-color: #f56c6c;
}

.status-dot.alarm {
  background-color: #e6a23c;
}

.status-dot.maintenance {
  background-color: #909399;
}

.device-name {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-type-tag {
  margin-top: 4px;
}
</style>
