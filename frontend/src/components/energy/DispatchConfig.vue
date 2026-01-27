<template>
  <div class="dispatch-config">
    <!-- 空状态提示 -->
    <el-alert
      v-if="!loading.devices && devices.length === 0 && storageSystems.length === 0 && pvSystems.length === 0"
      type="info"
      :closable="false"
      class="empty-alert"
    >
      <template #title>暂无配置数据</template>
      <p>系统中尚未配置任何可调度资源。您可以手动添加，或点击下方按钮加载演示数据。</p>
      <el-button type="primary" @click="initDemo" :loading="loading.initDemo" style="margin-top: 12px;">
        加载演示数据
      </el-button>
    </el-alert>

    <el-tabs v-model="activeConfigTab">
      <!-- 可调度设备 -->
      <el-tab-pane label="可调度设备" name="devices">
        <div class="config-header">
          <el-button type="primary" @click="showDeviceDialog()">
            <el-icon><Plus /></el-icon>添加设备
          </el-button>
          <el-button @click="loadDevices" :loading="loading.devices">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
          <el-button v-if="devices.length === 0" @click="initDemo" :loading="loading.initDemo">
            加载演示数据
          </el-button>
        </div>

        <!-- 设备统计 -->
        <el-row :gutter="20" class="stats-row" v-if="deviceStats">
          <el-col :span="6">
            <el-statistic title="设备总数" :value="deviceStats.total" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="已启用" :value="deviceStats.active_count" />
          </el-col>
          <el-col :span="12">
            <div class="type-tags">
              <el-tag
                v-for="item in deviceStats.by_type"
                :key="item.type"
                :type="getTypeTagColor(item.type)"
                class="type-tag"
              >
                {{ deviceTypeLabels[item.type] }}: {{ item.count }}台 / {{ item.total_power }}kW
              </el-tag>
            </div>
          </el-col>
        </el-row>

        <el-table :data="devices" v-loading="loading.devices" stripe>
          <el-table-column prop="name" label="设备名称" min-width="120" />
          <el-table-column prop="device_type" label="设备类型" width="100">
            <template #default="{ row }">
              <el-tag :type="getTypeTagColor(row.device_type)">
                {{ deviceTypeLabels[row.device_type] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="rated_power" label="额定功率(kW)" width="110" />
          <el-table-column prop="priority" label="优先级" width="80" />
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关键参数" min-width="200">
            <template #default="{ row }">
              <span v-if="row.device_type === 'shiftable'">
                运行{{ row.run_duration }}h/次, {{ row.daily_runs }}次/天
              </span>
              <span v-else-if="row.device_type === 'curtailable'">
                可削减{{ row.curtail_ratio }}%, 最长{{ row.max_curtail_duration }}h
              </span>
              <span v-else-if="row.device_type === 'modulating'">
                {{ row.min_power || 0 }}-{{ row.max_power || row.rated_power }}kW
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showDeviceDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="deleteDevice(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 储能系统 -->
      <el-tab-pane label="储能系统" name="storage">
        <div class="config-header">
          <el-button type="primary" @click="showStorageDialog()">
            <el-icon><Plus /></el-icon>添加储能
          </el-button>
          <el-button @click="loadStorage" :loading="loading.storage">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>

        <el-table :data="storageSystems" v-loading="loading.storage" stripe>
          <el-table-column prop="name" label="系统名称" min-width="120" />
          <el-table-column prop="capacity" label="容量(kWh)" width="100" />
          <el-table-column prop="max_charge_power" label="充电功率(kW)" width="110" />
          <el-table-column prop="max_discharge_power" label="放电功率(kW)" width="110" />
          <el-table-column label="效率" width="120">
            <template #default="{ row }">
              充{{ (row.charge_efficiency * 100).toFixed(0) }}% / 放{{ (row.discharge_efficiency * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column label="SOC范围" width="100">
            <template #default="{ row }">
              {{ (row.min_soc * 100).toFixed(0) }}-{{ (row.max_soc * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column prop="cycle_cost" label="循环成本(元/kWh)" width="130" />
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showStorageDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="deleteStorage(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 光伏系统 -->
      <el-tab-pane label="光伏系统" name="pv">
        <div class="config-header">
          <el-button type="primary" @click="showPVDialog()">
            <el-icon><Plus /></el-icon>添加光伏
          </el-button>
          <el-button @click="loadPV" :loading="loading.pv">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>

        <el-table :data="pvSystems" v-loading="loading.pv" stripe>
          <el-table-column prop="name" label="系统名称" min-width="150" />
          <el-table-column prop="rated_capacity" label="额定容量(kWp)" width="120" />
          <el-table-column label="系统效率" width="100">
            <template #default="{ row }">
              {{ (row.efficiency * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column prop="is_controllable" label="可调度" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_controllable ? 'success' : 'info'">
                {{ row.is_controllable ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showPVDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="deletePV(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 设备编辑对话框 -->
    <el-dialog
      v-model="deviceDialog.visible"
      :title="deviceDialog.isEdit ? '编辑设备' : '添加设备'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="deviceForm" label-width="120px" ref="deviceFormRef">
        <el-form-item label="设备名称" prop="name" required>
          <el-input v-model="deviceForm.name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type" required>
          <el-select v-model="deviceForm.device_type" style="width: 100%">
            <el-option
              v-for="(label, key) in deviceTypeLabels"
              :key="key"
              :label="label"
              :value="key"
            >
              <span>{{ label }}</span>
              <span style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px;">
                {{ deviceTypeDescriptions[key] }}
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="额定功率(kW)" prop="rated_power" required>
          <el-input-number v-model="deviceForm.rated_power" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-slider v-model="deviceForm.priority" :min="1" :max="10" show-stops />
        </el-form-item>
        <el-form-item label="启用" prop="is_active">
          <el-switch v-model="deviceForm.is_active" />
        </el-form-item>

        <!-- 时移型参数 -->
        <template v-if="deviceForm.device_type === 'shiftable'">
          <el-divider>时移型参数</el-divider>
          <el-form-item label="运行时长(h)">
            <el-input-number v-model="deviceForm.run_duration" :min="0" :precision="1" />
          </el-form-item>
          <el-form-item label="每日运行次数">
            <el-input-number v-model="deviceForm.daily_runs" :min="1" />
          </el-form-item>
        </template>

        <!-- 削减型参数 -->
        <template v-if="deviceForm.device_type === 'curtailable'">
          <el-divider>削减型参数</el-divider>
          <el-form-item label="可削减比例(%)">
            <el-input-number v-model="deviceForm.curtail_ratio" :min="0" :max="100" />
          </el-form-item>
          <el-form-item label="最大削减时长(h)">
            <el-input-number v-model="deviceForm.max_curtail_duration" :min="0" :precision="1" />
          </el-form-item>
        </template>

        <!-- 调节型参数 -->
        <template v-if="deviceForm.device_type === 'modulating'">
          <el-divider>调节型参数</el-divider>
          <el-form-item label="最小功率(kW)">
            <el-input-number v-model="deviceForm.min_power" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="最大功率(kW)">
            <el-input-number v-model="deviceForm.max_power" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="调节速率(kW/min)">
            <el-input-number v-model="deviceForm.ramp_rate" :min="0" :precision="2" />
          </el-form-item>
        </template>

        <el-form-item label="描述">
          <el-input v-model="deviceForm.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="loading.saveDevice">保存</el-button>
      </template>
    </el-dialog>

    <!-- 储能编辑对话框 -->
    <el-dialog
      v-model="storageDialog.visible"
      :title="storageDialog.isEdit ? '编辑储能' : '添加储能'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="storageForm" label-width="130px">
        <el-form-item label="系统名称" required>
          <el-input v-model="storageForm.name" placeholder="请输入储能系统名称" />
        </el-form-item>
        <el-form-item label="容量(kWh)" required>
          <el-input-number v-model="storageForm.capacity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="最大充电功率(kW)" required>
          <el-input-number v-model="storageForm.max_charge_power" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="最大放电功率(kW)" required>
          <el-input-number v-model="storageForm.max_discharge_power" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="充电效率">
          <el-slider v-model="storageForm.charge_efficiency" :min="0.5" :max="1" :step="0.01" :format-tooltip="(v: number) => `${(v*100).toFixed(0)}%`" />
        </el-form-item>
        <el-form-item label="放电效率">
          <el-slider v-model="storageForm.discharge_efficiency" :min="0.5" :max="1" :step="0.01" :format-tooltip="(v: number) => `${(v*100).toFixed(0)}%`" />
        </el-form-item>
        <el-form-item label="SOC范围">
          <el-slider v-model="storageForm.soc_range" range :min="0" :max="1" :step="0.05" :format-tooltip="(v: number) => `${(v*100).toFixed(0)}%`" />
        </el-form-item>
        <el-form-item label="循环成本(元/kWh)">
          <el-input-number v-model="storageForm.cycle_cost" :min="0" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="storageForm.is_active" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="storageForm.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="storageDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveStorage" :loading="loading.saveStorage">保存</el-button>
      </template>
    </el-dialog>

    <!-- 光伏编辑对话框 -->
    <el-dialog
      v-model="pvDialog.visible"
      :title="pvDialog.isEdit ? '编辑光伏' : '添加光伏'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="pvForm" label-width="120px">
        <el-form-item label="系统名称" required>
          <el-input v-model="pvForm.name" placeholder="请输入光伏系统名称" />
        </el-form-item>
        <el-form-item label="额定容量(kWp)" required>
          <el-input-number v-model="pvForm.rated_capacity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="系统效率">
          <el-slider v-model="pvForm.efficiency" :min="0.5" :max="1" :step="0.01" :format-tooltip="(v: number) => `${(v*100).toFixed(0)}%`" />
        </el-form-item>
        <el-form-item label="可调度">
          <el-switch v-model="pvForm.is_controllable" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="pvForm.is_active" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="pvForm.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pvDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="savePV" :loading="loading.savePV">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDispatchableDevices,
  createDispatchableDevice,
  updateDispatchableDevice,
  deleteDispatchableDevice,
  getDeviceStats,
  getStorageSystems,
  createStorageSystem,
  updateStorageSystem,
  deleteStorageSystem,
  getPVSystems,
  createPVSystem,
  updatePVSystem,
  deletePVSystem,
  initDemoData,
  deviceTypeLabels,
  deviceTypeDescriptions,
  type DispatchableDevice,
  type StorageConfig,
  type PVConfig,
  type DeviceType,
  type DeviceStats
} from '@/api/modules/dispatch'

const activeConfigTab = ref('devices')

const loading = reactive({
  devices: false,
  storage: false,
  pv: false,
  saveDevice: false,
  saveStorage: false,
  savePV: false,
  initDemo: false
})

// 设备相关
const devices = ref<DispatchableDevice[]>([])
const deviceStats = ref<DeviceStats | null>(null)
const deviceDialog = reactive({ visible: false, isEdit: false })
const deviceForm = reactive<any>({
  name: '',
  device_type: 'shiftable',
  rated_power: 0,
  priority: 5,
  is_active: true
})

// 储能相关
const storageSystems = ref<StorageConfig[]>([])
const storageDialog = reactive({ visible: false, isEdit: false })
const storageForm = reactive<any>({
  name: '',
  capacity: 0,
  max_charge_power: 0,
  max_discharge_power: 0,
  charge_efficiency: 0.95,
  discharge_efficiency: 0.95,
  soc_range: [0.1, 0.9],
  cycle_cost: 0.1,
  is_active: true
})

// 光伏相关
const pvSystems = ref<PVConfig[]>([])
const pvDialog = reactive({ visible: false, isEdit: false })
const pvForm = reactive<any>({
  name: '',
  rated_capacity: 0,
  efficiency: 0.85,
  is_controllable: false,
  is_active: true
})

const currentEditId = ref<number | null>(null)

onMounted(() => {
  loadDevices()
  loadStorage()
  loadPV()
})

// ==================== 演示数据初始化 ====================

async function initDemo() {
  loading.initDemo = true
  try {
    const res = await initDemoData()
    if (res.data?.created) {
      ElMessage.success('演示数据初始化成功')
      // 重新加载所有数据
      loadDevices()
      loadStorage()
      loadPV()
    } else {
      ElMessage.info(res.data?.message || '演示数据已存在')
    }
  } catch (e) {
    ElMessage.error('初始化失败')
    console.error('初始化演示数据失败', e)
  } finally {
    loading.initDemo = false
  }
}

function getTypeTagColor(type: DeviceType): string {
  const colors: Record<string, string> = {
    shiftable: 'primary',
    curtailable: 'warning',
    modulating: 'success',
    generation: '',
    storage: 'info',
    rigid: 'danger'
  }
  return colors[type] || ''
}

// ==================== 设备管理 ====================

async function loadDevices() {
  loading.devices = true
  try {
    const [devicesRes, statsRes] = await Promise.all([
      getDispatchableDevices(),
      getDeviceStats()
    ])
    devices.value = devicesRes.data || []
    deviceStats.value = statsRes.data || null
  } catch (e) {
    console.error('加载设备失败', e)
  } finally {
    loading.devices = false
  }
}

function showDeviceDialog(device?: DispatchableDevice) {
  if (device) {
    deviceDialog.isEdit = true
    currentEditId.value = device.id
    Object.assign(deviceForm, device)
  } else {
    deviceDialog.isEdit = false
    currentEditId.value = null
    Object.assign(deviceForm, {
      name: '',
      device_type: 'shiftable',
      rated_power: 0,
      priority: 5,
      is_active: true,
      run_duration: undefined,
      daily_runs: undefined,
      curtail_ratio: undefined,
      max_curtail_duration: undefined,
      min_power: undefined,
      max_power: undefined,
      ramp_rate: undefined,
      description: ''
    })
  }
  deviceDialog.visible = true
}

async function saveDevice() {
  loading.saveDevice = true
  try {
    if (deviceDialog.isEdit && currentEditId.value) {
      await updateDispatchableDevice(currentEditId.value, deviceForm)
      ElMessage.success('更新成功')
    } else {
      await createDispatchableDevice(deviceForm)
      ElMessage.success('创建成功')
    }
    deviceDialog.visible = false
    loadDevices()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    loading.saveDevice = false
  }
}

async function deleteDevice(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该设备?', '确认删除')
    await deleteDispatchableDevice(id)
    ElMessage.success('删除成功')
    loadDevices()
  } catch (e) {
    // 用户取消
  }
}

// ==================== 储能管理 ====================

async function loadStorage() {
  loading.storage = true
  try {
    const res = await getStorageSystems()
    storageSystems.value = res.data || []
  } catch (e) {
    console.error('加载储能失败', e)
  } finally {
    loading.storage = false
  }
}

function showStorageDialog(storage?: StorageConfig) {
  if (storage) {
    storageDialog.isEdit = true
    currentEditId.value = storage.id
    Object.assign(storageForm, {
      ...storage,
      soc_range: [storage.min_soc, storage.max_soc]
    })
  } else {
    storageDialog.isEdit = false
    currentEditId.value = null
    Object.assign(storageForm, {
      name: '',
      capacity: 0,
      max_charge_power: 0,
      max_discharge_power: 0,
      charge_efficiency: 0.95,
      discharge_efficiency: 0.95,
      soc_range: [0.1, 0.9],
      cycle_cost: 0.1,
      is_active: true,
      description: ''
    })
  }
  storageDialog.visible = true
}

async function saveStorage() {
  loading.saveStorage = true
  try {
    const data = {
      ...storageForm,
      min_soc: storageForm.soc_range[0],
      max_soc: storageForm.soc_range[1]
    }
    delete data.soc_range

    if (storageDialog.isEdit && currentEditId.value) {
      await updateStorageSystem(currentEditId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createStorageSystem(data)
      ElMessage.success('创建成功')
    }
    storageDialog.visible = false
    loadStorage()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    loading.saveStorage = false
  }
}

async function deleteStorage(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该储能系统?', '确认删除')
    await deleteStorageSystem(id)
    ElMessage.success('删除成功')
    loadStorage()
  } catch (e) {
    // 用户取消
  }
}

// ==================== 光伏管理 ====================

async function loadPV() {
  loading.pv = true
  try {
    const res = await getPVSystems()
    pvSystems.value = res.data || []
  } catch (e) {
    console.error('加载光伏失败', e)
  } finally {
    loading.pv = false
  }
}

function showPVDialog(pv?: PVConfig) {
  if (pv) {
    pvDialog.isEdit = true
    currentEditId.value = pv.id
    Object.assign(pvForm, pv)
  } else {
    pvDialog.isEdit = false
    currentEditId.value = null
    Object.assign(pvForm, {
      name: '',
      rated_capacity: 0,
      efficiency: 0.85,
      is_controllable: false,
      is_active: true,
      description: ''
    })
  }
  pvDialog.visible = true
}

async function savePV() {
  loading.savePV = true
  try {
    if (pvDialog.isEdit && currentEditId.value) {
      await updatePVSystem(currentEditId.value, pvForm)
      ElMessage.success('更新成功')
    } else {
      await createPVSystem(pvForm)
      ElMessage.success('创建成功')
    }
    pvDialog.visible = false
    loadPV()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    loading.savePV = false
  }
}

async function deletePV(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该光伏系统?', '确认删除')
    await deletePVSystem(id)
    ElMessage.success('删除成功')
    loadPV()
  } catch (e) {
    // 用户取消
  }
}
</script>

<style scoped lang="scss">
.dispatch-config {
  .empty-alert {
    margin-bottom: 20px;

    p {
      margin: 8px 0 0 0;
      color: var(--el-text-color-secondary);
    }
  }

  .config-header {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
  }

  .stats-row {
    margin-bottom: 20px;
    padding: 16px;
    background: var(--bg-card, rgba(255, 255, 255, 0.05));
    border-radius: 8px;
  }

  .type-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    height: 100%;

    .type-tag {
      font-size: 12px;
    }
  }
}

:deep(.el-form-item) {
  margin-bottom: 16px;
}

:deep(.el-divider) {
  margin: 16px 0;
}
</style>
