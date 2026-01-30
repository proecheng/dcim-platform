<template>
  <div class="device-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>点位管理</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增点位</el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="点位类型">
          <el-select v-model="filters.point_type" style="width: 150px">
            <el-option label="全部" value="ALL" />
            <el-option label="AI-模拟量输入" value="AI" />
            <el-option label="DI-开关量输入" value="DI" />
            <el-option label="AO-模拟量输出" value="AO" />
            <el-option label="DO-开关量输出" value="DO" />
          </el-select>
        </el-form-item>
        <el-form-item label="用途">
          <el-select v-model="filters.device_type" style="width: 150px">
            <el-option label="全部" value="ALL" />
            <el-option label="功率" value="power" />
            <el-option label="电流" value="current" />
            <el-option label="电能" value="energy" />
            <el-option label="电压" value="voltage" />
            <el-option label="功率因数" value="power_factor" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-select v-model="filters.area_code" style="width: 120px">
            <el-option label="全部" value="ALL" />
            <el-option label="A1区" value="A1" />
            <el-option label="A2区" value="A2" />
            <el-option label="B1区" value="B1" />
            <el-option label="F1区" value="F1" />
            <el-option label="F2区" value="F2" />
            <el-option label="F3区" value="F3" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索点位名称..."
            clearable
            style="width: 220px;"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 分页信息栏 -->
      <div class="pagination-bar">
        <span class="pagination-info">
          共 <strong>{{ total }}</strong> 条记录，第 <strong>{{ currentPage }}</strong> / <strong>{{ totalPages }}</strong> 页
        </span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>

      <!-- 点位列表 -->
      <el-table :data="points" stripe border style="width: 100%" table-layout="auto">
        <el-table-column prop="point_code" label="点位编码" width="180" />
        <el-table-column prop="point_name" label="点位名称" min-width="140" />
        <el-table-column prop="point_type" label="点位类型" width="80">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.point_type)" size="small">
              {{ row.point_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_type" label="用途" width="80" />
        <el-table-column prop="area_code" label="区域" width="60" />
        <el-table-column label="关联设备" min-width="75">
          <template #default="{ row }">
            <div v-if="row.energy_device_name" class="linked-device-cell">
              <span class="linked-device">{{ row.energy_device_name }}</span>
              <span class="unlink-btn" @click="handleUnlink(row)">取消关联</span>
            </div>
            <span v-else class="link-btn" @click="handleLink(row)">关联设备</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="collect_interval" label="采集周期" width="160">
          <template #default="{ row }">{{ row.collect_interval }}秒</template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="状态" width="70">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除该点位？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑点位' : '新增点位'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="点位编码" prop="point_code">
          <el-input v-model="form.point_code" :disabled="editMode" />
        </el-form-item>
        <el-form-item label="点位名称" prop="point_name">
          <el-input v-model="form.point_name" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="点位类型" prop="point_type">
              <el-select v-model="form.point_type" :disabled="editMode">
                <el-option label="AI-模拟量输入" value="AI" />
                <el-option label="DI-开关量输入" value="DI" />
                <el-option label="AO-模拟量输出" value="AO" />
                <el-option label="DO-开关量输出" value="DO" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用途" prop="device_type">
              <el-select v-model="form.device_type" :disabled="editMode">
                <el-option label="功率" value="power" />
                <el-option label="电流" value="current" />
                <el-option label="电能" value="energy" />
                <el-option label="电压" value="voltage" />
                <el-option label="功率因数" value="power_factor" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="区域代码" prop="area_code">
              <el-input v-model="form.area_code" :disabled="editMode" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="form.unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="量程最小值">
              <el-input-number v-model="form.min_range" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="量程最大值">
              <el-input-number v-model="form.max_range" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="采集周期">
          <el-input-number v-model="form.collect_interval" :min="1" />
          <span style="margin-left: 8px;">秒</span>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 关联设备对话框 -->
    <el-dialog v-model="linkDialogVisible" title="关联用能设备" width="650px">
      <div class="link-dialog-content">
        <el-input
          v-model="deviceSearchKeyword"
          placeholder="输入设备编码或名称搜索"
          clearable
          @input="onSearchInput"
          style="margin-bottom: 12px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-table
          :data="deviceSearchResults"
          highlight-current-row
          @current-change="onDeviceSelect"
          max-height="320"
          border
          size="small"
        >
          <el-table-column prop="device_code" label="设备编码" width="130" />
          <el-table-column prop="device_name" label="设备名称" min-width="140" />
          <el-table-column prop="device_type" label="类型" width="80" />
          <el-table-column prop="area_code" label="区域" width="70" />
        </el-table>

        <div v-if="selectedDevice" class="selected-tip">
          已选择: <strong>{{ selectedDevice.device_name }}</strong> ({{ selectedDevice.device_code }})
        </div>
      </div>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedDevice" @click="confirmLink">确定关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getPoints, createPoint, updatePoint, deletePoint,
  enablePoint, disablePoint, linkPointToDevice, unlinkPointFromDevice,
  type Point
} from '@/api/point'
import { getPowerDevices, type PowerDevice } from '@/api/modules/energy'

const points = ref<Point[]>([])
const dialogVisible = ref(false)
const editMode = ref(false)
const formRef = ref()

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

const filters = reactive({
  point_type: 'ALL',
  device_type: 'ALL',
  area_code: 'ALL',
  keyword: ''
})

const form = reactive({
  id: 0,
  point_code: '',
  point_name: '',
  point_type: 'AI',
  device_type: 'power',
  area_code: 'A1',
  unit: '',
  data_type: 'float',
  min_range: null as number | null,
  max_range: null as number | null,
  collect_interval: 10,
  description: ''
})

const rules = {
  point_code: [{ required: true, message: '请输入点位编码', trigger: 'blur' }],
  point_name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  point_type: [{ required: true, message: '请选择点位类型', trigger: 'change' }],
  device_type: [{ required: true, message: '请选择用途', trigger: 'change' }],
  area_code: [{ required: true, message: '请输入区域代码', trigger: 'blur' }]
}

// 关联设备相关状态
const linkDialogVisible = ref(false)
const linkingPoint = ref<Point | null>(null)
const deviceSearchKeyword = ref('')
const deviceSearchResults = ref<PowerDevice[]>([])
const selectedDevice = ref<PowerDevice | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  loadPoints()
})

