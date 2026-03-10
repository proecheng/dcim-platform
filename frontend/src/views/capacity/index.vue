<template>
  <div class="capacity-page">
    <!-- 区域维度筛选器 -->
    <el-row class="filter-row" :gutter="12" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-select v-model="locationDimension" placeholder="聚合维度" @change="handleDimensionChange" clearable>
          <el-option label="按区域" value="area" />
          <el-option label="按楼层" value="floor" />
          <el-option label="按房间" value="room" />
        </el-select>
      </el-col>
      <el-col :span="6" v-if="locationDimension && locationOptions.length > 0">
        <el-select v-model="selectedLocation" placeholder="选择位置" @change="handleLocationChange" clearable>
          <el-option v-for="loc in locationOptions" :key="loc" :label="loc" :value="loc" />
        </el-select>
      </el-col>
    </el-row>

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
            <div class="stat-detail">{{ statistics.power?.used_capacity_kw || 0 }}/{{ statistics.power?.total_capacity_kw || 0 }} kW</div>
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
            <div class="stat-detail">{{ statistics.cooling?.used_cooling_kw || 0 }}/{{ statistics.cooling?.total_cooling_kw || 0 }} kW</div>
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
            <div class="stat-detail">{{ statistics.weight?.used_weight_kg || 0 }}/{{ statistics.weight?.total_weight_kg || 0 }} kg</div>
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
                {{ row.used_capacity_kw }}/{{ row.total_capacity_kw }} kW
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
                {{ row.total_cooling_kw }} kW
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

        <!-- 承重容量标签页 -->
        <el-tab-pane label="承重容量" name="weight">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showWeightDialog()">新增承重</el-button>
          </div>
          <el-table :data="weightList" stripe border v-loading="loading">
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="location" label="位置" min-width="120" />
            <el-table-column label="承重使用" width="160">
              <template #default="{ row }">
                {{ row.used_weight_kg || 0 }}/{{ row.total_weight_kg || 0 }} kg
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="180">
              <template #default="{ row }">
                <div class="usage-cell">
                  <el-progress :percentage="row.usage_rate" :stroke-width="8" :color="getProgressColor(row.usage_rate)" />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showWeightDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeleteWeight(row)">删除</el-button>
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
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column prop="device_count" label="设备数量" width="100">
              <template #default="{ row }">
                {{ row.device_count || 0 }}
              </template>
            </el-table-column>
            <el-table-column prop="required_u" label="需求U位" width="100">
              <template #default="{ row }">
                {{ row.required_u || 0 }} U
              </template>
            </el-table-column>
            <el-table-column prop="required_power_kw" label="需求功率" width="120">
              <template #default="{ row }">
                {{ row.required_power_kw || 0 }} kW
              </template>
            </el-table-column>
            <el-table-column label="可行性" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_feasible ? 'success' : 'danger'" size="small">
                  {{ row.is_feasible ? '可行' : '不可行' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="feasibility_notes" label="评估说明" min-width="180">
              <template #default="{ row }">
                {{ row.feasibility_notes || row.description || '--' }}
              </template>
            </el-table-column>
            <el-table-column label="目标机柜" width="120">
              <template #default="{ row }">
                <span v-if="row.target_cabinet_id">{{ cabinetMap[row.target_cabinet_id] || `#${row.target_cabinet_id}` }}</span>
                <span v-else style="color: #999">未指定</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showPlanDialog(row)">编辑</el-button>
                <el-button type="warning" size="small" link @click="showOverrideDialog(row)">覆盖机柜</el-button>
                <el-button type="danger" link @click="confirmDeletePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 容量预警标签页 -->
        <el-tab-pane label="容量预警" name="alerts">
          <div class="tab-toolbar">
            <el-select v-model="alertTypeFilter" placeholder="类型筛选" clearable style="width: 150px; margin-right: 12px;" @change="loadAlertList">
              <el-option label="空间" value="space" />
              <el-option label="电力" value="power" />
              <el-option label="制冷" value="cooling" />
              <el-option label="承重" value="weight" />
            </el-select>
            <el-select v-model="alertStatusFilter" placeholder="状态筛选" clearable style="width: 150px;" @change="loadAlertList">
              <el-option label="警告" value="warning" />
              <el-option label="严重" value="critical" />
              <el-option label="已满" value="full" />
            </el-select>
          </div>
          <el-table :data="alertList" stripe border v-loading="loading" :row-class-name="getAlertRowClass">
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                {{ { space: '空间', power: '电力', cooling: '制冷', weight: '承重' }[row.type] || row.type }}
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="location" label="位置" min-width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="180">
              <template #default="{ row }">
                <div class="usage-cell">
                  <el-progress :percentage="row.usage_rate" :stroke-width="8" :color="getProgressColor(row.usage_rate)" />
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="threshold" label="阈值" width="100">
              <template #default="{ row }">{{ row.threshold }}%</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 容量趋势标签页 -->
        <el-tab-pane label="容量趋势" name="trend">
          <!-- 区域 A：趋势图表 -->
          <div style="display: flex; gap: 16px; margin-bottom: 16px; align-items: center;">
            <el-select v-model="trendType" placeholder="容量类型" style="width: 140px;" @change="loadTrendData">
              <el-option label="空间容量" value="space" />
              <el-option label="电力容量" value="power" />
              <el-option label="制冷容量" value="cooling" />
              <el-option label="承重容量" value="weight" />
            </el-select>
            <el-select v-model="trendRange" placeholder="时间范围" style="width: 140px;" @change="loadTrendData">
              <el-option label="最近7天" value="7" />
              <el-option label="最近30天" value="30" />
              <el-option label="最近90天" value="90" />
            </el-select>
            <el-select v-model="trendInterval" placeholder="聚合粒度" style="width: 140px;" @change="loadTrendData">
              <el-option label="按小时" value="hour" />
              <el-option label="按天" value="day" />
              <el-option label="按周" value="week" />
              <el-option label="按月" value="month" />
            </el-select>
          </div>
          <div ref="trendChartRef" style="width: 100%; height: 400px;"></div>

          <!-- 区域 B：预测图表 -->
          <el-divider content-position="left">容量预测</el-divider>
          <div style="display: flex; gap: 16px; margin-bottom: 16px; align-items: center;">
            <el-select v-model="forecastDays" placeholder="预测周期" style="width: 140px;" @change="loadForecastData">
              <el-option label="3个月" :value="90" />
              <el-option label="6个月" :value="180" />
              <el-option label="12个月" :value="365" />
            </el-select>
          </div>
          <el-alert v-if="forecastData.is_demo" title="当前为演示数据，系统需积累更多历史数据后将显示真实预测" type="info" :closable="false" show-icon style="margin-bottom: 16px;" />
          <div ref="forecastChartRef" style="width: 100%; height: 400px;"></div>

          <!-- 区域 C：扩容建议 -->
          <el-divider content-position="left" v-if="forecastData.expansion_suggestions?.length">扩容建议</el-divider>
          <el-row :gutter="16" v-if="forecastData.expansion_suggestions?.length">
            <el-col :span="12" v-for="(item, index) in forecastData.expansion_suggestions" :key="index" style="margin-bottom: 16px;">
              <el-card shadow="hover">
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon :size="20" color="#E6A23C"><WarningFilled /></el-icon>
                    <span>{{ trendTypeLabels[item.capacity_type] || item.capacity_type }}</span>
                  </div>
                </template>
                <p>预计超阈值日期：<strong>{{ item.predicted_exceed_date }}</strong></p>
                <p>当前使用率：{{ item.current_usage_rate.toFixed(1) }}%</p>
                <p>预计使用率：{{ item.predicted_usage_rate.toFixed(1) }}%</p>
                <p>资源缺口：{{ item.resource_gap }}</p>
                <p style="color: #409EFF;">{{ item.suggestion }}</p>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 空间容量对话框 -->
    <el-dialog append-to-body
      v-model="spaceDialogVisible"
      :title="isEdit ? '编辑空间容量' : '新增空间容量'"
      width="500px"
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
    <el-dialog append-to-body
      v-model="powerDialogVisible"
      :title="isEdit ? '编辑电力容量' : '新增电力容量'"
      width="500px"
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
    <el-dialog append-to-body
      v-model="coolingDialogVisible"
      :title="isEdit ? '编辑制冷容量' : '新增制冷容量'"
      width="500px"
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
    <el-dialog append-to-body
      v-model="planDialogVisible"
      :title="isEdit ? '编辑上架评估' : '新建上架评估'"
      width="1000px"
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

      <!-- 获取推荐按钮 -->
      <div style="margin: 16px 0; text-align: center;">
        <el-button type="primary" :loading="recommendLoading" @click="handleGetRecommendation" :disabled="!planForm.required_u || planForm.required_u < 1">
          <el-icon><Search /></el-icon> 获取上架推荐
        </el-button>
      </div>

      <!-- 推荐结果 -->
      <div v-if="showRecommendResult" style="margin-top: 16px;">
        <el-divider content-position="left">推荐候选机柜</el-divider>
        <el-table :data="recommendResult" size="small" border stripe max-height="300">
          <el-table-column prop="cabinet_code" label="编码" width="100" />
          <el-table-column prop="cabinet_name" label="名称" width="120" />
          <el-table-column prop="location" label="位置" width="120" show-overflow-tooltip />
          <el-table-column label="空间" width="70" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.space_score >= 80 ? '#67C23A' : row.space_score >= 60 ? '#E6A23C' : '#F56C6C' }">
                {{ row.space_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="电力" width="70" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.power_score >= 80 ? '#67C23A' : row.power_score >= 60 ? '#E6A23C' : '#F56C6C' }">
                {{ row.power_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="制冷" width="70" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.cooling_score >= 80 ? '#67C23A' : row.cooling_score >= 60 ? '#E6A23C' : '#F56C6C' }">
                {{ row.cooling_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="承重" width="70" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.weight_score >= 80 ? '#67C23A' : row.weight_score >= 60 ? '#E6A23C' : '#F56C6C' }">
                {{ row.weight_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="综合" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.total_score >= 80 ? 'success' : row.total_score >= 60 ? 'warning' : 'danger'" size="small">
                {{ row.total_score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
          <el-table-column label="操作" width="80" align="center" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" size="small" link @click="selectRecommendedCabinet(row)">选择</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPlanForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 承重容量对话框 -->
    <el-dialog append-to-body
      v-model="weightDialogVisible"
      :title="isEdit ? '编辑承重容量' : '新增承重容量'"
      width="500px"
    >
      <el-form
        ref="weightFormRef"
        :model="weightForm"
        :rules="weightRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="weightForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="weightForm.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="总承重(kg)" prop="total_weight_kg">
          <el-input-number
            v-model="weightForm.total_weight_kg"
            :min="0"
            :precision="2"
            placeholder="请输入总承重"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="已用(kg)" prop="used_weight_kg">
          <el-input-number
            v-model="weightForm.used_weight_kg"
            :min="0"
            :precision="2"
            placeholder="请输入已用承重"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="weightDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitWeightForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 覆盖机柜对话框 -->
    <el-dialog append-to-body v-model="overrideDialogVisible" title="选择目标机柜" width="700px">
      <el-table :data="cabinetList" v-loading="cabinetLoading" size="small" border stripe max-height="400">
        <el-table-column prop="cabinet_code" label="编码" width="120" />
        <el-table-column prop="cabinet_name" label="名称" width="150" />
        <el-table-column prop="location" label="位置" width="150" show-overflow-tooltip />
        <el-table-column prop="total_u" label="总U" width="70" align="center" />
        <el-table-column prop="available_u" label="可用U" width="70" align="center" />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleOverrideCabinet(row.id)">选择</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Grid, Lightning, Odometer, Box, Plus, Search, WarningFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getSpaceCapacities, createSpaceCapacity, updateSpaceCapacity, deleteSpaceCapacity,
  getPowerCapacities, createPowerCapacity, updatePowerCapacity, deletePowerCapacity,
  getCoolingCapacities, createCoolingCapacity, updateCoolingCapacity, deleteCoolingCapacity,
  getWeightCapacities, createWeightCapacity, updateWeightCapacity, deleteWeightCapacity,
  getCapacityPlans, createCapacityPlan, updateCapacityPlan, deleteCapacityPlan,
  getCapacityStatistics, getCapacityAlerts, getCapacityByLocation,
  getRackingRecommendation, overridePlanCabinet,
  getCapacityTrend, getCapacityForecast,
  type SpaceCapacity, type PowerCapacity, type CoolingCapacity, type WeightCapacity, type CapacityPlan,
  type CapacityStatistics, type CapacityStatus, type CabinetScore, type ExpansionSuggestion
} from '@/api/modules/capacity'
import { getCabinets } from '@/api/modules/asset'

// 类型定义
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const activeTab = ref('space')

// 列表数据
const spaceList = ref<SpaceCapacity[]>([])
const powerList = ref<PowerCapacity[]>([])
const coolingList = ref<CoolingCapacity[]>([])
const planList = ref<CapacityPlan[]>([])
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
  required_weight_kg: 0,
  target_cabinet_id: null as number | null
})

const planRules = {
  name: [{ required: true, message: '请输入评估名称', trigger: 'blur' }],
  device_count: [{ required: true, message: '请输入设备数量', trigger: 'blur' }]
}

// 承重容量对话框
const weightList = ref<WeightCapacity[]>([])
const weightDialogVisible = ref(false)
const weightFormRef = ref<FormInstance>()
const weightForm = reactive({
  name: '',
  location: '',
  total_weight_kg: 0,
  used_weight_kg: 0
})

const weightRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  total_weight_kg: [{ required: true, message: '请输入总承重', trigger: 'blur' }]
}

// 区域维度筛选
const locationDimension = ref<string>('')
const selectedLocation = ref<string>('')
const locationOptions = ref<string[]>([])
const locationData = ref<any[]>([])
const originalStatistics = ref<Partial<CapacityStatistics>>({})

// 容量预警
const alertList = ref<any[]>([])
const alertTypeFilter = ref<string>('')
const alertStatusFilter = ref<string>('')

// 推荐相关
const recommendLoading = ref(false)
const recommendResult = ref<CabinetScore[]>([])
const showRecommendResult = ref(false)

// 覆盖机柜相关
const overrideDialogVisible = ref(false)
const overridePlanId = ref<number | null>(null)
const cabinetList = ref<any[]>([])
const cabinetLoading = ref(false)

// 机柜名称映射
const cabinetMap = ref<Record<number, string>>({})

// 初始化加载
onMounted(() => {
  loadStatistics()
  loadSpaceList()
  window.addEventListener('resize', handleTrendChartResize)
})

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getCapacityStatistics() as any
    const data = res?.data ?? res
    if (data && typeof data === 'object') {
      statistics.value = data
      originalStatistics.value = { ...data }
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
    case 'weight':
      loadWeightList()
      break
    case 'plan':
      loadPlanList()
      break
    case 'alerts':
      loadAlertList()
      break
    case 'trend':
      nextTick(() => {
        loadTrendData()
        loadForecastData()
      })
      break
  }
}

// ==================== 空间容量 ====================
async function loadSpaceList() {
  loading.value = true
  try {
    const res = await getSpaceCapacities() as any
    const data = res?.data ?? res
    spaceList.value = Array.isArray(data) ? data : data?.items || []
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
    const res = await getPowerCapacities() as any
    const data = res?.data ?? res
    powerList.value = Array.isArray(data) ? data : data?.items || []
  } catch (e) {
    console.error('加载电力容量列表失败', e)
    ElMessage.error('加载电力容量列表失败')
  } finally {
    loading.value = false
  }
}

function showPowerDialog(row?: PowerCapacity) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(powerForm, {
      name: row.name,
      capacity_type: row.capacity_type || 'UPS',
      total_capacity_kw: row.total_capacity_kw || 0,
      used_capacity_kw: row.used_capacity_kw || 0,
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
      capacity_type: powerForm.capacity_type,
      total_capacity_kw: powerForm.total_capacity_kw,
      used_capacity_kw: powerForm.used_capacity_kw,
      redundancy_mode: powerForm.redundancy_mode
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
    const res = await getCoolingCapacities() as any
    const data = res?.data ?? res
    coolingList.value = Array.isArray(data) ? data : data?.items || []
  } catch (e) {
    console.error('加载制冷容量列表失败', e)
    ElMessage.error('加载制冷容量列表失败')
  } finally {
    loading.value = false
  }
}

function showCoolingDialog(row?: CoolingCapacity) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(coolingForm, {
      name: row.name,
      location: row.location || '',
      total_cooling_kw: row.total_cooling_kw || 0,
      used_cooling_kw: row.used_cooling_kw || 0,
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
      total_cooling_kw: coolingForm.total_cooling_kw,
      used_cooling_kw: coolingForm.used_cooling_kw,
      target_temperature: coolingForm.target_temperature
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
    const res = await getCapacityPlans() as any
    const data = res?.data ?? res
    planList.value = Array.isArray(data) ? data : data?.items || []
  } catch (e) {
    console.error('加载上架评估列表失败', e)
    ElMessage.error('加载上架评估列表失败')
  } finally {
    loading.value = false
  }
  // 加载机柜名称映射
  try {
    const cabRes = await getCabinets() as any
    const cabData = cabRes?.data ?? cabRes
    const cabs = Array.isArray(cabData) ? cabData : []
    const map: Record<number, string> = {}
    cabs.forEach((c: any) => { map[c.id] = c.cabinet_name })
    cabinetMap.value = map
  } catch (e) {
    // 忽略，不影响主功能
  }
}

function showPlanDialog(row?: CapacityPlan) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  recommendResult.value = []
  showRecommendResult.value = false
  if (row) {
    Object.assign(planForm, {
      name: row.name,
      description: row.description || '',
      device_count: row.device_count || 1,
      required_u: row.required_u || 0,
      required_power_kw: row.required_power_kw || 0,
      required_cooling_kw: row.required_cooling_kw || 0,
      required_weight_kg: row.required_weight_kg || 0,
      target_cabinet_id: row.target_cabinet_id || null
    })
  } else {
    Object.assign(planForm, {
      name: '',
      description: '',
      device_count: 1,
      required_u: 0,
      required_power_kw: 0,
      required_cooling_kw: 0,
      required_weight_kg: 0,
      target_cabinet_id: null
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
      name: planForm.name,
      description: planForm.description || undefined,
      device_count: planForm.device_count,
      required_u: planForm.required_u,
      required_power_kw: planForm.required_power_kw,
      required_cooling_kw: planForm.required_cooling_kw,
      required_weight_kg: planForm.required_weight_kg,
      target_cabinet_id: planForm.target_cabinet_id || undefined
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
    `确定要删除上架评估 "${row.name}" 吗？`,
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

async function handleGetRecommendation() {
  if (!planForm.required_u || planForm.required_u < 1) {
    ElMessage.warning('请先填写所需U位数（至少1U）')
    return
  }
  recommendLoading.value = true
  showRecommendResult.value = false
  try {
    const res = await getRackingRecommendation({
      required_u: planForm.required_u,
      required_power_kw: planForm.required_power_kw || undefined,
      required_cooling_kw: planForm.required_cooling_kw || undefined,
      required_weight_kg: planForm.required_weight_kg || undefined,
      limit: 5
    })
    const recData = (res as any)?.data ?? res
    recommendResult.value = recData?.candidates || []
    showRecommendResult.value = true
    if (recommendResult.value.length === 0) {
      ElMessage.info('没有找到满足条件的候选机柜')
    }
  } catch (e) {
    console.error('获取推荐失败', e)
    ElMessage.error('获取推荐失败')
  } finally {
    recommendLoading.value = false
  }
}

function selectRecommendedCabinet(row: CabinetScore) {
  planForm.target_cabinet_id = row.cabinet_id
  ElMessage.success(`已选择机柜: ${row.cabinet_name}(${row.cabinet_code})`)
}

async function showOverrideDialog(row: CapacityPlan) {
  overridePlanId.value = row.id
  cabinetLoading.value = true
  overrideDialogVisible.value = true
  try {
    const res = await getCabinets() as any
    const cabListData = res?.data ?? res
    cabinetList.value = Array.isArray(cabListData) ? cabListData : []
  } catch (e) {
    console.error('加载机柜列表失败', e)
    ElMessage.error('加载机柜列表失败')
  } finally {
    cabinetLoading.value = false
  }
}

async function handleOverrideCabinet(cabinetId: number) {
  if (!overridePlanId.value) return
  try {
    await overridePlanCabinet(overridePlanId.value, cabinetId)
    ElMessage.success('覆盖机柜成功')
    overrideDialogVisible.value = false
    loadPlanList()
  } catch (e) {
    console.error('覆盖机柜失败', e)
    ElMessage.error('覆盖机柜失败')
  }
}

// ==================== 承重容量 ====================
async function loadWeightList() {
  loading.value = true
  try {
    const res = await getWeightCapacities() as any
    const data = res?.data ?? res
    weightList.value = Array.isArray(data) ? data : data?.items || []
  } catch (e) {
    console.error('加载承重容量列表失败', e)
    ElMessage.error('加载承重容量列表失败')
  } finally {
    loading.value = false
  }
}

function showWeightDialog(row?: WeightCapacity) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  if (row) {
    Object.assign(weightForm, {
      name: row.name,
      location: row.location || '',
      total_weight_kg: row.total_weight_kg || 0,
      used_weight_kg: row.used_weight_kg || 0
    })
  } else {
    Object.assign(weightForm, {
      name: '',
      location: '',
      total_weight_kg: 0,
      used_weight_kg: 0
    })
  }
  weightDialogVisible.value = true
}

async function submitWeightForm() {
  const valid = await weightFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      name: weightForm.name,
      location: weightForm.location || undefined,
      total_weight_kg: weightForm.total_weight_kg,
      used_weight_kg: weightForm.used_weight_kg
    }

    if (isEdit.value && currentId.value) {
      await updateWeightCapacity(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createWeightCapacity(data)
      ElMessage.success('创建成功')
    }
    weightDialogVisible.value = false
    loadWeightList()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

function confirmDeleteWeight(row: WeightCapacity) {
  ElMessageBox.confirm(
    `确定要删除承重容量 "${row.name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteWeightCapacity(row.id)
      ElMessage.success('删除成功')
      loadWeightList()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 区域维度筛选 ====================
async function handleDimensionChange(val: string) {
  selectedLocation.value = ''
  locationOptions.value = []
  locationData.value = []

  if (!val) {
    // 清除维度，恢复总体统计
    if (Object.keys(originalStatistics.value).length > 0) {
      statistics.value = { ...originalStatistics.value }
    }
    return
  }

  try {
    const res = await getCapacityByLocation({ dimension: val as 'area' | 'floor' | 'room' }) as any
    const locData = res?.data ?? res
    if (locData?.items) {
      locationData.value = locData.items
      locationOptions.value = locData.items.map((item: any) => item.location)
    }
  } catch (e) {
    console.error('加载区域数据失败', e)
  }
}

function handleLocationChange(val: string) {
  if (!val) {
    // 清除位置选择，恢复总体统计
    if (Object.keys(originalStatistics.value).length > 0) {
      statistics.value = { ...originalStatistics.value }
    }
    return
  }

  const item = locationData.value.find((d: any) => d.location === val)
  if (item) {
    statistics.value = {
      ...statistics.value,
      space: { ...statistics.value.space, ...item.space } as any,
      power: { ...statistics.value.power, ...item.power } as any,
      cooling: { ...statistics.value.cooling, ...item.cooling } as any,
      weight: { ...statistics.value.weight, ...item.weight } as any
    }
  }
}

// ==================== 容量预警 ====================
async function loadAlertList() {
  loading.value = true
  try {
    const params: any = {}
    if (alertTypeFilter.value) params.type = alertTypeFilter.value
    if (alertStatusFilter.value) params.status = alertStatusFilter.value
    const res = await getCapacityAlerts(params) as any
    const alertData = res?.data ?? res
    alertList.value = Array.isArray(alertData) ? alertData : alertData?.items || []
  } catch (e) {
    console.error('加载容量预警列表失败', e)
    ElMessage.error('加载容量预警列表失败')
  } finally {
    loading.value = false
  }
}

function getAlertRowClass({ row }: { row: any }) {
  if (row.status === 'critical' || row.status === 'full') return 'alert-row-critical'
  if (row.status === 'warning') return 'alert-row-warning'
  return ''
}

// ==================== 容量趋势 ====================
const trendType = ref('space')
const trendRange = ref('30')
const trendInterval = ref('day')
const trendChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

const forecastDays = ref(90)
const forecastChartRef = ref<HTMLElement>()
let forecastChart: echarts.ECharts | null = null
const forecastData = ref<{
  timestamps: string[]
  predicted_usage: number[]
  confidence_upper: number[]
  confidence_lower: number[]
  is_demo: boolean
  expansion_suggestions: ExpansionSuggestion[]
}>({
  timestamps: [],
  predicted_usage: [],
  confidence_upper: [],
  confidence_lower: [],
  is_demo: false,
  expansion_suggestions: []
})

const trendTypeLabels: Record<string, string> = {
  space: '空间容量',
  power: '电力容量',
  cooling: '制冷容量',
  weight: '承重容量'
}

async function loadTrendData() {
  try {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - parseInt(trendRange.value))

    const res = await getCapacityTrend({
      type: trendType.value as 'space' | 'power' | 'cooling' | 'weight',
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      interval: trendInterval.value as 'hour' | 'day' | 'week' | 'month'
    })

    const trendData = (res as any)?.data ?? res
    if (trendData) {
      renderTrendChart(trendData)
    }
  } catch (e) {
    console.error('加载趋势数据失败', e)
  }
}

function renderTrendChart(data: { timestamps: string[], total: number[], used: number[], usage_rate: number[] }) {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['总量', '已用量', '使用率'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: data.timestamps, axisLabel: { rotate: 30 } },
    yAxis: [
      { type: 'value', name: '容量值' },
      { type: 'value', name: '使用率(%)', min: 0, max: 100, axisLabel: { formatter: '{value}%' } }
    ],
    series: [
      {
        name: '总量',
        type: 'line',
        data: data.total,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: '#91CC75' }
      },
      {
        name: '已用量',
        type: 'line',
        data: data.used,
        itemStyle: { color: '#5470C6' }
      },
      {
        name: '使用率',
        type: 'line',
        yAxisIndex: 1,
        data: data.usage_rate,
        itemStyle: { color: '#EE6666' }
      }
    ]
  }
  trendChart.setOption(option)
}

async function loadForecastData() {
  try {
    const res = await getCapacityForecast({
      type: trendType.value as 'space' | 'power' | 'cooling' | 'weight',
      days: forecastDays.value
    })

    const fcData = (res as any)?.data ?? res
    if (fcData) {
      forecastData.value = fcData
      renderForecastChart(fcData)
    }
  } catch (e) {
    console.error('加载预测数据失败', e)
  }
}

function renderForecastChart(data: typeof forecastData.value) {
  if (!forecastChartRef.value) return
  if (!forecastChart) {
    forecastChart = echarts.init(forecastChartRef.value)
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let result = params[0]?.axisValue + '<br/>'
        params.forEach((p: any) => {
          if (p.seriesName !== '置信下界') {
            result += `${p.marker}${p.seriesName}: ${p.value?.toFixed?.(1) ?? '-'}%<br/>`
          }
        })
        result += '<span style="color:#999;font-size:11px;">预测仅供参考</span>'
        return result
      }
    },
    legend: { data: ['预测使用率', '置信上界'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: data.timestamps, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '使用率(%)', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '预测使用率',
        type: 'line',
        data: data.predicted_usage,
        itemStyle: { color: '#5470C6' },
        markLine: {
          silent: true,
          data: [{ yAxis: 80, label: { formatter: '阈值 80%' }, lineStyle: { color: '#EE6666', type: 'dashed' } }]
        }
      },
      {
        name: '置信上界',
        type: 'line',
        data: data.confidence_upper,
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(84,112,198,0.15)' },
        symbol: 'none'
      },
      {
        name: '置信下界',
        type: 'line',
        data: data.confidence_lower,
        lineStyle: { opacity: 0 },
        areaStyle: { color: '#fff', origin: 'start' },
        symbol: 'none'
      }
    ]
  }
  forecastChart.setOption(option)
}

function handleTrendChartResize() {
  trendChart?.resize()
  forecastChart?.resize()
}

onUnmounted(() => {
  window.removeEventListener('resize', handleTrendChartResize)
  trendChart?.dispose()
  forecastChart?.dispose()
})

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
@use '@/styles/mixins-25d' as *;

.capacity-page {
  @include page-dashboard(4);
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

  :deep(.alert-row-warning) {
    td.el-table__cell {
      background-color: rgba(230, 162, 60, 0.1) !important;
    }
  }

  :deep(.alert-row-critical) {
    td.el-table__cell {
      background-color: rgba(245, 108, 108, 0.1) !important;
    }
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
