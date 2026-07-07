<template>
  <div class="asset-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff;">
            <el-icon :size="28"><Box /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.total_count || 0 }}</div>
            <div class="stat-label">资产总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a;">
            <el-icon :size="28"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.by_status?.in_use || 0 }}</div>
            <div class="stat-label">使用中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #909399;">
            <el-icon :size="28"><Coin /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.by_status?.in_stock || 0 }}</div>
            <div class="stat-label">库存中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6a23c;">
            <el-icon :size="28"><Tools /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.by_status?.maintenance || 0 }}</div>
            <div class="stat-label">维护中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="28"><Money /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ formatValue(statistics.total_value) }}</div>
            <div class="stat-label">资产总值</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="28"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.warranty_expiring_count || 0 }}</div>
            <div class="stat-label">即将过保</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 保修预警面板 -->
    <el-card class="warranty-alert-card" shadow="hover" v-if="warrantyAlerts.total_count > 0">
      <template #header>
        <div class="warranty-alert-header">
          <span>保修预警</span>
          <el-badge :value="warrantyAlerts.total_count" type="danger" />
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="alert-column alert-30">
            <div class="alert-title">
              <span>30天内到期</span>
              <el-badge :value="warrantyAlerts.within_30_days.length" type="danger" v-if="warrantyAlerts.within_30_days.length > 0" />
            </div>
            <div class="alert-list" v-if="warrantyAlerts.within_30_days.length > 0">
              <div
                class="alert-item"
                v-for="item in warrantyAlerts.within_30_days"
                :key="item.asset_id"
                @click="viewAlertAsset(item.asset_id)"
              >
                <div class="alert-item-name">{{ item.asset_name }}</div>
                <div class="alert-item-info">
                  <span>{{ item.asset_code }}</span>
                  <el-tag type="danger" size="small">{{ item.days_remaining }}天</el-tag>
                </div>
              </div>
            </div>
            <div class="alert-empty" v-else>无</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="alert-column alert-60">
            <div class="alert-title">
              <span>60天内到期</span>
              <el-badge :value="warrantyAlerts.within_60_days.length" type="warning" v-if="warrantyAlerts.within_60_days.length > 0" />
            </div>
            <div class="alert-list" v-if="warrantyAlerts.within_60_days.length > 0">
              <div
                class="alert-item"
                v-for="item in warrantyAlerts.within_60_days"
                :key="item.asset_id"
                @click="viewAlertAsset(item.asset_id)"
              >
                <div class="alert-item-name">{{ item.asset_name }}</div>
                <div class="alert-item-info">
                  <span>{{ item.asset_code }}</span>
                  <el-tag type="warning" size="small">{{ item.days_remaining }}天</el-tag>
                </div>
              </div>
            </div>
            <div class="alert-empty" v-else>无</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="alert-column alert-90">
            <div class="alert-title">
              <span>90天内到期</span>
              <el-badge :value="warrantyAlerts.within_90_days.length" type="info" v-if="warrantyAlerts.within_90_days.length > 0" />
            </div>
            <div class="alert-list" v-if="warrantyAlerts.within_90_days.length > 0">
              <div
                class="alert-item"
                v-for="item in warrantyAlerts.within_90_days"
                :key="item.asset_id"
                @click="viewAlertAsset(item.asset_id)"
              >
                <div class="alert-item-name">{{ item.asset_name }}</div>
                <div class="alert-item-info">
                  <span>{{ item.asset_code }}</span>
                  <el-tag type="info" size="small">{{ item.days_remaining }}天</el-tag>
                </div>
              </div>
            </div>
            <div class="alert-empty" v-else>无</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-filters">
          <el-select
            v-model="filters.asset_type"
            placeholder="资产类型"
            clearable
            style="width: 140px"
          >
            <el-option label="服务器" value="server" />
            <el-option label="网络设备" value="network" />
            <el-option label="存储设备" value="storage" />
            <el-option label="UPS" value="ups" />
            <el-option label="PDU" value="pdu" />
            <el-option label="空调" value="ac" />
            <el-option label="机柜" value="cabinet" />
            <el-option label="传感器" value="sensor" />
            <el-option label="其他" value="other" />
          </el-select>
          <el-select
            v-model="filters.status"
            placeholder="状态"
            clearable
            style="width: 120px"
          >
            <el-option label="库存" value="in_stock" />
            <el-option label="使用中" value="in_use" />
            <el-option label="借出" value="borrowed" />
            <el-option label="维护中" value="maintenance" />
            <el-option label="报废" value="scrapped" />
          </el-select>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索资产编码/名称"
            clearable
            style="width: 200px"
            :prefix-icon="Search"
            @keyup.enter="loadAssets"
          />
          <el-button type="primary" @click="loadAssets">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" :icon="Plus" @click="showAddDialog">新增资产</el-button>
          <el-button :icon="Upload" @click="importDialogVisible = true">导入</el-button>
          <el-button :icon="Download" @click="handleExport">导出</el-button>
        </div>
      </div>
    </el-card>

    <!-- 资产列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="assets" stripe border v-loading="loading">
        <el-table-column prop="asset_code" label="资产编码" width="140" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="asset_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.asset_type)" size="small">
              {{ getTypeName(row.asset_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="cabinet_name" label="所在机柜" width="120" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="100" />
        <el-table-column prop="warranty_status" label="保修状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.warranty_status === 'valid' ? 'success' : row.warranty_status === 'expiring' ? 'warning' : 'danger'"
              size="small"
            >
              {{ row.warranty_status === 'valid' ? '在保' : row.warranty_status === 'expiring' ? '即将过保' : '已过保' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewAsset(row)">查看</el-button>
            <el-button type="primary" link @click="editAsset(row)">编辑</el-button>
            <el-button type="warning" link @click="showMaintenanceDialog(row)">维护</el-button>
            <el-button type="danger" link @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadAssets"
          @current-change="loadAssets"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog append-to-body
      v-model="dialogVisible"
      :title="isEdit ? '编辑资产' : '新增资产'"
      width="700px"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产编码" prop="asset_code">
              <el-input v-model="form.asset_code" :disabled="isEdit" placeholder="请输入资产编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产名称" prop="asset_name">
              <el-input v-model="form.asset_name" placeholder="请输入资产名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产类型" prop="asset_type">
              <el-select v-model="form.asset_type" placeholder="请选择类型" style="width: 100%">
                <el-option label="服务器" value="server" />
                <el-option label="网络设备" value="network" />
                <el-option label="存储设备" value="storage" />
                <el-option label="UPS" value="ups" />
                <el-option label="PDU" value="pdu" />
                <el-option label="空调" value="ac" />
                <el-option label="机柜" value="cabinet" />
                <el-option label="传感器" value="sensor" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择状态" style="width: 100%">
                <el-option label="库存" value="in_stock" />
                <el-option label="使用中" value="in_use" />
                <el-option label="借出" value="borrowed" />
                <el-option label="维护中" value="maintenance" />
                <el-option label="报废" value="scrapped" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="品牌" prop="brand">
              <el-input v-model="form.brand" placeholder="请输入品牌" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号" prop="model">
              <el-input v-model="form.model" placeholder="请输入型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号" prop="serial_number">
              <el-input v-model="form.serial_number" placeholder="请输入序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人" prop="owner">
              <el-input v-model="form.owner" placeholder="请输入负责人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier">
              <el-input v-model="form.supplier" placeholder="请输入供应商" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="购买日期" prop="purchase_date">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                placeholder="选择购买日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购买价格" prop="purchase_price">
              <el-input-number
                v-model="form.purchase_price"
                :min="0"
                :precision="2"
                placeholder="请输入价格"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="保修开始" prop="warranty_start">
              <el-date-picker
                v-model="form.warranty_start"
                type="date"
                placeholder="选择保修开始日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保修结束" prop="warranty_end">
              <el-date-picker
                v-model="form.warranty_end"
                type="date"
                placeholder="选择保修结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="remark">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 维护记录对话框 -->
    <el-dialog append-to-body
      v-model="maintenanceDialogVisible"
      title="新建维护记录"
      width="500px"
    >
      <el-form
        ref="maintenanceFormRef"
        :model="maintenanceForm"
        :rules="maintenanceRules"
        label-width="100px"
      >
        <el-form-item label="资产">
          <el-input :value="currentAsset?.asset_name" disabled />
        </el-form-item>
        <el-form-item label="维护类型" prop="maintenance_type">
          <el-select v-model="maintenanceForm.maintenance_type" placeholder="请选择维护类型" style="width: 100%">
            <el-option label="定期维护" value="routine" />
            <el-option label="故障维修" value="repair" />
            <el-option label="升级更新" value="upgrade" />
            <el-option label="巡检" value="inspection" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护日期" prop="start_time">
          <el-date-picker
            v-model="maintenanceForm.start_time"
            type="date"
            placeholder="选择维护日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="维护人员" prop="technician">
          <el-input v-model="maintenanceForm.technician" placeholder="请输入维护人员" />
        </el-form-item>
        <el-form-item label="维护费用" prop="cost">
          <el-input-number
            v-model="maintenanceForm.cost"
            :min="0"
            :precision="2"
            placeholder="请输入费用"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="维护描述" prop="description">
          <el-input
            v-model="maintenanceForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入维护描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="maintenanceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMaintenance" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog append-to-body
      v-model="importDialogVisible"
      title="批量导入资产"
      width="650px"
      @closed="resetImport"
    >
      <div class="import-section">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".xlsx,.xls"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          drag
        >
          <el-icon :size="40" style="color: #909399;"><Upload /></el-icon>
          <div style="margin-top: 8px;">将文件拖到此处，或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              仅支持 .xlsx / .xls 格式，
              <el-button type="primary" link @click.stop="handleDownloadTemplate">下载导入模板</el-button>
            </div>
          </template>
        </el-upload>
      </div>

      <!-- 预校验结果 -->
      <div v-if="importResult" class="import-result">
        <el-alert
          :title="`校验完成：成功 ${importResult.success_count} 条，失败 ${importResult.error_count} 条`"
          :type="importResult.error_count > 0 ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 12px;"
        />
        <el-table
          v-if="importResult.errors && importResult.errors.length > 0"
          :data="importResult.errors"
          border
          size="small"
          max-height="250"
        >
          <el-table-column prop="row" label="行号" width="70" />
          <el-table-column prop="field" label="字段" width="120" />
          <el-table-column prop="message" label="错误信息" />
        </el-table>
      </div>

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="importLoading"
          :disabled="!importFile"
          @click="handlePreview"
        >
          预校验
        </el-button>
        <el-button
          type="success"
          :loading="importLoading"
          :disabled="!importResult || importResult.success_count === 0"
          @click="handleConfirmImport"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 资产详情对话框 -->
    <el-dialog append-to-body
      v-model="detailDialogVisible"
      title="资产详情"
      width="800px"
    >
      <el-tabs v-model="detailActiveTab">
        <el-tab-pane label="基本信息" name="info">
          <el-descriptions :column="2" border v-if="detailAsset">
            <el-descriptions-item label="资产编码">{{ detailAsset.asset_code }}</el-descriptions-item>
            <el-descriptions-item label="资产名称">{{ detailAsset.asset_name }}</el-descriptions-item>
            <el-descriptions-item label="资产类型">{{ getTypeName(detailAsset.asset_type) }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(detailAsset.status)" size="small">{{ getStatusName(detailAsset.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="品牌">{{ detailAsset.brand || '-' }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ detailAsset.model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ detailAsset.serial_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所在机柜">{{ detailAsset.cabinet_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ detailAsset.owner || '-' }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ detailAsset.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="保修开始">{{ detailAsset.warranty_start || '-' }}</el-descriptions-item>
            <el-descriptions-item label="保修结束">{{ detailAsset.warranty_end || '-' }}</el-descriptions-item>
            <el-descriptions-item label="供应商">{{ detailAsset.supplier || '-' }}</el-descriptions-item>
            <el-descriptions-item label="采购价格">{{ detailAsset.purchase_price ? '¥' + detailAsset.purchase_price : '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="生命周期" name="lifecycle" lazy>
          <LifecycleTimeline v-if="detailAsset" :asset-id="detailAsset.id" />
        </el-tab-pane>
        <el-tab-pane label="维护记录" name="maintenance" lazy>
          <div v-loading="maintenanceLoading">
            <el-table :data="maintenanceRecords" border size="small" v-if="maintenanceRecords.length > 0">
              <el-table-column prop="maintenance_type" label="类型" width="100">
                <template #default="{ row }">
                  {{ { routine: '定期维护', repair: '故障维修', upgrade: '升级更新', inspection: '巡检' }[row.maintenance_type as string] || row.maintenance_type }}
                </template>
              </el-table-column>
              <el-table-column prop="start_time" label="开始时间" width="160" />
              <el-table-column prop="end_time" label="结束时间" width="160" />
              <el-table-column prop="technician" label="维护人员" width="100" />
              <el-table-column prop="description" label="描述" />
              <el-table-column prop="result" label="结果" width="120" />
              <el-table-column prop="cost" label="费用" width="100">
                <template #default="{ row }">
                  {{ row.cost ? '¥' + row.cost : '-' }}
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无维护记录" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  Plus, Upload, Download, Search,
  Box, CircleCheck, Coin, Tools, Money, Warning
} from '@element-plus/icons-vue'
import {
  getAssets, getAsset, createAsset, updateAsset, deleteAsset,
  getAssetStatistics, createMaintenance,
  getMaintenanceRecords, getWarrantyAlerts,
  importAssets, exportAssets, downloadImportTemplate,
  type Asset, type AssetType, type AssetStatus, type AssetStatistics,
  type WarrantyAlertResponse
} from '@/api/modules/asset'
import LifecycleTimeline from '@/components/asset/LifecycleTimeline.vue'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const assets = ref<Asset[]>([])
const statistics = ref<Partial<AssetStatistics>>({})

// 筛选条件
const filters = reactive({
  asset_type: '' as AssetType | '',
  status: '' as AssetStatus | '',
  keyword: ''
})

// 分页
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 对话框状态
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const currentAssetId = ref<number | null>(null)

// 表单数据
const form = reactive({
  asset_code: '',
  asset_name: '',
  asset_type: '' as AssetType | '',
  status: 'in_stock' as AssetStatus,
  brand: '',
  model: '',
  serial_number: '',
  owner: '',
  department: '',
  supplier: '',
  purchase_date: '',
  purchase_price: undefined as number | undefined,
  warranty_start: '',
  warranty_end: '',
  remark: ''
})

// 表单校验规则
const formRules = {
  asset_code: [{ required: true, message: '请输入资产编码', trigger: 'blur' }],
  asset_name: [{ required: true, message: '请输入资产名称', trigger: 'blur' }],
  asset_type: [{ required: true, message: '请选择资产类型', trigger: 'change' }]
}

// 维护记录对话框
const maintenanceDialogVisible = ref(false)
const maintenanceFormRef = ref<FormInstance>()
const currentAsset = ref<Asset | null>(null)

const maintenanceForm = reactive({
  maintenance_type: '',
  start_time: '',
  technician: '',
  cost: undefined as number | undefined,
  description: ''
})

const maintenanceRules = {
  maintenance_type: [{ required: true, message: '请选择维护类型', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择维护日期', trigger: 'change' }],
  description: [{ required: true, message: '请输入维护描述', trigger: 'blur' }]
}

// 详情对话框
const detailDialogVisible = ref(false)
const detailActiveTab = ref('info')
const detailAsset = ref<Asset | null>(null)
const maintenanceLoading = ref(false)
const maintenanceRecords = ref<any[]>([])

// 保修预警
const warrantyAlerts = ref<WarrantyAlertResponse>({
  within_30_days: [],
  within_60_days: [],
  within_90_days: [],
  total_count: 0
})

// 初始化加载
onMounted(() => {
  loadAssets()
  loadStatistics()
  loadWarrantyAlerts()
})

// 加载资产列表
async function loadAssets() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      skip: (pagination.page - 1) * pagination.page_size,
      limit: pagination.page_size
    }
    if (filters.asset_type) params.asset_type = filters.asset_type
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    const res = await getAssets(params)
    // 响应拦截器已解包 response.data，res 即后端返回的数据本体
    if (Array.isArray(res)) {
      assets.value = res as unknown as Asset[]
      pagination.total = res.length
    } else if (res && typeof res === 'object') {
      assets.value = (res as any).items || (res as any).data || []
      pagination.total = (res as any).total || assets.value.length
    }
  } catch (e) {
    console.error('加载资产列表失败', e)
    ElMessage.error('加载资产列表失败')
    assets.value = []
  } finally {
    loading.value = false
  }
}

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getAssetStatistics()
    // 响应拦截器已解包，res 即 AssetStatistics 对象
    if (res && typeof res === 'object') {
      const data = (res as any).data || res
      statistics.value = data
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
    // API 失败时使用兜底默认值，保证卡片不显示异常
    statistics.value = {
      total_count: 0,
      by_status: {},
      by_type: {},
      by_department: {},
      total_value: 0,
      warranty_expiring_count: 0
    }
  }
}

// 重置筛选条件
function resetFilters() {
  filters.asset_type = ''
  filters.status = ''
  filters.keyword = ''
  pagination.page = 1
  loadAssets()
}

// 显示新增对话框
function showAddDialog() {
  isEdit.value = false
  currentAssetId.value = null
  resetForm()
  dialogVisible.value = true
}

// 编辑资产
function editAsset(row: Asset) {
  isEdit.value = true
  currentAssetId.value = row.id
  Object.assign(form, {
    asset_code: row.asset_code,
    asset_name: row.asset_name,
    asset_type: row.asset_type,
    status: row.status,
    brand: row.brand || '',
    model: row.model || '',
    serial_number: row.serial_number || '',
    owner: row.owner || '',
    department: row.department || '',
    supplier: row.supplier || '',
    purchase_date: row.purchase_date || '',
    purchase_price: row.purchase_price,
    warranty_start: row.warranty_start || '',
    warranty_end: row.warranty_end || '',
    remark: row.remark || ''
  })
  dialogVisible.value = true
}

// 查看资产详情
async function viewAsset(row: Asset) {
  detailAsset.value = row
  detailActiveTab.value = 'info'
  maintenanceRecords.value = []
  detailDialogVisible.value = true
}

// 显示维护记录对话框
function showMaintenanceDialog(row: Asset) {
  currentAsset.value = row
  maintenanceForm.maintenance_type = ''
  maintenanceForm.start_time = ''
  maintenanceForm.technician = ''
  maintenanceForm.cost = undefined
  maintenanceForm.description = ''
  maintenanceDialogVisible.value = true
}

// 提交表单
async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      asset_code: form.asset_code,
      asset_name: form.asset_name,
      asset_type: form.asset_type as AssetType,
      status: form.status,
      brand: form.brand || undefined,
      model: form.model || undefined,
      serial_number: form.serial_number || undefined,
      owner: form.owner || undefined,
      department: form.department || undefined,
      supplier: form.supplier || undefined,
      purchase_date: form.purchase_date || undefined,
      purchase_price: form.purchase_price,
      warranty_start: form.warranty_start || undefined,
      warranty_end: form.warranty_end || undefined,
      remark: form.remark || undefined
    }

    if (isEdit.value && currentAssetId.value) {
      await updateAsset(currentAssetId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createAsset(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadAssets()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 提交维护记录
async function submitMaintenance() {
  const valid = await maintenanceFormRef.value?.validate().catch(() => false)
  if (!valid || !currentAsset.value) return

  submitting.value = true
  try {
    await createMaintenance({
      asset_id: currentAsset.value.id,
      maintenance_type: maintenanceForm.maintenance_type,
      start_time: maintenanceForm.start_time,
      technician: maintenanceForm.technician || undefined,
      cost: maintenanceForm.cost,
      description: maintenanceForm.description
    })
    ElMessage.success('维护记录创建成功')
    maintenanceDialogVisible.value = false
  } catch (e) {
    console.error('创建维护记录失败', e)
    ElMessage.error('创建维护记录失败')
  } finally {
    submitting.value = false
  }
}

// 删除确认
function confirmDelete(row: Asset) {
  ElMessageBox.confirm(
    `确定要删除资产 "${row.asset_name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteAsset(row.id)
      ElMessage.success('删除成功')
      loadAssets()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {
    // 用户取消
  })
}

// 重置表单
function resetForm() {
  form.asset_code = ''
  form.asset_name = ''
  form.asset_type = ''
  form.status = 'in_stock'
  form.brand = ''
  form.model = ''
  form.serial_number = ''
  form.owner = ''
  form.department = ''
  form.supplier = ''
  form.purchase_date = ''
  form.purchase_price = undefined
  form.warranty_start = ''
  form.warranty_end = ''
  form.remark = ''
}

// ==================== 导入功能 ====================
const importDialogVisible = ref(false)
const importLoading = ref(false)
const importFile = ref<File | null>(null)
const uploadRef = ref()
const importResult = ref<{
  success_count: number
  error_count: number
  errors?: { row: number; field: string; message: string }[]
} | null>(null)

function handleFileChange(file: any) {
  importFile.value = file.raw
}

function handleFileRemove() {
  importFile.value = null
  importResult.value = null
}

function resetImport() {
  importFile.value = null
  importResult.value = null
  importLoading.value = false
}

async function handlePreview() {
  if (!importFile.value) return
  importLoading.value = true
  try {
    const res = await importAssets(importFile.value, 'preview')
    // 响应拦截器已解包，res 即后端返回的预校验结果
    const data = (res as any)?.data || res
    importResult.value = data as any
  } catch (e) {
    console.error('预校验失败', e)
    ElMessage.error('预校验失败')
  } finally {
    importLoading.value = false
  }
}

async function handleConfirmImport() {
  if (!importFile.value) return
  importLoading.value = true
  try {
    await importAssets(importFile.value, 'confirm')
    ElMessage.success('导入成功')
    importDialogVisible.value = false
    resetImport()
    loadAssets()
    loadStatistics()
  } catch (e) {
    console.error('导入失败', e)
    ElMessage.error('导入失败')
  } finally {
    importLoading.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    const res = await downloadImportTemplate()
    // 响应拦截器已解包，res 即 blob 数据本体
    const blobData = (res as any)?.data || res
    const blob = new Blob([blobData], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '资产导入模板.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('下载模板失败')
  }
}

// ==================== 导出功能 ====================
async function handleExport() {
  try {
    const res = await exportAssets({
      asset_type: filters.asset_type || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined
    })
    // 响应拦截器已解包，res 即 blob 数据本体
    const blobData = (res as any)?.data || res
    const blob = new Blob([blobData], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `资产列表_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败')
  }
}

// 格式化资产总值
function formatValue(value: number | undefined) {
  if (!value) return '0'
  if (value >= 10000) {
    return (value / 10000).toFixed(1) + '万'
  }
  return value.toFixed(0)
}

// 获取类型名称
function getTypeName(type: AssetType) {
  const map: Record<AssetType, string> = {
    server: '服务器',
    network: '网络设备',
    storage: '存储设备',
    ups: 'UPS',
    pdu: 'PDU',
    ac: '空调',
    cabinet: '机柜',
    sensor: '传感器',
    other: '其他'
  }
  return map[type] || type
}

// 获取状态名称
function getStatusName(status: AssetStatus) {
  const map: Record<AssetStatus, string> = {
    in_stock: '库存',
    in_use: '使用中',
    borrowed: '借出',
    maintenance: '维护中',
    scrapped: '报废'
  }
  return map[status] || status
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 获取类型标签样式
function getTypeTagType(type: AssetType): TagType {
  const map: Record<AssetType, TagType> = {
    server: 'primary',
    network: 'success',
    storage: 'warning',
    ups: 'danger',
    pdu: 'info',
    ac: 'success',
    cabinet: 'info',
    sensor: 'warning',
    other: 'info'
  }
  return map[type] || 'info'
}

// 获取状态标签样式
function getStatusType(status: AssetStatus): TagType {
  const map: Record<AssetStatus, TagType> = {
    in_stock: 'info',
    in_use: 'success',
    borrowed: 'warning',
    maintenance: 'danger',
    scrapped: 'info'
  }
  return map[status] || 'info'
}

// 加载维护记录
watch(() => detailActiveTab.value, async (tab) => {
  if (tab === 'maintenance' && detailAsset.value) {
    maintenanceLoading.value = true
    try {
      const res = await getMaintenanceRecords({ asset_id: detailAsset.value.id })
      // 响应拦截器已解包，res 可能是数组或含 data/items 的对象
      if (Array.isArray(res)) {
        maintenanceRecords.value = res
      } else if (res && typeof res === 'object') {
        maintenanceRecords.value = (res as any).data || (res as any).items || []
      } else {
        maintenanceRecords.value = []
      }
    } catch (e) {
      console.error('加载维护记录失败', e)
      maintenanceRecords.value = []
    } finally {
      maintenanceLoading.value = false
    }
  }
})

// 加载保修预警
async function loadWarrantyAlerts() {
  try {
    const res = await getWarrantyAlerts()
    // 响应拦截器已解包，res 即 WarrantyAlertResponse 对象
    const data = (res as any)?.data || res
    if (data && typeof data === 'object') {
      warrantyAlerts.value = {
        within_30_days: data.within_30_days || [],
        within_60_days: data.within_60_days || [],
        within_90_days: data.within_90_days || [],
        total_count: data.total_count || 0
      }
    }
  } catch (e) {
    console.error('加载保修预警失败', e)
    // API 失败时使用兜底默认值
    warrantyAlerts.value = {
      within_30_days: [],
      within_60_days: [],
      within_90_days: [],
      total_count: 0
    }
  }
}

// 查看预警资产详情
async function viewAlertAsset(assetId: number) {
  let asset = assets.value.find(a => a.id === assetId)
  if (!asset) {
    try {
      const res = await getAsset(assetId)
      asset = Array.isArray(res) ? res[0] : (res as any).data ?? (res as any)
    } catch {
      ElMessage.warning('资产不存在或已被删除')
      return
    }
  }
  if (asset) {
    viewAsset(asset)
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.asset-page {
  @include page-dashboard(6);
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: var(--radius-lg, 8px);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.1));

      &[style*="409eff"] {
        box-shadow: 0 0 15px rgba(64, 158, 255, 0.4);
      }
      &[style*="67c23a"] {
        box-shadow: 0 0 15px rgba(82, 196, 26, 0.4);
      }
      &[style*="909399"] {
        box-shadow: 0 0 15px rgba(144, 147, 153, 0.4);
      }
      &[style*="e6a23c"] {
        box-shadow: 0 0 15px rgba(230, 162, 60, 0.4);
      }
      &[style*="f56c6c"] {
        box-shadow: 0 0 15px rgba(245, 108, 108, 0.4);
      }
    }

    .stat-info {
      .stat-value {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-primary);
      }

      .stat-label {
        font-size: 13px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }

    &:hover {
      border-color: var(--border-active, #409eff);
      box-shadow: var(--shadow-glow, 0 0 12px rgba(64, 158, 255, 0.2));
    }
  }

  .toolbar-card {
    margin-bottom: 20px;
    background: var(--bg-card);
    border-color: var(--border-color);

    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;

      .toolbar-filters {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }

      .toolbar-actions {
        display: flex;
        gap: 12px;
      }
    }
  }

  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .pagination-wrapper {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
    }
  }

  .warranty-alert-card {
    margin-bottom: 20px;
    background: var(--bg-card);
    border-color: var(--border-color);

    .warranty-alert-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
    }

    .alert-column {
      .alert-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid;
      }

      &.alert-30 .alert-title { border-color: #f56c6c; color: #f56c6c; }
      &.alert-60 .alert-title { border-color: #e6a23c; color: #e6a23c; }
      &.alert-90 .alert-title { border-color: #909399; color: #909399; }
    }

    .alert-list {
      max-height: 200px;
      overflow-y: auto;
    }

    .alert-item {
      padding: 8px;
      border-radius: 4px;
      cursor: pointer;
      margin-bottom: 4px;
      transition: background 0.2s;

      &:hover {
        background: rgba(64, 158, 255, 0.08);
      }

      .alert-item-name {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 2px;
      }

      .alert-item-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        color: #909399;
      }
    }

    .alert-empty {
      text-align: center;
      color: #c0c4cc;
      padding: 20px 0;
    }
  }
}
</style>
