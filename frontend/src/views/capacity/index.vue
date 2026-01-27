<template>
  <div class="capacity-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-space">
          <div class="stat-icon" style="background: linear-gradient(135deg, #409eff, #66b1ff);">
            <el-icon :size="28"><Grid /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.space?.usage_rate?.toFixed(1) || 0 }}%</div>
            <div class="stat-label">空间容量</div>
            <div class="stat-detail">{{ statistics.space?.used_u_positions || 0 }}/{{ statistics.space?.total_u_positions || 0 }} U</div>
            <el-progress
              :percentage="statistics.space?.usage_rate || 0"
              :stroke-width="6"
              :show-text="false"
              :color="getProgressColor(statistics.space?.usage_rate)"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-power">
          <div class="stat-icon" style="background: linear-gradient(135deg, #e6a23c, #f0c78a);">
            <el-icon :size="28"><Lightning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.power?.usage_rate?.toFixed(1) || 0 }}%</div>
            <div class="stat-label">电力容量</div>
            <div class="stat-detail">{{ statistics.power?.used_power || 0 }}/{{ statistics.power?.total_power || 0 }} kW</div>
            <el-progress
              :percentage="statistics.power?.usage_rate || 0"
              :stroke-width="6"
              :show-text="false"
              :color="getProgressColor(statistics.power?.usage_rate)"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-cooling">
          <div class="stat-icon" style="background: linear-gradient(135deg, #67c23a, #95d475);">
            <el-icon :size="28"><Odometer /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.cooling?.usage_rate?.toFixed(1) || 0 }}%</div>
            <div class="stat-label">制冷容量</div>
            <div class="stat-detail">{{ statistics.cooling?.used_cooling || 0 }}/{{ statistics.cooling?.total_cooling || 0 }} kW</div>
            <el-progress
              :percentage="statistics.cooling?.usage_rate || 0"
              :stroke-width="6"
              :show-text="false"
              :color="getProgressColor(statistics.cooling?.usage_rate)"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-weight">
          <div class="stat-icon" style="background: linear-gradient(135deg, #909399, #b4b4b6);">
            <el-icon :size="28"><Box /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.weight?.usage_rate?.toFixed(1) || 0 }}%</div>
            <div class="stat-label">承重容量</div>
            <div class="stat-detail">{{ statistics.weight?.used_weight || 0 }}/{{ statistics.weight?.total_weight || 0 }} kg</div>
            <el-progress
              :percentage="statistics.weight?.usage_rate || 0"
              :stroke-width="6"
              :show-text="false"
              :color="getProgressColor(statistics.weight?.usage_rate)"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主内容区域 -->
    <el-card shadow="hover" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 空间容量标签页 -->
        <el-tab-pane label="空间容量" name="space">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showSpaceDialog()">新增空间</el-button>
          </div>
          <el-table :data="spaceList" stripe border v-loading="loading">
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="location" label="位置" min-width="120" />
            <el-table-column label="U位使用" width="140">
              <template #default="{ row }">
                {{ row.used_u_positions }}/{{ row.total_u_positions }} U
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="180">
              <template #default="{ row }">
                <div class="usage-cell">
                  <el-progress
                    :percentage="row.usage_rate"
                    :stroke-width="8"
                    :color="getProgressColor(row.usage_rate)"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showSpaceDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeleteSpace(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 电力容量标签页 -->
        <el-tab-pane label="电力容量" name="power">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showPowerDialog()">新增电力</el-button>
          </div>
          <el-table :data="powerList" stripe border v-loading="loading">
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="capacity_type" label="容量类型" width="120">
              <template #default="{ row }">
                {{ row.capacity_type || 'UPS' }}
              </template>
            </el-table-column>
            <el-table-column label="功率使用" width="140">
              <template #default="{ row }">
                {{ row.used_power }}/{{ row.total_power }} kW
              </template>
            </el-table-column>
            <el-table-column prop="redundancy_mode" label="冗余模式" width="100">
              <template #default="{ row }">
                {{ row.redundancy_mode || 'N' }}
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="180">
              <template #default="{ row }">
                <div class="usage-cell">
                  <el-progress
                    :percentage="row.usage_rate"
                    :stroke-width="8"
                    :color="getProgressColor(row.usage_rate)"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showPowerDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeletePower(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 制冷容量标签页 -->
        <el-tab-pane label="制冷容量" name="cooling">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showCoolingDialog()">新增制冷</el-button>
          </div>
          <el-table :data="coolingList" stripe border v-loading="loading">
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="location" label="位置" min-width="120" />
            <el-table-column label="制冷量" width="140">
              <template #default="{ row }">
                {{ row.total_cooling }} kW
              </template>
            </el-table-column>
            <el-table-column label="温度" width="140">
              <template #default="{ row }">
                {{ row.current_temperature || '--' }}/{{ row.target_temperature || '--' }}°C
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="180">
              <template #default="{ row }">
                <div class="usage-cell">
                  <el-progress
                    :percentage="row.usage_rate"
                    :stroke-width="8"
                    :color="getProgressColor(row.usage_rate)"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showCoolingDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeleteCooling(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 上架评估标签页 -->
        <el-tab-pane label="上架评估" name="plan">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showPlanDialog()">新建评估</el-button>
          </div>
          <el-table :data="planList" stripe border v-loading="loading">
            <el-table-column prop="plan_name" label="名称" min-width="150" />
            <el-table-column prop="device_count" label="设备数量" width="100">
              <template #default="{ row }">
                {{ row.device_count || 0 }}
              </template>
            </el-table-column>
            <el-table-column prop="space_requirement" label="需求U位" width="100">
              <template #default="{ row }">
                {{ row.space_requirement || 0 }} U
              </template>
            </el-table-column>
            <el-table-column prop="power_requirement" label="需求功率" width="120">
              <template #default="{ row }">
                {{ row.power_requirement || 0 }} kW
              </template>
            </el-table-column>
            <el-table-column label="可行性" width="100">
              <template #default="{ row }">
                <el-tag :type="row.feasible ? 'success' : 'danger'" size="small">
                  {{ row.feasible ? '可行' : '不可行' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="feasibility_notes" label="评估说明" min-width="180">
              <template #default="{ row }">
                {{ row.feasibility_notes || row.description || '--' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showPlanDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeletePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 空间容量对话框 -->
    <el-dialog
      v-model="spaceDialogVisible"
      :title="isEdit ? '编辑空间容量' : '新增空间容量'"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="spaceFormRef"
        :model="spaceForm"
        :rules="spaceRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="spaceForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="spaceForm.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="总U位" prop="total_u_positions">
          <el-input-number
            v-model="spaceForm.total_u_positions"
            :min="1"
            :max="10000"
            placeholder="请输入总U位数"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="已用U位" prop="used_u_positions">
          <el-input-number
            v-model="spaceForm.used_u_positions"
            :min="0"
            :max="spaceForm.total_u_positions"
            placeholder="请输入已用U位数"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="告警阈值" prop="warning_threshold">
          <el-input-number
            v-model="spaceForm.warning_threshold"
            :min="0"
            :max="100"
            placeholder="百分比"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="spaceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSpaceForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 电力容量对话框 -->
    <el-dialog
      v-model="powerDialogVisible"
      :title="isEdit ? '编辑电力容量' : '新增电力容量'"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="powerFormRef"
        :model="powerForm"
        :rules="powerRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="powerForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="容量类型" prop="capacity_type">
          <el-select v-model="powerForm.capacity_type" placeholder="请选择容量类型" style="width: 100%">
            <el-option label="UPS" value="UPS" />
            <el-option label="PDU" value="PDU" />
            <el-option label="市电" value="市电" />
            <el-option label="柴发" value="柴发" />
          </el-select>
        </el-form-item>
        <el-form-item label="总容量(kW)" prop="total_capacity_kw">
          <el-input-number
            v-model="powerForm.total_capacity_kw"
            :min="0"
            :precision="2"
            placeholder="请输入总容量"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="已用(kW)" prop="used_capacity_kw">
          <el-input-number
            v-model="powerForm.used_capacity_kw"
            :min="0"
            :precision="2"
            placeholder="请输入已用容量"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="冗余模式" prop="redundancy_mode">
          <el-select v-model="powerForm.redundancy_mode" placeholder="请选择冗余模式" style="width: 100%">
            <el-option label="N" value="N" />
            <el-option label="N+1" value="N+1" />
            <el-option label="2N" value="2N" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="powerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPowerForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 制冷容量对话框 -->
    <el-dialog
      v-model="coolingDialogVisible"
      :title="isEdit ? '编辑制冷容量' : '新增制冷容量'"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="coolingFormRef"
        :model="coolingForm"
        :rules="coolingRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="coolingForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="coolingForm.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="总制冷量(kW)" prop="total_cooling_kw">
          <el-input-number
            v-model="coolingForm.total_cooling_kw"
            :min="0"
            :precision="2"
            placeholder="请输入总制冷量"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="已用(kW)" prop="used_cooling_kw">
          <el-input-number
            v-model="coolingForm.used_cooling_kw"
            :min="0"
            :precision="2"
            placeholder="请输入已用制冷量"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="目标温度(°C)" prop="target_temperature">
          <el-input-number
            v-model="coolingForm.target_temperature"
            :min="10"
            :max="35"
            :precision="1"
            placeholder="请输入目标温度"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="coolingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCoolingForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 上架评估对话框 -->
    <el-dialog
      v-model="planDialogVisible"
      :title="isEdit ? '编辑上架评估' : '新建上架评估'"
      width="600px"
      destroy-on-close
    >
      <el-form
        ref="planFormRef"
        :model="planForm"
        :rules="planRules"
        label-width="120px"
      >
        <el-form-item label="评估名称" prop="name">
          <el-input v-model="planForm.name" placeholder="请输入评估名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="planForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述"
          />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备数量" prop="device_count">
              <el-input-number
                v-model="planForm.device_count"
                :min="1"
                placeholder="请输入设备数量"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求U位" prop="required_u">
              <el-input-number
                v-model="planForm.required_u"
                :min="0"
                placeholder="请输入需求U位"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="需求功率(kW)" prop="required_power_kw">
              <el-input-number
                v-model="planForm.required_power_kw"
                :min="0"
                :precision="2"
                placeholder="请输入需求功率"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求制冷(kW)" prop="required_cooling_kw">
              <el-input-number
                v-model="planForm.required_cooling_kw"
                :min="0"
                :precision="2"
                placeholder="请输入需求制冷量"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="需求承重(kg)" prop="required_weight_kg">
          <el-input-number
            v-model="planForm.required_weight_kg"
            :min="0"
            :precision="2"
            placeholder="请输入需求承重"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPlanForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Grid, Lightning, Odometer, Box, Plus } from '@element-plus/icons-vue'
import {
  getSpaceCapacities, createSpaceCapacity, updateSpaceCapacity, deleteSpaceCapacity,
  getPowerCapacities, createPowerCapacity, updatePowerCapacity, deletePowerCapacity,
  getCoolingCapacities, createCoolingCapacity, updateCoolingCapacity, deleteCoolingCapacity,
  getCapacityPlans, createCapacityPlan, updateCapacityPlan, deleteCapacityPlan,
  getCapacityStatistics,
  type SpaceCapacity, type PowerCapacity, type CoolingCapacity, type CapacityPlan,
  type CapacityStatistics, type CapacityStatus
} from '@/api/modules/capacity'

// 类型定义
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const activeTab = ref('space')

// 列表数据
const spaceList = ref<SpaceCapacity[]>([])
const powerList = ref<(PowerCapacity & { capacity_type?: string; redundancy_mode?: string })[]>([])
const coolingList = ref<(CoolingCapacity & { current_temperature?: number; target_temperature?: number })[]>([])
const planList = ref<(CapacityPlan & { device_count?: number; feasible?: boolean; feasibility_notes?: string })[]>([])
const statistics = ref<Partial<CapacityStatistics>>({})

// 对话框状态
const isEdit = ref(false)
const currentId = ref<number | null>(null)

// 空间容量对话框
const spaceDialogVisible = ref(false)
const spaceFormRef = ref<FormInstance>()
const spaceForm = reactive({
  name: '',
  location: '',
  total_u_positions: 42,
  used_u_positions: 0,
  warning_threshold: 80
})

const spaceRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  total_u_positions: [{ required: true, message: '请输入总U位数', trigger: 'blur' }]
}

// 电力容量对话框
const powerDialogVisible = ref(false)
const powerFormRef = ref<FormInstance>()
const powerForm = reactive({
  name: '',
  capacity_type: 'UPS',
  total_capacity_kw: 0,
  used_capacity_kw: 0,
  redundancy_mode: 'N'
})

const powerRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  total_capacity_kw: [{ required: true, message: '请输入总容量', trigger: 'blur' }]
}

// 制冷容量对话框
const coolingDialogVisible = ref(false)
const coolingFormRef = ref<FormInstance>()
const coolingForm = reactive({
  name: '',
  location: '',
  total_cooling_kw: 0,
  used_cooling_kw: 0,
  target_temperature: 24
})

const coolingRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  total_cooling_kw: [{ required: true, message: '请输入总制冷量', trigger: 'blur' }]
}

// 上架评估对话框
const planDialogVisible = ref(false)
const planFormRef = ref<FormInstance>()
const planForm = reactive({
  name: '',
  description: '',
  device_count: 1,
  required_u: 0,
  required_power_kw: 0,
  required_cooling_kw: 0,
  required_weight_kg: 0
})

const planRules = {
  name: [{ required: true, message: '请输入评估名称', trigger: 'blur' }],
  device_count: [{ required: true, message: '请输入设备数量', trigger: 'blur' }]
}

// 初始化加载
onMounted(() => {
  loadStatistics()
  loadSpaceList()
})

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getCapacityStatistics()
    if (res.data) {
      statistics.value = res.data
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

// 标签页切换
function handleTabChange(tab: string) {
  switch (tab) {
    case 'space':
      loadSpaceList()
      break
    case 'power':
      loadPowerList()
      break
    case 'cooling':
      loadCoolingList()
      break
    case 'plan':
      loadPlanList()
      break
  }
}

// ==================== 空间容量 ====================
async function loadSpaceList() {
  loading.value = true
  try {
    const res = await getSpaceCapacities()
    if (res.data) {
      spaceList.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('加载空间容量列表失败', e)
    ElMessage.error('加载空间容量列表失败')
  } finally {
    loading.value = false
  }
}

function showSpaceDialog(row?: SpaceCapacity) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(spaceForm, {
      name: row.name,
      location: row.location || '',
      total_u_positions: row.total_u_positions,
      used_u_positions: row.used_u_positions,
      warning_threshold: row.warning_threshold
    })
  } else {
    Object.assign(spaceForm, {
      name: '',
      location: '',
      total_u_positions: 42,
      used_u_positions: 0,
      warning_threshold: 80
    })
  }
  spaceDialogVisible.value = true
}

async function submitSpaceForm() {
  const valid = await spaceFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      name: spaceForm.name,
      location: spaceForm.location || undefined,
      total_area: 0,
      total_cabinets: 0,
      total_u_positions: spaceForm.total_u_positions,
      used_u_positions: spaceForm.used_u_positions,
      warning_threshold: spaceForm.warning_threshold
    }

    if (isEdit.value && currentId.value) {
      await updateSpaceCapacity(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createSpaceCapacity(data)
      ElMessage.success('创建成功')
    }
    spaceDialogVisible.value = false
    loadSpaceList()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

function confirmDeleteSpace(row: SpaceCapacity) {
  ElMessageBox.confirm(
    `确定要删除空间容量 "${row.name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteSpaceCapacity(row.id)
      ElMessage.success('删除成功')
      loadSpaceList()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 电力容量 ====================
async function loadPowerList() {
  loading.value = true
  try {
    const res = await getPowerCapacities()
    if (res.data) {
      powerList.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('加载电力容量列表失败', e)
    ElMessage.error('加载电力容量列表失败')
  } finally {
    loading.value = false
  }
}

function showPowerDialog(row?: PowerCapacity & { capacity_type?: string; redundancy_mode?: string }) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(powerForm, {
      name: row.name,
      capacity_type: row.capacity_type || 'UPS',
      total_capacity_kw: row.total_power,
      used_capacity_kw: row.used_power,
      redundancy_mode: row.redundancy_mode || 'N'
    })
  } else {
    Object.assign(powerForm, {
      name: '',
      capacity_type: 'UPS',
      total_capacity_kw: 0,
      used_capacity_kw: 0,
      redundancy_mode: 'N'
    })
  }
  powerDialogVisible.value = true
}

async function submitPowerForm() {
  const valid = await powerFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      name: powerForm.name,
      total_power: powerForm.total_capacity_kw,
      used_power: powerForm.used_capacity_kw
    }

    if (isEdit.value && currentId.value) {
      await updatePowerCapacity(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createPowerCapacity(data)
      ElMessage.success('创建成功')
    }
    powerDialogVisible.value = false
    loadPowerList()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

function confirmDeletePower(row: PowerCapacity) {
  ElMessageBox.confirm(
    `确定要删除电力容量 "${row.name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deletePowerCapacity(row.id)
      ElMessage.success('删除成功')
      loadPowerList()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 制冷容量 ====================
async function loadCoolingList() {
  loading.value = true
  try {
    const res = await getCoolingCapacities()
    if (res.data) {
      coolingList.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('加载制冷容量列表失败', e)
    ElMessage.error('加载制冷容量列表失败')
  } finally {
    loading.value = false
  }
}

function showCoolingDialog(row?: CoolingCapacity & { target_temperature?: number }) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(coolingForm, {
      name: row.name,
      location: row.location || '',
      total_cooling_kw: row.total_cooling,
      used_cooling_kw: row.used_cooling,
      target_temperature: row.target_temperature || 24
    })
  } else {
    Object.assign(coolingForm, {
      name: '',
      location: '',
      total_cooling_kw: 0,
      used_cooling_kw: 0,
      target_temperature: 24
    })
  }
  coolingDialogVisible.value = true
}

async function submitCoolingForm() {
  const valid = await coolingFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      name: coolingForm.name,
      location: coolingForm.location || undefined,
      total_cooling: coolingForm.total_cooling_kw,
      used_cooling: coolingForm.used_cooling_kw
    }

    if (isEdit.value && currentId.value) {
      await updateCoolingCapacity(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createCoolingCapacity(data)
      ElMessage.success('创建成功')
    }
    coolingDialogVisible.value = false
    loadCoolingList()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

function confirmDeleteCooling(row: CoolingCapacity) {
  ElMessageBox.confirm(
    `确定要删除制冷容量 "${row.name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteCoolingCapacity(row.id)
      ElMessage.success('删除成功')
      loadCoolingList()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 上架评估 ====================
async function loadPlanList() {
  loading.value = true
  try {
    const res = await getCapacityPlans()
    if (res.data) {
      planList.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('加载上架评估列表失败', e)
    ElMessage.error('加载上架评估列表失败')
  } finally {
    loading.value = false
  }
}

function showPlanDialog(row?: CapacityPlan & { device_count?: number }) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(planForm, {
      name: row.plan_name,
      description: row.description || '',
      device_count: row.device_count || 1,
      required_u: row.space_requirement || 0,
      required_power_kw: row.power_requirement || 0,
      required_cooling_kw: row.cooling_requirement || 0,
      required_weight_kg: row.weight_requirement || 0
    })
  } else {
    Object.assign(planForm, {
      name: '',
      description: '',
      device_count: 1,
      required_u: 0,
      required_power_kw: 0,
      required_cooling_kw: 0,
      required_weight_kg: 0
    })
  }
  planDialogVisible.value = true
}

async function submitPlanForm() {
  const valid = await planFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      plan_name: planForm.name,
      plan_type: 'deployment',
      description: planForm.description || undefined,
      target_date: new Date().toISOString().split('T')[0],
      space_requirement: planForm.required_u,
      power_requirement: planForm.required_power_kw,
      cooling_requirement: planForm.required_cooling_kw,
      weight_requirement: planForm.required_weight_kg
    }

    if (isEdit.value && currentId.value) {
      await updateCapacityPlan(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createCapacityPlan(data)
      ElMessage.success('创建成功')
    }
    planDialogVisible.value = false
    loadPlanList()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

function confirmDeletePlan(row: CapacityPlan) {
  ElMessageBox.confirm(
    `确定要删除上架评估 "${row.plan_name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteCapacityPlan(row.id)
      ElMessage.success('删除成功')
      loadPlanList()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 辅助函数 ====================

/** 获取状态标签类型 */
function getStatusType(status: CapacityStatus): TagType {
  const map: Record<CapacityStatus, TagType> = {
    normal: 'success',
    warning: 'warning',
    critical: 'danger',
    full: 'danger'
  }
  return map[status] || 'info'
}

/** 获取状态标签文本 */
function getStatusLabel(status: CapacityStatus): string {
  const map: Record<CapacityStatus, string> = {
    normal: '正常',
    warning: '警告',
    critical: '严重',
    full: '已满'
  }
  return map[status] || status
}

/** 获取进度条颜色 */
function getProgressColor(percentage: number | undefined): string {
  const p = percentage || 0
  if (p >= 90) return '#f56c6c'
  if (p >= 70) return '#e6a23c'
  return '#67c23a'
}
</script>

<style scoped lang="scss">
.capacity-page {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: all 0.3s ease;

    :deep(.el-card__body) {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 20px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;
    }

    .stat-info {
      flex: 1;
      min-width: 0;

      .stat-value {
        font-size: 28px;
        font-weight: bold;
        color: var(--text-primary);
        line-height: 1.2;
      }

      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
        margin-top: 4px;
      }

      .stat-detail {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 4px;
        margin-bottom: 8px;
      }

      :deep(.el-progress) {
        .el-progress-bar__outer {
          background-color: rgba(255, 255, 255, 0.1);
        }
      }
    }

    &:hover {
      transform: translateY(-2px);
      border-color: var(--accent-color);
    }

    &.stat-card-space:hover {
      box-shadow: 0 0 20px rgba(64, 158, 255, 0.3);
    }

    &.stat-card-power:hover {
      box-shadow: 0 0 20px rgba(230, 162, 60, 0.3);
    }

    &.stat-card-cooling:hover {
      box-shadow: 0 0 20px rgba(103, 194, 58, 0.3);
    }

    &.stat-card-weight:hover {
      box-shadow: 0 0 20px rgba(144, 147, 153, 0.3);
    }
  }

  .main-card {
    background: var(--bg-card-solid);
    border-color: var(--border-color);

    :deep(.el-card__body) {
      background-color: var(--bg-card-solid);
    }

    :deep(.el-tabs__header) {
      margin-bottom: 20px;
      background-color: var(--bg-tertiary);
      border-bottom: 1px solid var(--border-color);
      padding: 0 16px;
    }

    :deep(.el-tabs__nav-wrap::after) {
      background-color: transparent;
    }

    :deep(.el-tabs__item) {
      color: var(--text-secondary);
      font-weight: 400;
      height: 48px;
      line-height: 48px;

      &.is-active {
        color: var(--accent-color);
        font-weight: 500;
      }

      &:hover {
        color: var(--text-primary);
      }
    }

    :deep(.el-tabs__active-bar) {
      background-color: var(--accent-color);
    }

    :deep(.el-tabs__content) {
      background-color: var(--bg-card-solid);
      padding: 0 16px 16px;
    }
  }

  .tab-toolbar {
    margin-bottom: 16px;
    display: flex;
    justify-content: flex-start;
    gap: 12px;
  }

  .usage-cell {
    padding-right: 10px;

    :deep(.el-progress) {
      .el-progress__text {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }
  }

  :deep(.el-table) {
    background: transparent;

    th.el-table__cell {
      background: var(--bg-card);
      color: var(--text-primary);
      border-color: var(--border-color);
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background: var(--bg-card);

      &:hover > td.el-table__cell {
        background: rgba(255, 255, 255, 0.05);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background: rgba(255, 255, 255, 0.02);
    }
  }

  :deep(.el-dialog) {
    background: var(--bg-card);
    border: 1px solid var(--border-color);

    .el-dialog__header {
      border-bottom: 1px solid var(--border-color);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__footer {
      border-top: 1px solid var(--border-color);
    }
  }

  :deep(.el-form-item__label) {
    color: var(--text-secondary);
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select .el-input__wrapper),
  :deep(.el-input-number) {
    background: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--accent-color);
    }
  }

  :deep(.el-input__inner),
  :deep(.el-textarea__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-secondary);
    }
  }
}
</style>
