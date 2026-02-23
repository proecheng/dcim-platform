<template>
  <div class="video-manage-page">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- NVR 管理 -->
      <el-tab-pane label="NVR管理" name="nvr">
        <el-card shadow="hover" class="table-card">
          <div class="section-header">
            <span class="section-title">NVR 设备列表</span>
            <div class="filter-bar">
              <el-button type="primary" :icon="Plus" @click="openNvrDialog()">新增NVR</el-button>
              <el-button :icon="Refresh" @click="loadNvrList">刷新</el-button>
            </div>
          </div>
          <el-table :data="nvrList" stripe border v-loading="loadingNvr" row-key="id">
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="ip_address" label="IP地址" width="150" />
            <el-table-column prop="port" label="端口" width="80" align="center" />
            <el-table-column prop="manufacturer" label="厂商" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer || '-' }}</template>
            </el-table-column>
            <el-table-column prop="model" label="型号" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.model || '-' }}</template>
            </el-table-column>
            <el-table-column prop="max_channels" label="最大通道数" width="110" align="center">
              <template #default="{ row }">{{ row.max_channels ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="camera_count" label="摄像头数" width="100" align="center" />
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'online' ? 'success' : 'danger'">
                  {{ row.status === 'online' ? '在线' : '离线' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" :icon="Edit" link @click="openNvrDialog(row)">编辑</el-button>
                <el-button type="danger" size="small" :icon="Delete" link @click="handleDeleteNvr(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="nvrPage.page"
            v-model:page-size="nvrPage.pageSize"
            :total="nvrPage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadNvrList"
            @current-change="loadNvrList"
          />
        </el-card>
      </el-tab-pane>

      <!-- 摄像头管理 -->
      <el-tab-pane label="摄像头管理" name="camera">
        <el-card shadow="hover" class="table-card">
          <div class="section-header">
            <span class="section-title">摄像头列表</span>
            <div class="filter-bar">
              <el-select v-model="camFilter.nvr_id" placeholder="关联NVR" clearable style="width: 160px" @change="loadCameraList">
                <el-option v-for="n in nvrOptions" :key="n.id" :label="n.name" :value="n.id" />
              </el-select>
              <el-input v-model="camFilter.area_code" placeholder="区域" clearable style="width: 120px" @clear="loadCameraList" @keyup.enter="loadCameraList" />
              <el-select v-model="camFilter.status" placeholder="状态" clearable style="width: 120px" @change="loadCameraList">
                <el-option label="在线" value="online" />
                <el-option label="离线" value="offline" />
                <el-option label="未知" value="unknown" />
              </el-select>
              <el-button type="primary" :icon="Plus" @click="openCamDialog()">新增摄像头</el-button>
              <el-button :icon="Refresh" @click="loadCameraList">刷新</el-button>
            </div>
          </div>
          <el-table :data="cameraList" stripe border v-loading="loadingCam" row-key="id">
            <el-table-column prop="code" label="编码" width="130" show-overflow-tooltip />
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="camera_type" label="类型" width="80" align="center">
              <template #default="{ row }">{{ cameraTypeMap[row.camera_type] || row.camera_type }}</template>
            </el-table-column>
            <el-table-column prop="rtsp_url" label="RTSP地址" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.rtsp_url || '-' }}</template>
            </el-table-column>
            <el-table-column prop="nvr_name" label="关联NVR" width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.nvr_name || '-' }}</template>
            </el-table-column>
            <el-table-column prop="area_code" label="区域" width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.area_code || '-' }}</template>
            </el-table-column>
            <el-table-column prop="location_description" label="位置描述" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.location_description || '-' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" :icon="Edit" link @click="openCamDialog(row)">编辑</el-button>
                <el-button type="danger" size="small" :icon="Delete" link @click="handleDeleteCam(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="camPage.page"
            v-model:page-size="camPage.pageSize"
            :total="camPage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadCameraList"
            @current-change="loadCameraList"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- NVR 新增/编辑对话框 -->
    <el-dialog append-to-body v-model="nvrDialogVisible" :title="nvrForm.id ? '编辑NVR' : '新增NVR'" width="560px">
      <el-form ref="nvrFormRef" :model="nvrForm" :rules="nvrRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="nvrForm.name" placeholder="请输入NVR名称" />
        </el-form-item>
        <el-form-item label="IP地址" prop="ip_address">
          <el-input v-model="nvrForm.ip_address" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="nvrForm.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="nvrForm.username" placeholder="NVR登录用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="nvrForm.password" type="password" show-password placeholder="NVR登录密码" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="nvrForm.manufacturer" placeholder="如 海康威视" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="nvrForm.model" placeholder="如 DS-7608N" />
        </el-form-item>
        <el-form-item label="最大通道数">
          <el-input-number v-model="nvrForm.max_channels" :min="1" :max="128" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="nvrForm.description" type="textarea" :rows="2" placeholder="备注说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nvrDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingNvr" @click="handleSaveNvr">确定</el-button>
      </template>
    </el-dialog>

    <!-- 摄像头 新增/编辑对话框 -->
    <el-dialog append-to-body v-model="camDialogVisible" :title="camForm.id ? '编辑摄像头' : '新增摄像头'" width="640px">
      <el-form ref="camFormRef" :model="camForm" :rules="camRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="camForm.name" placeholder="摄像头名称" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="camForm.code" placeholder="唯一编码" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="camForm.camera_type" style="width: 100%">
            <el-option label="球机" value="dome" />
            <el-option label="枪机" value="bullet" />
            <el-option label="云台" value="ptz" />
          </el-select>
        </el-form-item>
        <el-form-item label="RTSP地址">
          <el-input v-model="camForm.rtsp_url" placeholder="rtsp://..." />
        </el-form-item>
        <el-form-item label="ONVIF地址">
          <el-input v-model="camForm.onvif_url" placeholder="http://..." />
        </el-form-item>
        <el-form-item label="HLS地址">
          <el-input v-model="camForm.hls_url" placeholder="http://..." />
        </el-form-item>
        <el-form-item label="关联NVR">
          <el-select v-model="camForm.nvr_id" clearable placeholder="选择NVR" style="width: 100%">
            <el-option v-for="n in nvrOptions" :key="n.id" :label="n.name" :value="n.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="通道号">
          <el-input-number v-model="camForm.channel_no" :min="1" :max="128" style="width: 100%" />
        </el-form-item>
        <el-form-item label="区域编码">
          <el-input v-model="camForm.area_code" placeholder="如 A-01" />
        </el-form-item>
        <el-form-item label="机柜ID">
          <el-input-number v-model="camForm.cabinet_id" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="设备ID">
          <el-input-number v-model="camForm.device_id" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="位置描述">
          <el-input v-model="camForm.location_description" placeholder="安装位置描述" />
        </el-form-item>

        <!-- 预置位 -->
        <el-divider content-position="left">预置位</el-divider>
        <div v-for="(preset, idx) in camForm.presets" :key="idx" class="preset-row">
          <el-form-item :label="`预置位 ${idx + 1}`" class="preset-item">
            <div class="preset-fields">
              <el-input-number v-model="preset.preset_index" :min="1" placeholder="序号" style="width: 90px" />
              <el-input v-model="preset.name" placeholder="名称" style="width: 140px" />
              <el-input v-model="preset.description" placeholder="描述" style="flex: 1" />
              <el-button type="danger" :icon="Delete" link @click="camForm.presets.splice(idx, 1)" />
            </div>
          </el-form-item>
        </div>
        <el-button type="primary" link :icon="Plus" @click="addPreset">添加预置位</el-button>
      </el-form>
      <template #footer>
        <el-button @click="camDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCam" @click="handleSaveCam">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getNVRList,
  createNVR,
  updateNVR,
  deleteNVR,
  getCameraList,
  createCamera,
  updateCamera,
  deleteCamera,
} from '@/api/modules/video'
import type {
  NVRItem,
  NVRCreateParams,
  NVRUpdateParams,
  CameraItem,
  CameraCreateParams,
  CameraUpdateParams,
  CameraPresetCreate,
} from '@/api/modules/video'
import type { FormInstance, FormRules } from 'element-plus'

