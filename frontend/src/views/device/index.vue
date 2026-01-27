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
          <el-select v-model="filters.point_type" placeholder="全部" clearable>
            <el-option label="AI-模拟量输入" value="AI" />
            <el-option label="DI-开关量输入" value="DI" />
            <el-option label="AO-模拟量输出" value="AO" />
            <el-option label="DO-开关量输出" value="DO" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="filters.device_type" placeholder="全部" clearable>
            <el-option label="温湿度" value="TH" />
            <el-option label="UPS" value="UPS" />
            <el-option label="配电" value="PDU" />
            <el-option label="空调" value="AC" />
            <el-option label="门禁" value="DOOR" />
            <el-option label="烟感" value="SMOKE" />
            <el-option label="漏水" value="WATER" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-select v-model="filters.area_code" placeholder="全部" clearable>
            <el-option label="A1区" value="A1" />
            <el-option label="A2区" value="A2" />
            <el-option label="B1区" value="B1" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadPoints">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 点位列表 -->
      <el-table :data="points" stripe border>
        <el-table-column prop="point_code" label="点位编码" width="150" />
        <el-table-column prop="point_name" label="点位名称" min-width="150" />
        <el-table-column prop="point_type" label="点位类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.point_type)" size="small">
              {{ row.point_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_type" label="设备类型" width="100" />
        <el-table-column prop="area_code" label="区域" width="80" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="collect_interval" label="采集周期" width="100">
          <template #default="{ row }">{{ row.collect_interval }}秒</template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
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
            <el-form-item label="设备类型" prop="device_type">
              <el-select v-model="form.device_type" :disabled="editMode">
                <el-option label="温湿度" value="TH" />
                <el-option label="UPS" value="UPS" />
                <el-option label="配电" value="PDU" />
                <el-option label="空调" value="AC" />
                <el-option label="门禁" value="DOOR" />
                <el-option label="烟感" value="SMOKE" />
                <el-option label="漏水" value="WATER" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getPoints, createPoint, updatePoint, deletePoint,
  enablePoint, disablePoint, type Point
} from '@/api/point'

const points = ref<Point[]>([])
const dialogVisible = ref(false)
const editMode = ref(false)
const formRef = ref()

const filters = reactive({
  point_type: '',
  device_type: '',
  area_code: ''
})

const form = reactive({
  id: 0,
  point_code: '',
  point_name: '',
  point_type: 'AI',
  device_type: 'TH',
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
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  area_code: [{ required: true, message: '请输入区域代码', trigger: 'blur' }]
}

onMounted(() => {
  loadPoints()
})

async function loadPoints() {
  try {
    const params = { ...filters }
    Object.keys(params).forEach(key => {
      if (!params[key as keyof typeof params]) {
        delete params[key as keyof typeof params]
      }
    })
    const result = await getPoints(params)
    // 后端返回分页响应，需要取 items（如果是分页对象）或直接使用（如果是数组）
    points.value = Array.isArray(result) ? result : (result.items || result)
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

function resetFilters() {
  filters.point_type = ''
  filters.device_type = ''
  filters.area_code = ''
  loadPoints()
}

function handleAdd() {
  editMode.value = false
  Object.assign(form, {
    id: 0,
    point_code: '',
    point_name: '',
    point_type: 'AI',
    device_type: 'TH',
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
}
</style>
