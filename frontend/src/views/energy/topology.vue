<template>
  <div class="energy-topology">
    <!-- 工具栏 -->
    <el-card class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="summary-item">
            <span class="label">总容量</span>
            <span class="value">{{ topology?.total_capacity || 0 }} kVA</span>
          </div>
          <div class="summary-item">
            <span class="label">计量点</span>
            <span class="value">{{ topology?.total_meter_points || 0 }} 个</span>
          </div>
          <div class="summary-item">
            <span class="label">用电设备</span>
            <span class="value">{{ topology?.total_devices || 0 }} 台</span>
          </div>
        </div>
        <div class="toolbar-right">
          <el-switch
            v-model="editMode"
            active-text="编辑模式"
            inactive-text="查看模式"
            style="margin-right: 16px;"
          />
          <template v-if="editMode">
            <el-tooltip :disabled="!!selectedNode" content="请先选中一个节点" placement="top">
              <el-button
                type="primary"
                @click="handleOpenAddDialog"
                :disabled="!selectedNode"
              >
                <el-icon><Plus /></el-icon>添加节点
              </el-button>
            </el-tooltip>
            <el-tooltip :disabled="!!selectedNode && !selectedNode.isVirtual" content="请先选中一个非虚拟节点" placement="top">
              <el-button
                type="danger"
                @click="selectedNode && handleDeleteNode(selectedNode)"
                :disabled="!selectedNode || selectedNode.isVirtual"
              >
                <el-icon><Delete /></el-icon>删除节点
              </el-button>
            </el-tooltip>
            <el-button @click="handleExport">
              <el-icon><Download /></el-icon>导出
            </el-button>
            <el-button @click="showImportDialog = true">
              <el-icon><Upload /></el-icon>导入
            </el-button>
          </template>
          <el-button type="primary" @click="loadTopology" :loading="loading">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <div class="main-content">
      <!-- 拓扑树 -->
      <el-card class="topology-card" v-loading="loading">
        <template #header>
          <div class="card-header">
            <span>配电系统拓扑</span>
            <el-tag v-if="editMode" type="warning" size="small">编辑中</el-tag>
          </div>
        </template>
        <div class="topology-tree">
          <el-tree
            ref="treeRef"
            :data="treeData"
            :props="{ children: 'children', label: 'label' }"
            node-key="key"
            default-expand-all
            :expand-on-click-node="false"
            highlight-current
            @node-click="handleNodeClick"
            @node-contextmenu="handleContextMenu"
          >
            <template #default="{ node, data }">
              <div class="tree-node" :class="[data.type, data.pointType ? `point-${data.pointType}` : '', { selected: selectedNode?.key === data.key, virtual: data.isVirtual }]">
                <el-icon class="node-icon">
                  <component :is="getNodeIcon(data.type, data.pointType)" />
                </el-icon>
                <span class="node-label">{{ data.label }}</span>
                <span class="node-info" v-if="data.info">{{ data.info }}</span>
                <el-tag v-if="data.isVirtual" type="info" size="small">虚拟节点</el-tag>
                <el-tag v-else-if="data.status" :type="getStatusType(data.status)" size="small">
                  {{ getStatusText(data.status) }}
                </el-tag>
                <div class="node-actions" v-if="editMode && !data.isVirtual" @click.stop>
                  <el-button link type="primary" size="small" @click="handleEditNode(data)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button link type="primary" size="small" @click="handleAddChildNode(data)" v-if="canAddChild(data.type)">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                  <el-button link type="danger" size="small" @click="handleDeleteNode(data)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </template>
          </el-tree>
        </div>
      </el-card>

      <!-- 属性面板 -->
      <el-card class="property-panel" v-if="selectedNode && editMode && !selectedNode.isVirtual">
        <template #header>
          <div class="panel-header">
            <span>{{ getNodeTypeName(selectedNode.type) }}属性</span>
            <el-button link type="primary" @click="selectedNode = null">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </template>
        <el-form :model="editForm" label-width="80px" size="small">
          <el-form-item label="编码">
            <el-input v-model="editForm.code" placeholder="输入编码" />
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="editForm.name" placeholder="输入名称" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="editForm.status" placeholder="选择状态">
              <el-option label="正常" value="normal" />
              <el-option label="告警" value="warning" />
              <el-option label="故障" value="fault" />
              <el-option label="离线" value="offline" />
            </el-select>
          </el-form-item>
          <!-- 变压器特有字段 -->
          <template v-if="selectedNode.type === 'transformer'">
            <el-form-item label="额定容量">
              <el-input-number v-model="editForm.rated_capacity" :min="0" style="width: 100%;" />
              <span class="unit">kVA</span>
            </el-form-item>
            <el-form-item label="高压侧">
              <el-input-number v-model="editForm.voltage_high" :min="0" style="width: 100%;" />
              <span class="unit">kV</span>
            </el-form-item>
            <el-form-item label="低压侧">
              <el-input-number v-model="editForm.voltage_low" :min="0" style="width: 100%;" />
              <span class="unit">V</span>
            </el-form-item>
            <el-form-item label="申报需量">
              <el-input-number v-model="editForm.declared_demand" :min="0" style="width: 100%;" />
              <span class="unit">kW</span>
            </el-form-item>
          </template>
          <!-- 计量点特有字段 -->
          <template v-if="selectedNode.type === 'meter_point'">
            <el-form-item label="计量类型">
              <el-select v-model="editForm.meter_type" style="width: 100%;">
                <el-option label="总表" value="main" />
                <el-option label="分表" value="sub" />
                <el-option label="考核表" value="check" />
              </el-select>
            </el-form-item>
            <el-form-item label="测量类型">
              <el-checkbox-group v-model="editForm.measurement_types">
                <el-checkbox v-for="t in measurementTypes" :key="t.value" :value="t.value">
                  {{ t.label }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="CT变比">
              <el-input-number v-model="editForm.ct_ratio" :min="0" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="PT变比">
              <el-input-number v-model="editForm.pt_ratio" :min="0" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="申报需量">
              <el-input-number v-model="editForm.declared_demand" :min="0" style="width: 100%;" />
              <span class="unit">kW</span>
            </el-form-item>
          </template>
          <!-- 回路特有字段 -->
          <template v-if="selectedNode.type === 'circuit'">
            <el-form-item label="额定电流">
              <el-input-number v-model="editForm.rated_current" :min="0" style="width: 100%;" />
              <span class="unit">A</span>
            </el-form-item>
          </template>
          <!-- 设备特有字段 -->
          <template v-if="selectedNode.type === 'device'">
            <el-form-item label="额定功率">
              <el-input-number v-model="editForm.rated_power" :min="0" style="width: 100%;" />
              <span class="unit">kW</span>
            </el-form-item>
          </template>
          <!-- 采集点位特有字段 -->
          <template v-if="selectedNode.type === 'point'">
            <el-form-item label="点位类型">
              <el-select v-model="editForm.point_type" style="width: 100%;">
                <el-option label="模拟量输入" value="AI" />
                <el-option label="数字量输入" value="DI" />
                <el-option label="模拟量输出" value="AO" />
                <el-option label="数字量输出" value="DO" />
              </el-select>
            </el-form-item>
            <el-form-item label="测量类型">
              <el-select v-model="editForm.measurement_type" style="width: 100%;">
                <el-option v-for="t in measurementTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="寄存器地址">
              <el-input v-model="editForm.register_address" placeholder="如 40001" />
            </el-form-item>
            <el-form-item label="数据类型">
              <el-select v-model="editForm.data_type" style="width: 100%;">
                <el-option label="16位整数" value="INT16" />
                <el-option label="32位整数" value="INT32" />
                <el-option label="32位浮点" value="FLOAT32" />
                <el-option label="64位浮点" value="FLOAT64" />
              </el-select>
            </el-form-item>
            <el-form-item label="系数">
              <el-input-number v-model="editForm.scale_factor" :precision="4" style="width: 100%;" />
            </el-form-item>
          </template>
          <el-form-item label="位置">
            <el-input v-model="editForm.location" placeholder="输入位置" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="editForm.remark" type="textarea" :rows="2" placeholder="输入备注" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSaveNode" :loading="saving">保存</el-button>
            <el-button @click="selectedNode = null">取消</el-button>
            <el-button type="danger" @click="handleDeleteNode(selectedNode)">删除</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 设备关联点位面板（非编辑模式时也显示） -->
      <el-card class="device-points-panel" v-if="selectedNode && selectedNode.type === 'device' && !selectedNode.isVirtual">
        <template #header>
          <div class="panel-header">
            <span>关联点位 - {{ selectedNode.label }}</span>
            <div class="panel-actions">
              <el-button link type="primary" @click="handleAddPoint" v-if="editMode">
                <el-icon><Plus /></el-icon> 添加
              </el-button>
              <el-button link type="primary" @click="loadDevicePoints" :loading="loadingDevicePoints">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        <div v-loading="loadingDevicePoints">
          <div v-if="devicePoints.length === 0" class="no-points">
            <el-empty description="暂无关联点位" :image-size="60">
              <el-button v-if="editMode" type="primary" size="small" @click="handleAddPoint">添加点位</el-button>
            </el-empty>
          </div>
          <div v-else class="points-list">
            <div v-for="pt in devicePoints" :key="pt.id" class="point-item" :class="pt.role">
              <div class="point-header">
                <el-tag :type="getPointRoleType(pt.role)" size="small">
                  {{ getPointRoleLabel(pt.role) }}
                </el-tag>
                <span class="point-name">{{ pt.point_name }}</span>
              </div>
              <div class="point-value" v-if="pt.realtime">
                <span class="value" :class="{ offline: pt.realtime.status === 'offline' }">
                  {{ pt.realtime.value !== null ? pt.realtime.value : '--' }}
                </span>
                <span class="unit">{{ pt.unit || '' }}</span>
                <el-tag v-if="pt.realtime.status === 'offline'" type="info" size="small">离线</el-tag>
              </div>
              <div class="point-code">{{ pt.point_code }}</div>
              <div class="point-actions" v-if="editMode">
                <el-button link size="small" @click="handleEditPoint(pt)">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button link size="small" type="danger" @click="handleDeletePoint(pt)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 添加节点对话框 -->
    <el-dialog v-model="showAddDialog" title="添加节点" width="560px" class="topology-dialog">
      <!-- 参考节点信息 -->
      <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
        <template #title>
          <div>参考节点: <strong>{{ selectedNode?.label }}</strong> ({{ getNodeTypeName(selectedNode?.type) }})</div>
        </template>
      </el-alert>

      <el-form :model="addForm" label-width="100px" :rules="addFormRules" ref="addFormRef">
        <!-- 添加位置选择 -->
        <el-form-item label="添加位置" required>
          <el-radio-group v-model="addPosition" @change="onPositionChange">
            <el-radio-button value="child" :disabled="!canAddChildToSelected">
              添加下级 {{ canAddChildToSelected ? `(${getChildTypeName(selectedNode?.type)})` : '' }}
            </el-radio-button>
            <el-radio-button value="sibling" :disabled="!canAddSiblingToSelected">
              添加同级 ({{ getNodeTypeName(selectedNode?.type) }})
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="名称" prop="name">
          <el-input v-model="addForm.name" placeholder="输入名称" />
        </el-form-item>

        <!-- 变压器特有字段 -->
        <template v-if="actualNodeType === 'transformer'">
          <el-form-item label="额定容量" prop="rated_capacity">
            <el-input-number v-model="addForm.rated_capacity" :min="0" style="width: 100%;" />
            <span class="unit">kVA</span>
          </el-form-item>
          <el-form-item label="高压侧电压">
            <el-input-number v-model="addForm.voltage_high" :min="0" style="width: 100%;" />
            <span class="unit">kV</span>
          </el-form-item>
          <el-form-item label="低压侧电压">
            <el-input-number v-model="addForm.voltage_low" :min="0" style="width: 100%;" />
            <span class="unit">V</span>
          </el-form-item>
        </template>
        <!-- 计量点特有字段 -->
        <template v-if="actualNodeType === 'meter_point'">
          <el-form-item label="计量类型">
            <el-select v-model="addForm.meter_type" style="width: 100%;">
              <el-option label="总表" value="main" />
              <el-option label="分表" value="sub" />
              <el-option label="考核表" value="check" />
            </el-select>
          </el-form-item>
          <el-form-item label="测量类型">
            <el-checkbox-group v-model="addForm.measurement_types">
              <el-checkbox v-for="t in measurementTypes" :key="t.value" :value="t.value">
                {{ t.label }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="CT变比">
            <el-input-number v-model="addForm.ct_ratio" :min="0" style="width: 100%;" />
          </el-form-item>
          <el-form-item label="PT变比">
            <el-input-number v-model="addForm.pt_ratio" :min="0" style="width: 100%;" />
          </el-form-item>
        </template>
        <!-- 配电柜特有字段 -->
        <template v-if="actualNodeType === 'panel'">
          <el-form-item label="配电柜类型">
            <el-select v-model="addForm.panel_type" style="width: 100%;">
              <el-option label="进线柜" value="incoming" />
              <el-option label="配电柜" value="distribution" />
              <el-option label="出线柜" value="outgoing" />
              <el-option label="计量柜" value="metering" />
            </el-select>
          </el-form-item>
        </template>
        <!-- 回路特有字段 -->
        <template v-if="actualNodeType === 'circuit'">
          <el-form-item label="回路类型">
            <el-select v-model="addForm.circuit_type" style="width: 100%;">
              <el-option label="出线" value="outgoing" />
              <el-option label="馈线" value="feeder" />
              <el-option label="备用" value="spare" />
            </el-select>
          </el-form-item>
          <el-form-item label="额定电流">
            <el-input-number v-model="addForm.rated_current" :min="0" style="width: 100%;" />
            <span class="unit">A</span>
          </el-form-item>
        </template>
        <!-- 设备特有字段 -->
        <template v-if="actualNodeType === 'device'">
          <el-form-item label="设备类型">
            <el-select v-model="addForm.device_type" style="width: 100%;">
              <el-option label="IT设备" value="IT" />
              <el-option label="空调" value="AC" />
              <el-option label="UPS" value="UPS" />
              <el-option label="照明" value="LIGHT" />
              <el-option label="其他" value="OTHER" />
            </el-select>
          </el-form-item>
          <el-form-item label="额定功率">
            <el-input-number v-model="addForm.rated_power" :min="0" style="width: 100%;" />
            <span class="unit">kW</span>
          </el-form-item>
        </template>
        <!-- 采集点位特有字段 -->
        <template v-if="actualNodeType === 'point'">
          <el-form-item label="点位类型" required>
            <el-select v-model="addForm.point_type" style="width: 100%;">
              <el-option label="模拟量输入" value="AI" />
              <el-option label="数字量输入" value="DI" />
              <el-option label="模拟量输出" value="AO" />
              <el-option label="数字量输出" value="DO" />
            </el-select>
          </el-form-item>
          <el-form-item label="测量类型" required>
            <el-select v-model="addForm.measurement_type" style="width: 100%;">
              <el-option v-for="t in measurementTypes" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="寄存器地址">
            <el-input v-model="addForm.register_address" placeholder="如 40001" />
          </el-form-item>
          <el-form-item label="数据类型">
            <el-select v-model="addForm.data_type" style="width: 100%;">
              <el-option label="16位整数" value="INT16" />
              <el-option label="32位整数" value="INT32" />
              <el-option label="32位浮点" value="FLOAT32" />
              <el-option label="64位浮点" value="FLOAT64" />
            </el-select>
          </el-form-item>
          <el-form-item label="系数">
            <el-input-number v-model="addForm.scale_factor" :precision="4" style="width: 100%;" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmAdd" :loading="saving">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入拓扑数据" width="500px" class="topology-dialog">
      <el-alert type="warning" :closable="false" style="margin-bottom: 16px;">
        <template #title>导入将覆盖现有数据，请谨慎操作</template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="数据文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".json"
            @change="handleFileChange"
          >
            <el-button type="primary">选择JSON文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="清除现有数据">
          <el-switch v-model="importClearExisting" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmImport" :loading="importing">导入</el-button>
      </template>
    </el-dialog>

    <!-- 点位编辑对话框 -->
    <el-dialog v-model="showPointDialog" :title="editingPoint ? '编辑点位' : '新增点位'" width="600px" class="topology-dialog">
      <el-form ref="pointFormRef" :model="pointForm" :rules="pointRules" label-width="100px" size="default">
        <el-form-item label="点位编码" prop="point_code">
          <el-input v-model="pointForm.point_code" :disabled="!!editingPoint" />
        </el-form-item>
        <el-form-item label="点位名称" prop="point_name">
          <el-input v-model="pointForm.point_name" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="点位类型" prop="point_type">
              <el-select v-model="pointForm.point_type" :disabled="!!editingPoint">
                <el-option label="AI-模拟量输入" value="AI" />
                <el-option label="DI-开关量输入" value="DI" />
                <el-option label="AO-模拟量输出" value="AO" />
                <el-option label="DO-开关量输出" value="DO" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用途" prop="device_type">
              <el-select v-model="pointForm.device_type" :disabled="!!editingPoint">
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
              <el-input v-model="pointForm.area_code" :disabled="!!editingPoint" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="pointForm.unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="量程最小值">
              <el-input-number v-model="pointForm.min_range" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="量程最大值">
              <el-input-number v-model="pointForm.max_range" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="采集周期">
          <el-input-number v-model="pointForm.collect_interval" :min="1" />
          <span style="margin-left: 8px;">秒</span>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="pointForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPointDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSavePoint" :loading="savingPoint">确定</el-button>
      </template>
    </el-dialog>

    <!-- 右键菜单 -->
    <div
      v-if="contextMenuVisible"
      class="context-menu"
      :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
      @click.stop
    >
      <template v-if="!contextMenuNode?.isVirtual">
        <div class="menu-item" @click="handleEditNode(contextMenuNode)">
          <el-icon><Edit /></el-icon>编辑
        </div>
      </template>
      <div class="menu-item" @click="handleAddChildNode(contextMenuNode)" v-if="canAddChild(contextMenuNode?.type)">
        <el-icon><Plus /></el-icon>添加下级 ({{ getChildTypeName(contextMenuNode?.type) }})
      </div>
      <div class="menu-item" @click="handleAddSiblingNode(contextMenuNode)" v-if="canAddSibling(contextMenuNode)">
        <el-icon><Plus /></el-icon>添加同级 ({{ getNodeTypeName(contextMenuNode?.type) }})
      </div>
      <template v-if="!contextMenuNode?.isVirtual">
        <div class="menu-item danger" @click="handleDeleteNode(contextMenuNode)">
          <el-icon><Delete /></el-icon>删除
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  Refresh, OfficeBuilding, Odometer, Box, Connection, Monitor,
  Plus, Edit, Delete, Download, Upload, Close, Grid,
  DataLine, CircleCheck, TrendCharts, Open
} from '@element-plus/icons-vue'
import {
  getDistributionTopology,
  createTopologyNode,
  updateTopologyNode,
  deleteTopologyNode,
  exportTopology,
  importTopology,
  getDeviceLinkedPoints,
  createDevicePoints,
  updateDevicePoint,
  deleteDevicePointById,
  type DistributionTopology,
  type TopologyNodeTypeEnum,
  type TopologyNodeCreateRequest,
  type TopologyNodeUpdateRequest,
  type DeviceLinkedPoint
} from '@/api/modules/energy'

// 扩展节点类型，增加 grid 和 point
type ExtendedNodeType = TopologyNodeTypeEnum | 'grid' | 'point'

// 节点层级关系
const nodeHierarchy: Record<ExtendedNodeType, { child: ExtendedNodeType | null; parent: ExtendedNodeType | null; label: string }> = {
  grid: { child: 'transformer', parent: null, label: '电网主节点' },
  transformer: { child: 'meter_point', parent: 'grid', label: '变压器' },
  meter_point: { child: 'panel', parent: 'transformer', label: '计量点' },
  panel: { child: 'circuit', parent: 'meter_point', label: '配电柜' },
  circuit: { child: 'device', parent: 'panel', label: '回路' },
  device: { child: null, parent: 'circuit', label: '设备' },
  point: { child: null, parent: 'device', label: '采集点位' }
}

// 测量类型选项
const measurementTypes = [
  { value: 'voltage', label: '电压 (V)', unit: 'V' },
  { value: 'current', label: '电流 (A)', unit: 'A' },
  { value: 'power', label: '有功功率 (kW)', unit: 'kW' },
  { value: 'reactive_power', label: '无功功率 (kVar)', unit: 'kVar' },
  { value: 'power_factor', label: '功率因数', unit: '' },
  { value: 'energy', label: '电量 (kWh)', unit: 'kWh' },
  { value: 'frequency', label: '频率 (Hz)', unit: 'Hz' },
  { value: 'temperature', label: '温度 (°C)', unit: '°C' },
  { value: 'humidity', label: '湿度 (%RH)', unit: '%RH' },
  { value: 'other', label: '其他', unit: '' }
]

// 状态
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const editMode = ref(false)
const topology = ref<DistributionTopology | null>(null)
const selectedNode = ref<any>(null)
const treeRef = ref()

// 添加节点
const showAddDialog = ref(false)
const addPosition = ref<'child' | 'sibling'>('child')
const addFormRef = ref<FormInstance>()
const addForm = reactive<any>({
  name: '',
  parent_id: null,
  rated_capacity: 1000,
  voltage_high: 10,
  voltage_low: 400,
  ct_ratio: 1,
  pt_ratio: 1,
  meter_type: 'main',
  measurement_types: [] as string[],
  panel_type: 'distribution',
  circuit_type: 'outgoing',
  rated_current: 100,
  device_type: 'IT',
  rated_power: 10,
  // 采集点位字段
  point_type: 'AI',
  measurement_type: 'power',
  register_address: '',
  data_type: 'FLOAT32',
  scale_factor: 1
})

const addFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}