// ==================== 常量 ====================
const cameraTypeMap: Record<string, string> = { dome: '球机', bullet: '枪机', ptz: '云台' }

// ==================== Tab ====================
const activeTab = ref('nvr')

function handleTabChange(tab: string) {
  if (tab === 'nvr') loadNvrList()
  else if (tab === 'camera') { loadNvrOptions(); loadCameraList() }
}

// ==================== NVR 列表 ====================
const loadingNvr = ref(false)
const nvrList = ref<NVRItem[]>([])
const nvrPage = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadNvrList() {
  loadingNvr.value = true
  try {
    const res = await getNVRList({ page: nvrPage.page, page_size: nvrPage.pageSize })
    nvrList.value = res.items || []
    nvrPage.total = res.total || 0
  } catch {
    ElMessage.error('加载NVR列表失败')
  } finally {
    loadingNvr.value = false
  }
}

// ==================== NVR 对话框 ====================
const nvrDialogVisible = ref(false)
const savingNvr = ref(false)
const nvrFormRef = ref<FormInstance>()

interface NvrFormState {
  id: number | null
  name: string
  ip_address: string
  port: number
  username: string
  password: string
  manufacturer: string
  model: string
  max_channels: number
  description: string
}

const nvrFormDefault: NvrFormState = {
  id: null, name: '', ip_address: '', port: 554, username: '', password: '',
  manufacturer: '', model: '', max_channels: 8, description: '',
}
const nvrForm = reactive<NvrFormState>({ ...nvrFormDefault })

const nvrRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  ip_address: [{ required: true, message: '请输入IP地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
}

function openNvrDialog(row?: NVRItem) {
  Object.assign(nvrForm, nvrFormDefault)
  if (row) {
    nvrForm.id = row.id
    nvrForm.name = row.name
    nvrForm.ip_address = row.ip_address
    nvrForm.port = row.port
    nvrForm.username = row.username || ''
    nvrForm.password = ''
    nvrForm.manufacturer = row.manufacturer || ''
    nvrForm.model = row.model || ''
    nvrForm.max_channels = row.max_channels ?? 8
    nvrForm.description = row.description || ''
  }
  nvrDialogVisible.value = true
}

async function handleSaveNvr() {
  const valid = await nvrFormRef.value?.validate().catch(() => false)
  if (!valid) return
  savingNvr.value = true
  try {
    if (nvrForm.id) {
      const data: NVRUpdateParams = {
        name: nvrForm.name, ip_address: nvrForm.ip_address, port: nvrForm.port,
        username: nvrForm.username || undefined, manufacturer: nvrForm.manufacturer || undefined,
        model: nvrForm.model || undefined, max_channels: nvrForm.max_channels,
        description: nvrForm.description || undefined,
      }
      if (nvrForm.password) data.password = nvrForm.password
      await updateNVR(nvrForm.id, data)
      ElMessage.success('更新成功')
    } else {
      const data: NVRCreateParams = {
        name: nvrForm.name, ip_address: nvrForm.ip_address, port: nvrForm.port,
        username: nvrForm.username || undefined, password: nvrForm.password || undefined,
        manufacturer: nvrForm.manufacturer || undefined, model: nvrForm.model || undefined,
        max_channels: nvrForm.max_channels, description: nvrForm.description || undefined,
      }
      await createNVR(data)
      ElMessage.success('创建成功')
    }
    nvrDialogVisible.value = false
    loadNvrList()
  } catch {
    ElMessage.error(nvrForm.id ? '更新失败' : '创建失败')
  } finally {
    savingNvr.value = false
  }
}

async function handleDeleteNvr(row: NVRItem) {
  try {
    await ElMessageBox.confirm(`确认删除NVR「${row.name}」？关联的摄像头将解除绑定。`, '删除确认', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteNVR(row.id)
    ElMessage.success('删除成功')
    loadNvrList()
  } catch (e: unknown) {
    if (e !== 'cancel' && String(e) !== 'cancel') ElMessage.error('删除失败')
  }
}

// ==================== NVR 下拉选项 ====================
const nvrOptions = ref<NVRItem[]>([])

async function loadNvrOptions() {
  try {
    const res = await getNVRList({ page: 1, page_size: 200 })
    nvrOptions.value = res.items || []
  } catch { /* 静默 */ }
}

// ==================== 摄像头列表 ====================
const loadingCam = ref(false)
const cameraList = ref<CameraItem[]>([])
const camPage = reactive({ page: 1, pageSize: 20, total: 0 })
const camFilter = reactive({ nvr_id: undefined as number | undefined, area_code: '', status: '' })

async function loadCameraList() {
  loadingCam.value = true
  try {
    const params: Record<string, unknown> = { page: camPage.page, page_size: camPage.pageSize }
    if (camFilter.nvr_id) params.nvr_id = camFilter.nvr_id
    if (camFilter.area_code) params.area_code = camFilter.area_code
    if (camFilter.status) params.status = camFilter.status
    const res = await getCameraList(params as Parameters<typeof getCameraList>[0])
    cameraList.value = res.items || []
    camPage.total = res.total || 0
  } catch {
    ElMessage.error('加载摄像头列表失败')
  } finally {
    loadingCam.value = false
  }
}

// ==================== 摄像头对话框 ====================
const camDialogVisible = ref(false)
const savingCam = ref(false)
const camFormRef = ref<FormInstance>()

interface CamFormState {
  id: number | null
  name: string
  code: string
  camera_type: string
  rtsp_url: string
  onvif_url: string
  hls_url: string
  nvr_id: number | undefined
  channel_no: number | undefined
  area_code: string
  cabinet_id: number | undefined
  device_id: number | undefined
  location_description: string
  presets: CameraPresetCreate[]
}

const camFormDefault: CamFormState = {
  id: null, name: '', code: '', camera_type: 'dome', rtsp_url: '', onvif_url: '', hls_url: '',
  nvr_id: undefined, channel_no: undefined, area_code: '', cabinet_id: undefined,
  device_id: undefined, location_description: '', presets: [],
}
const camForm = reactive<CamFormState>({ ...camFormDefault })

const camRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
}

function openCamDialog(row?: CameraItem) {
  Object.assign(camForm, { ...camFormDefault, presets: [] })
  if (row) {
    camForm.id = row.id
    camForm.name = row.name
    camForm.code = row.code
    camForm.camera_type = row.camera_type
    camForm.rtsp_url = row.rtsp_url || ''
    camForm.onvif_url = row.onvif_url || ''
    camForm.hls_url = row.hls_url || ''
    camForm.nvr_id = row.nvr_id ?? undefined
    camForm.channel_no = row.channel_no ?? undefined
    camForm.area_code = row.area_code || ''
    camForm.cabinet_id = row.cabinet_id ?? undefined
    camForm.device_id = row.device_id ?? undefined
    camForm.location_description = row.location_description || ''
    camForm.presets = (row.presets || []).map(p => ({
      preset_index: p.preset_index, name: p.name, description: p.description || '',
    }))
  }
  loadNvrOptions()
  camDialogVisible.value = true
}

function addPreset() {
  camForm.presets.push({ preset_index: camForm.presets.length + 1, name: '', description: '' })
}

async function handleSaveCam() {
  const valid = await camFormRef.value?.validate().catch(() => false)
  if (!valid) return
  savingCam.value = true
  try {
    const presets = camForm.presets.filter(p => p.name.trim())
    if (camForm.id) {
      const data: CameraUpdateParams = {
        name: camForm.name, code: camForm.code, camera_type: camForm.camera_type,
        rtsp_url: camForm.rtsp_url || undefined, onvif_url: camForm.onvif_url || undefined,
        hls_url: camForm.hls_url || undefined, nvr_id: camForm.nvr_id ?? null,
        channel_no: camForm.channel_no ?? null, area_code: camForm.area_code || null,
        cabinet_id: camForm.cabinet_id ?? null, device_id: camForm.device_id ?? null,
        location_description: camForm.location_description || undefined, presets,
      }
      await updateCamera(camForm.id, data)
      ElMessage.success('更新成功')
    } else {
      const data: CameraCreateParams = {
        name: camForm.name, code: camForm.code, camera_type: camForm.camera_type,
        rtsp_url: camForm.rtsp_url || undefined, onvif_url: camForm.onvif_url || undefined,
        hls_url: camForm.hls_url || undefined, nvr_id: camForm.nvr_id,
        channel_no: camForm.channel_no, area_code: camForm.area_code || undefined,
        cabinet_id: camForm.cabinet_id, device_id: camForm.device_id,
        location_description: camForm.location_description || undefined, presets,
      }
      await createCamera(data)
      ElMessage.success('创建成功')
    }
    camDialogVisible.value = false
    loadCameraList()
  } catch {
    ElMessage.error(camForm.id ? '更新失败' : '创建失败')
  } finally {
    savingCam.value = false
  }
}

async function handleDeleteCam(row: CameraItem) {
  try {
    await ElMessageBox.confirm(`确认删除摄像头「${row.name}」？`, '删除确认', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteCamera(row.id)
    ElMessage.success('删除成功')
    loadCameraList()
  } catch (e: unknown) {
    if (e !== 'cancel' && String(e) !== 'cancel') ElMessage.error('删除失败')
  }
}

// ==================== 辅助函数 ====================
type TagType = 'success' | 'warning' | 'info' | 'danger'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { online: 'success', offline: 'danger', unknown: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { online: '在线', offline: '离线', unknown: '未知' }
  return map[status] || status
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadNvrList()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.video-manage-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.preset-row {
  .preset-item {
    margin-bottom: 8px;
  }
}

.preset-fields {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
</style>