async function loadPoints() {
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filters.point_type && filters.point_type !== 'ALL') {
      params.point_type = filters.point_type
    }
    if (filters.device_type && filters.device_type !== 'ALL') {
      params.device_type = filters.device_type
    }
    if (filters.area_code && filters.area_code !== 'ALL') {
      params.area_code = filters.area_code
    }
    if (filters.keyword && filters.keyword.trim()) {
      params.keyword = filters.keyword.trim()
    }
    const result = await getPoints(params)
    // 后端返回分页响应
    if (Array.isArray(result)) {
      points.value = result
      total.value = result.length
    } else {
      points.value = result.items || []
      total.value = result.total || 0
    }
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadPoints()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadPoints()
}

function handleSearch() {
  currentPage.value = 1
  loadPoints()
}

function resetFilters() {
  filters.point_type = 'ALL'
  filters.device_type = 'ALL'
  filters.area_code = 'ALL'
  filters.keyword = ''
  currentPage.value = 1
  loadPoints()
}

function handleAdd() {
  editMode.value = false
  Object.assign(form, {
    id: 0,
    point_code: '',
    point_name: '',
    point_type: 'AI',
    device_type: 'power',
    area_code: 'A1',
    unit: '',
    data_type: 'float',
    min_range: null,
    max_range: null,
    collect_interval: 10,
    description: ''
  })
  dialogVisible.value = true
}

function handleEdit(row: Point) {
  editMode.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  try {
    if (editMode.value) {
      await updatePoint(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createPoint(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadPoints()
  } catch (e) {
    console.error('操作失败', e)
  }
}

async function handleDelete(id: number) {
  try {
    await deletePoint(id)
    ElMessage.success('删除成功')
    loadPoints()
  } catch (e) {
    console.error('删除失败', e)
  }
}

async function handleToggle(row: Point) {
  try {
    if (row.is_enabled) {
      await enablePoint(row.id)
    } else {
      await disablePoint(row.id)
    }
    ElMessage.success(row.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.is_enabled = !row.is_enabled
    console.error('操作失败', e)
  }
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function getTypeTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    AI: 'primary',
    DI: 'success',
    AO: 'warning',
    DO: 'danger'
  }
  return map[type] || 'info'
}

// ====== 关联设备功能 ======

function handleLink(row: Point) {
  linkingPoint.value = row
  deviceSearchKeyword.value = ''
  deviceSearchResults.value = []
  selectedDevice.value = null
  linkDialogVisible.value = true
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchDevices()
  }, 300)
}

async function searchDevices() {
  const keyword = deviceSearchKeyword.value.trim()
  if (!keyword) {
    deviceSearchResults.value = []
    return
  }
  try {
    const res = await getPowerDevices({ keyword })
    const data = (res as any)?.data ?? res
    deviceSearchResults.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('搜索设备失败', e)
    deviceSearchResults.value = []
  }
}

function onDeviceSelect(row: PowerDevice | null) {
  selectedDevice.value = row
}

async function confirmLink() {
  if (!linkingPoint.value || !selectedDevice.value) return
  try {
    await linkPointToDevice(linkingPoint.value.id, selectedDevice.value.id)
    ElMessage.success('关联成功')
    linkDialogVisible.value = false
    loadPoints()
  } catch (e) {
    console.error('关联失败', e)
    ElMessage.error('关联失败')
  }
}

async function handleUnlink(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定取消点位 "${row.point_name}" 与设备 "${row.energy_device_name}" 的关联？`,
      '取消关联',
      { type: 'warning' }
    )
    await unlinkPointFromDevice(row.id)
    ElMessage.success('已取消关联')
    loadPoints()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('取消关联失败', e)
      ElMessage.error('取消关联失败')
    }
  }
}
</script>

<style scoped lang="scss">
.device-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .filter-form {
    margin-bottom: 20px;
  }

  .pagination-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding: 8px 12px;
    background: rgba(64, 158, 255, 0.05);
    border-radius: 4px;

    .pagination-info {
      font-size: 13px;
      color: #909399;

      strong {
        color: var(--el-color-primary);
        margin: 0 2px;
      }
    }
  }

  .linked-device {
    color: var(--el-color-primary);
    font-weight: 500;
  }

  .linked-device-cell {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  // 未关联 - 关联设备按钮：更亮更突出
  .link-btn {
    color: #67c23a;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.2s;

    &:hover {
      color: #85ce61;
      text-decoration: underline;
    }
  }

  // 已关联 - 取消关联按钮：小字、低调
  .unlink-btn {
    color: #909399;
    font-size: 12px;
    cursor: pointer;
    transition: color 0.2s;

    &:hover {
      color: #f56c6c;
    }
  }

  .no-link {
    color: var(--el-text-color-placeholder);
    font-style: italic;
  }

  .link-dialog-content {
    .selected-tip {
      margin-top: 12px;
      padding: 8px 12px;
      background: var(--el-color-primary-light-9);
      border-radius: 4px;
      font-size: 13px;
      color: var(--el-color-primary);
    }
  }
}
</style>
<!-- HMR trigger -->