// 编辑表单
const editForm = reactive<any>({
  code: '',
  name: '',
  status: 'normal',
  rated_capacity: 0,
  voltage_high: 0,
  voltage_low: 0,
  ct_ratio: 1,
  pt_ratio: 1,
  meter_type: 'main',
  measurement_types: [] as string[],
  rated_current: 0,
  rated_power: 0,
  declared_demand: 0,
  location: '',
  remark: '',
  // 采集点位字段
  point_type: 'AI',
  measurement_type: 'power',
  register_address: '',
  data_type: 'FLOAT32',
  scale_factor: 1
})

// 导入
const showImportDialog = ref(false)
const importClearExisting = ref(false)
const importFile = ref<File | null>(null)
const uploadRef = ref()

// 设备关联点位
const loadingDevicePoints = ref(false)
const devicePoints = ref<any[]>([])

// 点位编辑对话框
const showPointDialog = ref(false)
const editingPoint = ref<DeviceLinkedPoint | null>(null)
const savingPoint = ref(false)
const pointFormRef = ref()
const pointForm = reactive({
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
const pointRules = {
  point_code: [{ required: true, message: '请输入点位编码', trigger: 'blur' }],
  point_name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  point_type: [{ required: true, message: '请选择点位类型', trigger: 'change' }],
  device_type: [{ required: true, message: '请选择用途', trigger: 'change' }],
  area_code: [{ required: true, message: '请输入区域代码', trigger: 'blur' }]
}

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuNode = ref<any>(null)

// 计算属性 - 计算实际要添加的节点类型
const actualNodeType = computed<ExtendedNodeType>(() => {
  if (!selectedNode.value) return 'transformer'
  if (addPosition.value === 'child') {
    return nodeHierarchy[selectedNode.value.type as ExtendedNodeType]?.child || 'transformer'
  } else {
    return selectedNode.value.type as ExtendedNodeType
  }
})

// 是否可以添加下级节点
const canAddChildToSelected = computed(() => {
  if (!selectedNode.value) return false
  return canAddChild(selectedNode.value.type)
})

// 是否可以添加同级节点
const canAddSiblingToSelected = computed(() => {
  if (!selectedNode.value) return false
  // 电网主节点可以添加同级
  if (selectedNode.value.type === 'grid') return true
  // 其他节点必须有父节点才能添加同级
  return selectedNode.value.parentId !== undefined || selectedNode.value.parentType !== undefined
})

// 树形数据 - 始终包含虚拟电网主节点
const treeData = computed(() => {
  // 构建设备节点（包含采集点位）
  const buildDeviceNode = (d: any, circuitId: number) => ({
    key: `device-${d.id}`,
    id: d.id,
    label: d.device_name || d.name,
    code: d.device_code || d.code,
    type: 'device',
    info: d.rated_power ? `${d.rated_power} kW` : '',
    parentId: circuitId,
    parentType: 'circuit',
    rawData: d,
    children: d.points?.map((pt: any) => ({
      key: `point-${pt.id}`,
      id: pt.id,
      label: pt.point_name || pt.name,
      code: pt.point_code || pt.code,
      type: 'point',
      pointType: pt.point_type,
      info: pt.unit || pt.measurement_type || '',
      parentId: d.id,
      parentType: 'device',
      rawData: pt
    })) || []
  })

  // 构建回路节点
  // API returns circuit_id, not id
  const buildCircuitNode = (c: any, panelId: number) => ({
    key: `circuit-${c.circuit_id}`,
    id: c.circuit_id,
    label: c.circuit_name,
    code: c.circuit_code,
    type: 'circuit',
    info: c.load_type || '',
    parentId: panelId,
    parentType: 'panel',
    rawData: c,
    children: c.devices?.map((d: any) => buildDeviceNode(d, c.circuit_id)) || []
  })

  // 构建配电柜节点
  // API returns panel_id, not id
  const buildPanelNode = (p: any, meterPointId: number) => ({
    key: `panel-${p.panel_id}`,
    id: p.panel_id,
    label: p.panel_name,
    code: p.panel_code,
    type: 'panel',
    info: p.panel_type,
    status: p.status,
    parentId: meterPointId,
    parentType: 'meter_point',
    rawData: p,
    children: p.circuits?.map((c: any) => buildCircuitNode(c, p.panel_id)) || []
  })

  // 构建计量点节点
  // API returns meter_point_id, not id
  const buildMeterPointNode = (m: any, transformerId: number) => ({
    key: `meter_point-${m.meter_point_id}`,
    id: m.meter_point_id,
    label: m.meter_name,
    code: m.meter_code,
    type: 'meter_point',
    info: m.declared_demand ? `${m.declared_demand} kW` : '',
    status: m.status,
    parentId: transformerId,
    parentType: 'transformer',
    rawData: m,
    children: m.panels?.map((p: any) => buildPanelNode(p, m.meter_point_id)) || []
  })

  // 构建变压器节点
  // API returns transformer_id, not id
  const buildTransformerNode = (t: any) => ({
    key: `transformer-${t.transformer_id}`,
    id: t.transformer_id,
    label: t.transformer_name,
    code: t.transformer_code,
    type: 'transformer',
    info: `${t.rated_capacity} kVA`,
    status: t.status,
    parentId: null,
    parentType: 'grid',
    rawData: t,
    children: t.meter_points?.map((m: any) => buildMeterPointNode(m, t.transformer_id)) || []
  })

  // 始终添加虚拟电网主节点
  const gridRoot = {
    key: 'grid-root',
    id: null,
    type: 'grid',
    label: '电网主节点',
    info: '配电系统入口',
    isVirtual: true,
    children: [] as any[]
  }

  if (topology.value?.transformers?.length) {
    gridRoot.children = topology.value.transformers.map(t => buildTransformerNode(t))
  }

  return [gridRoot]
})

// 工具函数
const getNodeIcon = (type: string, pointType?: string) => {
  // 如果是采集点位，根据点位类型返回不同图标
  if (type === 'point' && pointType) {
    const pointIcons: Record<string, any> = {
      AI: DataLine,       // 模拟量输入 - 数据折线
      DI: CircleCheck,    // 开关量输入 - 圆形勾选
      AO: TrendCharts,    // 模拟量输出 - 趋势图
      DO: Open            // 开关量输出 - 开关
    }
    return pointIcons[pointType] || Odometer
  }

  const icons: Record<string, any> = {
    grid: Grid,
    transformer: OfficeBuilding,
    meter_point: Odometer,
    panel: Box,
    circuit: Connection,
    device: Monitor,
    point: Odometer
  }
  return icons[type] || Box
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = { normal: 'success', warning: 'warning', fault: 'danger', offline: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = { normal: '正常', warning: '告警', fault: '故障', offline: '离线' }
  return map[status] || status
}

const getNodeTypeName = (type: string | undefined) => {
  if (!type) return ''
  return nodeHierarchy[type as ExtendedNodeType]?.label || type
}

// 获取子节点类型名称
const getChildTypeName = (type: string | undefined) => {
  if (!type) return ''
  const childType = nodeHierarchy[type as ExtendedNodeType]?.child
  return childType ? nodeHierarchy[childType]?.label : ''
}

// 是否可以添加子节点
const canAddChild = (type: string | undefined): boolean => {
  if (!type) return false
  return nodeHierarchy[type as ExtendedNodeType]?.child !== null
}

// 是否可以添加同级节点
const canAddSibling = (node: any): boolean => {
  if (!node) return false
  // 电网主节点可以添加同级（多个电网入口）
  if (node.type === 'grid') return true
  // 其他节点必须有父节点才能添加同级
  return node.parentId !== undefined || node.parentType !== undefined
}

// 计算子节点数量
const countChildren = (node: any): number => {
  if (!node.children?.length) return 0
  return node.children.length + node.children.reduce((sum: number, c: any) => sum + countChildren(c), 0)
}

// 收集某类型已有编码
const collectExistingCodes = (type: ExtendedNodeType): string[] => {
  if (!topology.value) return []
  const codes: string[] = []

  if (type === 'transformer') {
    topology.value.transformers?.forEach(t => codes.push(t.transformer_code))
  } else if (type === 'meter_point') {
    topology.value.transformers?.forEach(t => {
      t.meter_points?.forEach(m => codes.push(m.meter_code))
    })
  } else if (type === 'panel') {
    topology.value.transformers?.forEach(t => {
      t.meter_points?.forEach(m => {
        m.panels?.forEach(p => codes.push(p.panel_code))
      })
    })
  } else if (type === 'circuit') {
    topology.value.transformers?.forEach(t => {
      t.meter_points?.forEach(m => {
        m.panels?.forEach(p => {
          p.circuits?.forEach(c => codes.push(c.circuit_code))
        })
      })
    })
  } else if (type === 'device') {
    topology.value.transformers?.forEach(t => {
      t.meter_points?.forEach(m => {
        m.panels?.forEach(p => {
          p.circuits?.forEach(c => {
            c.devices?.forEach(d => codes.push(d.device_code))
          })
        })
      })
    })
  } else if (type === 'point') {
    topology.value.transformers?.forEach(t => {
      t.meter_points?.forEach(m => {
        m.panels?.forEach(p => {
          p.circuits?.forEach(c => {
            c.devices?.forEach((d: any) => {
              d.points?.forEach((pt: any) => codes.push(pt.point_code))
            })
          })
        })
      })
    })
  }
  return codes
}

// 从已有编码中提取最大序号
const extractMaxSeq = (codes: string[], prefix: string): number => {
  let max = 0
  const prefixUpper = prefix.toUpperCase()
  for (const code of codes) {
    const upper = code.toUpperCase()
    if (upper.startsWith(prefixUpper)) {
      // 取前缀后面的数字部分，如 TR-003 → 003, M004 → 004
      const rest = upper.slice(prefixUpper.length).replace(/^[-_]/, '')
      const num = parseInt(rest, 10)
      if (!isNaN(num) && num > max) max = num
    }
  }
  return max
}

// 自动生成下一个编码
const generateNextCode = (type: ExtendedNodeType, subType?: string): string => {
  const codes = collectExistingCodes(type)

  // 每种节点类型对应的前缀和编号格式
  if (type === 'transformer') {
    const seq = extractMaxSeq(codes, 'TR-') + 1
    return `TR-${String(seq).padStart(3, '0')}`
  }
  if (type === 'meter_point') {
    const seq = extractMaxSeq(codes, 'M') + 1
    return `M${String(seq).padStart(3, '0')}`
  }
  if (type === 'panel') {
    // 配电柜前缀由子类型决定
    const prefixMap: Record<string, string> = {
      main: 'MDP', incoming: 'MDP', distribution: 'PDU',
      outgoing: 'OUT', metering: 'MTR', sub: 'SUB',
      ups_input: 'UPS-IN', ups_output: 'UPS-OUT'
    }
    const prefix = prefixMap[subType || 'distribution'] || 'PNL'
    const seq = extractMaxSeq(codes, prefix + '-') + 1
    return `${prefix}-${String(seq).padStart(3, '0')}`
  }
  if (type === 'circuit') {
    const seq = extractMaxSeq(codes, 'C-') + 1
    return `C-${String(seq).padStart(3, '0')}`
  }
  if (type === 'device') {
    // 设备前缀由设备类型决定
    const prefixMap: Record<string, string> = {
      IT: 'SRV', AC: 'AC', UPS: 'UPS',
      LIGHT: 'LIGHT', HVAC: 'HVAC', OTHER: 'DEV'
    }
    const prefix = prefixMap[subType || 'OTHER'] || 'DEV'
    const seq = extractMaxSeq(codes, prefix + '-') + 1
    return `${prefix}-${String(seq).padStart(3, '0')}`
  }
  if (type === 'point') {
    // 采集点位前缀由点位类型决定
    const prefixMap: Record<string, string> = {
      AI: 'AI', DI: 'DI', AO: 'AO', DO: 'DO'
    }
    const prefix = prefixMap[subType || 'AI'] || 'PT'
    const seq = extractMaxSeq(codes, prefix + '-') + 1
    return `${prefix}-${String(seq).padStart(3, '0')}`
  }
  return `NODE-001`
}

// 加载拓扑数据
const loadTopology = async () => {
  loading.value = true
  try {
    const res = await getDistributionTopology()
    // 检查多种可能的成功状态
    if (res.code === 0 || res.data) {
      topology.value = res.data
    } else {
      console.error('加载拓扑失败:', res.message)
    }
  } catch (e: any) {
    console.error('加载拓扑失败', e)
    ElMessage.error(e?.response?.data?.message || '加载拓扑数据失败')
  } finally {
    loading.value = false
  }
}

// 节点操作
const handleNodeClick = (data: any) => {
  // 设置选中节点（查看或编辑模式都可以选中）
  selectedNode.value = data

  if (!editMode.value) {
    // 不在编辑模式时提示用户
    if (!data.isVirtual) {
      ElMessage.info('提示：开启"编辑模式"可编辑或删除节点')
    }
    return
  }

  // 虚拟节点不需要填充编辑表单
  if (data.isVirtual) return

  // 填充编辑表单
  editForm.code = data.code || ''
  editForm.name = data.label || ''
  editForm.status = data.status || 'normal'
  editForm.location = data.rawData?.location || ''
  editForm.remark = data.rawData?.remark || ''

  if (data.type === 'transformer') {
    editForm.rated_capacity = data.rawData?.rated_capacity || 0
    editForm.voltage_high = data.rawData?.voltage_high || 0
    editForm.voltage_low = data.rawData?.voltage_low || 0
    editForm.declared_demand = data.rawData?.declared_demand || 0
  } else if (data.type === 'meter_point') {
    editForm.meter_type = data.rawData?.meter_type || 'main'
    editForm.measurement_types = data.rawData?.measurement_types || []
    editForm.ct_ratio = data.rawData?.ct_ratio || 1
    editForm.pt_ratio = data.rawData?.pt_ratio || 1
    editForm.declared_demand = data.rawData?.declared_demand || 0
  } else if (data.type === 'circuit') {
    editForm.rated_current = data.rawData?.rated_current || 0
  } else if (data.type === 'device') {
    editForm.rated_power = data.rawData?.rated_power || 0
  } else if (data.type === 'point') {
    editForm.point_type = data.rawData?.point_type || 'AI'
    editForm.measurement_type = data.rawData?.measurement_type || 'power'
    editForm.register_address = data.rawData?.register_address || ''
    editForm.data_type = data.rawData?.data_type || 'FLOAT32'
    editForm.scale_factor = data.rawData?.scale_factor || 1
  }
}

const handleContextMenu = (event: MouseEvent, data: any) => {
  if (!editMode.value) return

  event.preventDefault()
  contextMenuVisible.value = true
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuNode.value = data
}

// 打开添加节点对话框
const handleOpenAddDialog = () => {
  if (!selectedNode.value) {
    ElMessage.warning('请先选中一个节点')
    return
  }

  // 重置表单
  addForm.name = ''
  addForm.measurement_types = []

  // 默认选择添加下级（如果可以的话）
  if (canAddChildToSelected.value) {
    addPosition.value = 'child'
  } else if (canAddSiblingToSelected.value) {
    addPosition.value = 'sibling'
  }

  showAddDialog.value = true
}

// 位置变更时的回调
const onPositionChange = () => {
  // 重置表单名称
  addForm.name = ''
}

const handleAddNode = (type: ExtendedNodeType) => {
  // 保留此函数用于兼容，但现在主要通过 handleOpenAddDialog 调用
  addForm.name = ''
  addForm.parent_id = null
  showAddDialog.value = true
}

const handleAddChildNode = (parentNode: any) => {
  contextMenuVisible.value = false

  if (!canAddChild(parentNode.type)) {
    ElMessage.warning('该节点不能添加子节点')
    return
  }

  selectedNode.value = parentNode
  addPosition.value = 'child'
  addForm.name = ''
  addForm.measurement_types = []
  showAddDialog.value = true
}

const handleAddSiblingNode = (node: any) => {
  contextMenuVisible.value = false

  if (!canAddSibling(node)) {
    ElMessage.warning('该节点不能添加同级节点')
    return
  }

  selectedNode.value = node
  addPosition.value = 'sibling'
  addForm.name = ''
  addForm.measurement_types = []
  showAddDialog.value = true
}

const handleEditNode = (data: any) => {
  contextMenuVisible.value = false
  selectedNode.value = data
  handleNodeClick(data)
}

const handleDeleteNode = async (data: any) => {
  contextMenuVisible.value = false

  // 虚拟节点不能删除
  if (data.isVirtual) {
    ElMessage.warning('虚拟节点不能删除')
    return
  }

  const childCount = countChildren(data)
  let message = `确定要删除 ${getNodeTypeName(data.type)} "${data.label}" 吗？`
  if (childCount > 0) {
    message += `<br/><br/><span style="color: var(--el-color-warning);">⚠️ 该节点下有 <strong>${childCount}</strong> 个子节点，将一并删除！</span>`
  }

  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true
    })

    saving.value = true
    const res = await deleteTopologyNode({
      node_id: data.id,
      node_type: data.type as TopologyNodeTypeEnum,
      cascade: true
    })

    // 检查多种可能的成功状态：
    // 后端直接返回 {success, deleted} 或包装后的 {code, data: {success, deleted}}
    const isSuccess = (res as any).success === true ||
                      res.code === 0 ||
                      res.data?.success === true ||
                      (res as any).deleted

    if (isSuccess) {
      ElMessage.success('删除成功')
      if (selectedNode.value?.key === data.key) {
        selectedNode.value = null
      }
      await loadTopology()
    } else {
      // 处理包装和非包装的错误消息
      const errorMsg = res.message || (res as any).detail || '删除失败'
      ElMessage.error(errorMsg)
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('deleteTopologyNode error:', e)
      ElMessage.error(e?.response?.data?.message || e?.message || '删除失败')
    }
  } finally {
    saving.value = false
  }
}

const handleSaveNode = async () => {
  if (!selectedNode.value || selectedNode.value.isVirtual) return

  saving.value = true
  try {
    const updateData: TopologyNodeUpdateRequest = {
      node_id: selectedNode.value.id,
      node_type: selectedNode.value.type as TopologyNodeTypeEnum,
      code: editForm.code,
      name: editForm.name,
      status: editForm.status,
      location: editForm.location,
      remark: editForm.remark
    }

    if (selectedNode.value.type === 'transformer') {
      updateData.rated_capacity = editForm.rated_capacity
      updateData.voltage_high = editForm.voltage_high
      updateData.voltage_low = editForm.voltage_low
      updateData.declared_demand = editForm.declared_demand
    } else if (selectedNode.value.type === 'meter_point') {
      updateData.meter_type = editForm.meter_type
      updateData.measurement_types = editForm.measurement_types
      updateData.ct_ratio = editForm.ct_ratio
      updateData.pt_ratio = editForm.pt_ratio
      updateData.declared_demand = editForm.declared_demand
    } else if (selectedNode.value.type === 'circuit') {
      updateData.rated_current = editForm.rated_current
    } else if (selectedNode.value.type === 'device') {
      updateData.rated_power = editForm.rated_power
    } else if (selectedNode.value.type === 'point') {
      updateData.point_type = editForm.point_type
      updateData.measurement_type = editForm.measurement_type
      updateData.register_address = editForm.register_address
      updateData.data_type = editForm.data_type
      updateData.scale_factor = editForm.scale_factor
    }

    const res = await updateTopologyNode(updateData)

    // 检查多种可能的成功状态：
    // 后端直接返回 {success} 或包装后的 {code, data: {success}}
    const isSuccess = (res as any).success === true ||
                      res.code === 0 ||
                      res.data?.success === true

    if (isSuccess) {
      ElMessage.success('保存成功')
      await loadTopology()
    } else {
      // 处理包装和非包装的错误消息
      const errorMsg = res.message || (res as any).detail || '保存失败'
      ElMessage.error(errorMsg)
    }
  } catch (e: any) {
    console.error('updateTopologyNode error:', e)
    ElMessage.error(e?.response?.data?.message || e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleConfirmAdd = async () => {
  // 表单验证
  if (!addFormRef.value) {
    ElMessage.warning('表单未初始化')
    return
  }

  // 检查必填字段
  if (!addForm.name?.trim()) {
    ElMessage.warning('请输入名称')
    return
  }

  if (!selectedNode.value) {
    ElMessage.warning('请先选中一个节点')
    return
  }

  saving.value = true
  try {
    // 计算实际要添加的节点类型和父节点
    let nodeType: ExtendedNodeType
    let parentId: number | null = null
    let parentType: ExtendedNodeType | undefined

    if (addPosition.value === 'child') {
      // 添加下级：父节点是选中节点
      nodeType = nodeHierarchy[selectedNode.value.type as ExtendedNodeType]?.child as ExtendedNodeType
      if (selectedNode.value.type === 'grid') {
        // 电网主节点下添加变压器，无需设置 parent_id
        parentId = null
        parentType = undefined
      } else {
        parentId = selectedNode.value.id
        parentType = selectedNode.value.type as ExtendedNodeType
      }
    } else {
      // 添加同级：与选中节点相同类型，父节点是选中节点的父节点
      nodeType = selectedNode.value.type as ExtendedNodeType
      if (selectedNode.value.type === 'grid') {
        // 电网主节点添加同级（多个电网入口），但这实际上是添加另一个虚拟根，暂不支持
        ElMessage.warning('暂不支持添加多个电网入口')
        saving.value = false
        return
      } else if (selectedNode.value.type === 'transformer') {
        // 变压器的同级，父节点也是 null（都挂在电网主节点下）
        parentId = null
        parentType = undefined
      } else {
        parentId = selectedNode.value.parentId
        parentType = selectedNode.value.parentType as ExtendedNodeType
      }
    }

    // grid 类型不能直接创建
    if (nodeType === 'grid') {
      ElMessage.warning('不能创建电网主节点')
      saving.value = false
      return
    }

    const createData: TopologyNodeCreateRequest = {
      node_type: nodeType as TopologyNodeTypeEnum
    }

    // 设置父节点
    if (parentId !== null && parentType) {
      createData.parent_id = parentId
      createData.parent_type = parentType as TopologyNodeTypeEnum
    }

    // 根据类型设置字段，编码自动生成
    if (nodeType === 'transformer') {
      createData.transformer_code = generateNextCode('transformer')
      createData.transformer_name = addForm.name
      createData.rated_capacity = addForm.rated_capacity
      createData.voltage_high = addForm.voltage_high
      createData.voltage_low = addForm.voltage_low
    } else if (nodeType === 'meter_point') {
      createData.meter_code = generateNextCode('meter_point')
      createData.meter_name = addForm.name
      createData.meter_type = addForm.meter_type
      createData.measurement_types = addForm.measurement_types
      createData.ct_ratio = addForm.ct_ratio
      createData.pt_ratio = addForm.pt_ratio
    } else if (nodeType === 'panel') {
      createData.panel_code = generateNextCode('panel', addForm.panel_type)
      createData.panel_name = addForm.name
      createData.panel_type = addForm.panel_type
    } else if (nodeType === 'circuit') {
      createData.circuit_code = generateNextCode('circuit')
      createData.circuit_name = addForm.name
      createData.circuit_type = addForm.circuit_type
      createData.rated_current = addForm.rated_current
    } else if (nodeType === 'device') {
      createData.device_code = generateNextCode('device', addForm.device_type)
      createData.device_name = addForm.name
      createData.device_type = addForm.device_type
      createData.rated_power = addForm.rated_power
    } else if (nodeType === 'point') {
      createData.point_code = generateNextCode('point', addForm.point_type)
      createData.point_name = addForm.name
      createData.point_type = addForm.point_type
      createData.measurement_type = addForm.measurement_type
      createData.register_address = addForm.register_address
      createData.data_type = addForm.data_type
      createData.scale_factor = addForm.scale_factor
    }

    const res = await createTopologyNode(createData)

    // 检查多种可能的成功状态：
    // 后端直接返回 {success, node_id} 或包装后的 {code, data: {success, node_id}}
    const isSuccess = (res as any).success === true ||
                      res.code === 0 ||
                      res.data?.success === true ||
                      (res.data as any)?.node_id

    if (isSuccess) {
      ElMessage.success('添加成功')
      showAddDialog.value = false
      await loadTopology()
    } else {
      // 处理包装和非包装的错误消息
      const errorMsg = res.message || (res as any).detail || '添加失败'
      ElMessage.error(errorMsg)
    }
  } catch (e: any) {
    console.error('createTopologyNode error:', e)
    // 不重复显示错误消息，因为 axios 拦截器已经显示了
    // ElMessage.error(e?.response?.data?.message || e?.message || '添加失败')
  } finally {
    saving.value = false
  }
}

// 导入导出
const handleExport = async () => {
  try {
    const res = await exportTopology()
    if (res.code === 0 && res.data) {
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `topology-${new Date().toISOString().slice(0, 10)}.json`
      link.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    }
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

const handleFileChange = (file: any) => {
  importFile.value = file.raw
}

const handleConfirmImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  importing.value = true
  try {
    const text = await importFile.value.text()
    const data = JSON.parse(text)
    data.clear_existing = importClearExisting.value

    const res = await importTopology(data)
    if (res.code === 0) {
      ElMessage.success(`导入成功，创建了 ${res.data?.created_count || 0} 个节点`)
      showImportDialog.value = false
      loadTopology()
    } else {
      ElMessage.error(res.message || '导入失败')
    }
  } catch (e) {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    importing.value = false
  }
}

// 点击外部关闭右键菜单
const handleClickOutside = () => {
  contextMenuVisible.value = false
}

onMounted(() => {
  loadTopology()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// 编辑模式切换时清除选中
watch(editMode, (val) => {
  if (!val) {
    selectedNode.value = null
  }
})

// 设备关联点位相关函数
const loadDevicePoints = async () => {
  if (!selectedNode.value || selectedNode.value.type !== 'device') {
    devicePoints.value = []
    return
  }

  loadingDevicePoints.value = true
  try {
    const res = await getDeviceLinkedPoints(selectedNode.value.id)
    const data = res.data || res
    devicePoints.value = data.points || []
  } catch (e: any) {
    console.error('加载设备点位失败:', e)
    devicePoints.value = []
  } finally {
    loadingDevicePoints.value = false
  }
}

// 监听选中节点变化，自动加载设备点位
watch(selectedNode, (newNode) => {
  if (newNode && newNode.type === 'device' && !newNode.isVirtual) {
    loadDevicePoints()
  } else {
    devicePoints.value = []
  }
})

type PointRoleTagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'

const getPointRoleType = (role: string): PointRoleTagType => {
  const map: Record<string, PointRoleTagType> = {
    power: 'danger',
    current: 'warning',
    energy: 'success',
    voltage: 'primary',
    power_factor: 'info',
    associated: 'info'
  }
  return map[role] || 'info'
}

const getPointRoleLabel = (role: string): string => {
  const map: Record<string, string> = {
    power: '功率',
    current: '电流',
    energy: '电能',
    voltage: '电压',
    power_factor: '功率因数',
    associated: '关联'
  }
  return map[role] || role
}

// 点位增删改方法
const handleAddPoint = () => {
  editingPoint.value = null
  Object.assign(pointForm, {
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
  showPointDialog.value = true
}

const handleEditPoint = (pt: DeviceLinkedPoint) => {
  editingPoint.value = pt
  Object.assign(pointForm, {
    point_code: pt.point_code || '',
    point_name: pt.point_name,
    point_type: pt.point_type || 'AI',
    device_type: pt.device_type || 'power',
    area_code: pt.area_code || 'A1',
    unit: pt.unit || '',
    data_type: pt.data_type || 'float',
    min_range: pt.min_range ?? null,
    max_range: pt.max_range ?? null,
    collect_interval: pt.collect_interval || 10,
    description: pt.description || ''
  })
  showPointDialog.value = true
}

const handleSavePoint = async () => {
  if (!selectedNode.value) return
  if (savingPoint.value) return  // 防止重复提交

  // 表单验证
  const valid = await pointFormRef.value?.validate().catch(() => false)
  if (!valid) return

  savingPoint.value = true
  try {
    if (editingPoint.value) {
      // 更新点位
      await updateDevicePoint(editingPoint.value.id, {
        point_name: pointForm.point_name,
        unit: pointForm.unit,
        min_range: pointForm.min_range,
        max_range: pointForm.max_range,
        collect_interval: pointForm.collect_interval,
        description: pointForm.description
      })
      ElMessage.success('更新成功')
    } else {
      // 创建点位
      await createDevicePoints({
        energy_device_id: selectedNode.value.id,
        points: [{
          point_code: pointForm.point_code,
          point_name: pointForm.point_name,
          point_type: pointForm.point_type,
          device_type: pointForm.device_type,
          area_code: pointForm.area_code,
          unit: pointForm.unit,
          data_type: pointForm.data_type,
          min_range: pointForm.min_range,
          max_range: pointForm.max_range,
          collect_interval: pointForm.collect_interval,
          description: pointForm.description
        }]
      })
      ElMessage.success('创建成功')
    }
    showPointDialog.value = false
    await loadDevicePoints()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '操作失败')
  } finally {
    savingPoint.value = false
  }
}

const handleDeletePoint = async (pt: DeviceLinkedPoint) => {
  try {
    await ElMessageBox.confirm(
      `确定删除点位 "${pt.point_name}" 吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await deleteDevicePointById(pt.id)
    ElMessage.success('点位删除成功')
    await loadDevicePoints()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || e.message || '删除失败')
    }
  }
}
</script>

<style scoped lang="scss">
.energy-topology {
  padding: 20px;
  height: calc(100vh - var(--header-height) - 40px);
  display: flex;
  flex-direction: column;
}

.toolbar-card {
  margin-bottom: 16px;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  :deep(.el-card__body) {
    padding: 12px 16px;
    background-color: var(--bg-card-solid);
  }
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 32px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-item {
  display: flex;
  flex-direction: column;

  .label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .value {
    font-size: 18px;
    font-weight: bold;
    color: var(--text-primary);
  }
}

.main-content {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
}

.topology-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);
  overflow: hidden;

  :deep(.el-card__header) {
    background-color: var(--bg-tertiary);
    border-bottom-color: var(--border-color);
    color: var(--text-primary);
    padding: 12px 16px;
  }

  :deep(.el-card__body) {
    flex: 1;
    overflow: auto;
    background-color: var(--bg-card-solid);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.property-panel {
  width: 320px;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);
  overflow: auto;

  :deep(.el-card__header) {
    background-color: var(--bg-tertiary);
    border-bottom-color: var(--border-color);
    color: var(--text-primary);
    padding: 12px 16px;
  }

  :deep(.el-card__body) {
    background-color: var(--bg-card-solid);
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.topology-tree {
  :deep(.el-tree) {
    background-color: transparent;

    .el-tree-node__content {
      height: auto;
      padding: 4px 0;
      background-color: transparent;

      &:hover {
        background-color: var(--bg-tertiary);
      }
    }

    .el-tree-node__expand-icon {
      color: var(--text-secondary);
    }
  }
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  width: 100%;

  &.selected {
    background-color: var(--primary-light);
  }

  .node-actions {
    margin-left: auto;
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
  }

  &.selected .node-actions {
    opacity: 1 !important;

    // 选中状态下按钮使用深色，与浅蓝背景形成对比
    .el-button {
      color: #1a1a2e !important;

      &.el-button--danger {
        color: #c0392b !important;
      }

      &:hover {
        color: var(--primary-color) !important;
      }

      &.el-button--danger:hover {
        color: var(--error-color) !important;
      }
    }
  }

  &:hover .node-actions {
    opacity: 1;
  }
}

.node-icon {
  font-size: 16px;
}

.tree-node.transformer .node-icon { color: var(--error-color); }
.tree-node.meter_point .node-icon { color: var(--warning-color); }
.tree-node.panel .node-icon { color: var(--primary-color); }
.tree-node.circuit .node-icon { color: var(--success-color); }
.tree-node.device .node-icon { color: var(--info-color); }
.tree-node.point .node-icon { color: #9c27b0; }
.tree-node.grid .node-icon { color: #ff5722; }

// 采集点位类型样式
.tree-node.point-AI .node-icon { color: #2196f3; } // 蓝色 - 模拟量输入
.tree-node.point-DI .node-icon { color: #4caf50; } // 绿色 - 开关量输入
.tree-node.point-AO .node-icon { color: #ff9800; } // 橙色 - 模拟量输出
.tree-node.point-DO .node-icon { color: #9c27b0; } // 紫色 - 开关量输出

.tree-node.virtual {
  opacity: 0.8;
  border: 1px dashed var(--border-color);
  background-color: var(--bg-tertiary);
}

.node-label {
  font-weight: 500;
  color: var(--text-primary);
}

.node-info {
  color: var(--text-secondary);
  font-size: 12px;
}

.unit {
  margin-left: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

// 设备关联点位面板样式
.device-points-panel {
  width: 320px;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);
  max-height: 400px;
  overflow: auto;

  :deep(.el-card__header) {
    background-color: var(--bg-tertiary);
    border-bottom-color: var(--border-color);
    color: var(--text-primary);
    padding: 12px 16px;
  }

  :deep(.el-card__body) {
    background-color: var(--bg-card-solid);
    padding: 12px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .panel-actions {
      display: flex;
      gap: 8px;
    }
  }

  .no-points {
    padding: 20px 0;
    text-align: center;
  }

  .points-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .point-item {
    position: relative;
    padding: 10px 12px;
    border-radius: 6px;
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border-color);

    &:hover .point-actions {
      opacity: 1;
    }

    &.power {
      border-left: 3px solid var(--error-color);
    }

    &.current {
      border-left: 3px solid var(--warning-color);
    }

    &.energy {
      border-left: 3px solid var(--success-color);
    }

    &.voltage {
      border-left: 3px solid var(--primary-color);
    }

    .point-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }

    .point-name {
      font-weight: 500;
      color: var(--text-primary);
      font-size: 13px;
    }

    .point-value {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 4px;

      .value {
        font-size: 18px;
        font-weight: bold;
        color: var(--primary-color);

        &.offline {
          color: var(--text-secondary);
        }
      }

      .unit {
        font-size: 12px;
        color: var(--text-secondary);
        margin-left: 2px;
      }
    }

    .point-code {
      font-size: 11px;
      color: var(--text-secondary);
      font-family: monospace;
    }

    .point-actions {
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      opacity: 0;
      transition: opacity 0.2s;
      display: flex;
      gap: 4px;
      background-color: var(--bg-tertiary);
      padding: 4px;
      border-radius: 4px;
    }
  }
}

// 右键菜单
.context-menu {
  position: fixed;
  background: var(--bg-card-solid);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 2000;
  padding: 4px 0;
  min-width: 120px;

  .menu-item {
    padding: 8px 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-regular);

    &:hover {
      background-color: var(--bg-hover);
    }

    &.danger {
      color: var(--error-color);
    }

    .el-icon {
      font-size: 14px;
    }
  }
}

// 深色主题适配
:deep(.el-form-item__label) {
  color: var(--text-regular);
}

:deep(.el-input__inner),
:deep(.el-textarea__inner),
:deep(.el-select .el-input__inner) {
  background-color: var(--bg-tertiary);
  border-color: var(--border-color);
  color: var(--text-primary);
}

:deep(.el-input-number) {
  .el-input__inner {
    background-color: var(--bg-tertiary);
    border-color: var(--border-color);
    color: var(--text-primary);
  }
}
</style>

<!-- 全局样式 - 用于 teleport 到 body 的组件 -->
<style lang="scss">
.topology-dropdown-menu {
  background-color: var(--bg-card-solid, #1d1e1f) !important;
  border-color: var(--border-color, #4c4d4f) !important;

  .el-dropdown-menu {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    border-color: var(--border-color, #4c4d4f) !important;
  }

  .el-dropdown-menu__item {
    color: var(--text-primary, #e5eaf3) !important;

    &:hover, &:focus {
      background-color: var(--bg-tertiary, #2c2c2c) !important;
      color: var(--primary-color, #409eff) !important;
    }

    &.is-disabled {
      color: var(--text-disabled, #6c6e72) !important;
    }

    .el-icon {
      margin-right: 8px;
      color: inherit;
    }
  }

  // 箭头颜色
  .el-popper__arrow::before {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    border-color: var(--border-color, #4c4d4f) !important;
  }
}

// 对话框深色主题
.topology-dialog {
  .el-dialog {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    border: 1px solid var(--border-color, #4c4d4f);
  }

  .el-dialog__header {
    background-color: var(--bg-tertiary, #2c2c2c) !important;
    border-bottom: 1px solid var(--border-color, #4c4d4f);
    padding: 16px 20px;
    margin-right: 0;

    .el-dialog__title {
      color: var(--text-primary, #e5eaf3) !important;
    }

    .el-dialog__headerbtn {
      top: 16px;

      .el-dialog__close {
        color: var(--text-secondary, #a3a6ad) !important;

        &:hover {
          color: var(--primary-color, #409eff) !important;
        }
      }
    }
  }

  .el-dialog__body {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    color: var(--text-primary, #e5eaf3) !important;
    padding: 20px;
  }

  .el-dialog__footer {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    border-top: 1px solid var(--border-color, #4c4d4f);
    padding: 12px 20px;
  }

  // 表单样式
  .el-form-item__label {
    color: var(--text-regular, #cfd3dc) !important;
  }

  .el-input__wrapper,
  .el-textarea__inner {
    background-color: var(--bg-tertiary, #2c2c2c) !important;
    border-color: var(--border-color, #4c4d4f) !important;
    box-shadow: none !important;
  }

  .el-input__inner,
  .el-textarea__inner {
    color: var(--text-primary, #e5eaf3) !important;

    &::placeholder {
      color: var(--text-placeholder, #8d9095) !important;
    }
  }

  .el-select {
    .el-input__wrapper {
      background-color: var(--bg-tertiary, #2c2c2c) !important;
    }
  }

  .el-input-number {
    .el-input__wrapper {
      background-color: var(--bg-tertiary, #2c2c2c) !important;
    }

    .el-input-number__decrease,
    .el-input-number__increase {
      background-color: var(--bg-tertiary, #2c2c2c) !important;
      border-color: var(--border-color, #4c4d4f) !important;
      color: var(--text-primary, #e5eaf3) !important;

      &:hover {
        color: var(--primary-color, #409eff) !important;
      }
    }
  }

  .el-checkbox__label {
    color: var(--text-primary, #e5eaf3) !important;
  }

  .el-alert {
    background-color: var(--bg-tertiary, #2c2c2c) !important;
    border-color: var(--border-color, #4c4d4f) !important;

    .el-alert__title {
      color: var(--warning-color, #e6a23c) !important;
    }
  }

  .el-upload-dragger {
    background-color: var(--bg-tertiary, #2c2c2c) !important;
    border-color: var(--border-color, #4c4d4f) !important;

    .el-upload__text {
      color: var(--text-regular, #cfd3dc) !important;

      em {
        color: var(--primary-color, #409eff) !important;
      }
    }

    .el-icon {
      color: var(--text-secondary, #a3a6ad) !important;
    }

    &:hover {
      border-color: var(--primary-color, #409eff) !important;
    }
  }
}

// Select 下拉菜单（也是 teleport 到 body 的）
.el-select-dropdown {
  background-color: var(--bg-card-solid, #1d1e1f) !important;
  border-color: var(--border-color, #4c4d4f) !important;

  .el-select-dropdown__item {
    color: var(--text-primary, #e5eaf3) !important;

    &:hover, &.hover {
      background-color: var(--bg-tertiary, #2c2c2c) !important;
    }

    &.selected {
      color: var(--primary-color, #409eff) !important;
    }
  }

  .el-popper__arrow::before {
    background-color: var(--bg-card-solid, #1d1e1f) !important;
    border-color: var(--border-color, #4c4d4f) !important;
  }
}
</style>
