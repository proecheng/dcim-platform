<template>
  <div class="alarm-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 告警记录标签 -->
      <el-tab-pane label="告警记录" name="records">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>告警管理</span>
              <el-button type="primary" @click="batchAck" :disabled="!selectedIds.length">
                批量确认 ({{ selectedIds.length }})
              </el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="filter-form">
            <el-form-item label="告警状态">
              <el-select v-model="filters.status" placeholder="全部" clearable>
                <el-option label="活动" value="active" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
              </el-select>
            </el-form-item>
            <el-form-item label="告警级别">
              <el-select v-model="filters.level" placeholder="全部" clearable>
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item label="设备类型">
              <el-select v-model="filters.device_type" placeholder="全部" clearable>
                <el-option
                  v-for="dt in deviceTypeOptions"
                  :key="dt"
                  :label="dt"
                  :value="dt"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadAlarms">查询</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 告警统计 -->
          <div class="alarm-stats">
            <el-tag type="danger" effect="dark">紧急: {{ alarmCount.critical }}</el-tag>
            <el-tag type="warning" effect="dark">重要: {{ alarmCount.major }}</el-tag>
            <el-tag type="primary" effect="dark">一般: {{ alarmCount.minor }}</el-tag>
            <el-tag type="info" effect="dark">提示: {{ alarmCount.info }}</el-tag>
          </div>

          <!-- 告警列表 -->
          <el-table
            :data="alarms"
            stripe
            border
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="alarm_level" label="级别" width="80">
              <template #default="{ row }">
                <el-tag :type="getLevelTagType(row.alarm_level)" size="small">
                  {{ getLevelText(row.alarm_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="升级" width="80">
              <template #default="{ row }">
                <el-tooltip v-if="row.escalated_from" :content="row.escalation_remark || `从 ${getLevelText(row.escalated_from)} 升级`" placement="top">
                  <el-tag type="warning" size="small">已升级</el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="point_code" label="点位编码" width="150" />
            <el-table-column prop="point_name" label="点位名称" width="150" />
            <el-table-column prop="alarm_message" label="告警内容" min-width="200" />
            <el-table-column prop="trigger_value" label="触发值" width="100">
              <template #default="{ row }">
                {{ row.trigger_value != null ? row.trigger_value : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="threshold_value" label="阈值" width="100">
              <template #default="{ row }">
                {{ row.threshold_value != null ? row.threshold_value : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="告警时间" width="180" />
            <el-table-column prop="acknowledged_at" label="确认时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.acknowledged_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="resolved_at" label="解决时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.resolved_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="duration_seconds" label="持续时间" width="120">
              <template #default="{ row }">
                {{ formatDuration(row.duration_seconds) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'active'"
                  type="primary"
                  link
                  @click="handleAck(row.id)"
                >
                  确认
                </el-button>
                <el-button
                  v-if="row.status === 'active' || row.status === 'acknowledged'"
                  type="warning"
                  link
                  @click="handleProcess(row.id)"
                >
                  处理
                </el-button>
                <el-button
                  v-if="row.status !== 'resolved'"
                  type="success"
                  link
                  @click="handleResolve(row.id)"
                >
                  解除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadAlarms"
            @current-change="loadAlarms"
          />
        </el-card>
      </el-tab-pane>

      <!-- 告警规则标签 -->
      <el-tab-pane label="告警规则" name="rules">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>告警规则管理</span>
              <el-button type="primary" @click="handleAddRule">新增规则</el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="filter-form">
            <el-form-item label="规则类型">
              <el-select v-model="ruleFilters.rule_type" placeholder="全部" clearable>
                <el-option label="与" value="and" />
                <el-option label="或" value="or" />
                <el-option label="序列" value="sequence" />
              </el-select>
            </el-form-item>
            <el-form-item label="告警级别">
              <el-select v-model="ruleFilters.alarm_level" placeholder="全部" clearable>
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item label="启用状态">
              <el-select v-model="ruleFilters.is_enabled" placeholder="全部" clearable>
                <el-option label="启用" :value="true" />
                <el-option label="禁用" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadRules">查询</el-button>
              <el-button @click="resetRuleFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 规则列表 -->
          <el-table :data="rules" stripe border>
            <el-table-column prop="rule_name" label="规则名称" min-width="150" />
            <el-table-column prop="rule_type" label="规则类型" width="100">
              <template #default="{ row }">
                <el-tag :type="getRuleTypeTagType(row.rule_type)" size="small">
                  {{ getRuleTypeText(row.rule_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="alarm_level" label="告警级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getLevelTagType(row.alarm_level)" size="small">
                  {{ getLevelText(row.alarm_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="alarm_message" label="告警消息" min-width="200" show-overflow-tooltip />
            <el-table-column prop="condition_expr" label="条件表达式" min-width="200" show-overflow-tooltip />
            <el-table-column prop="is_enabled" label="启用" width="80">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_enabled"
                  :before-change="() => handleToggleRule(row)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditRule(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeleteRule(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="rulePagination.page"
            v-model:page-size="rulePagination.pageSize"
            :total="rulePagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadRules"
            @current-change="loadRules"
          />
        </el-card>
      </el-tab-pane>

      <!-- 告警屏蔽标签 -->
      <el-tab-pane label="告警屏蔽" name="shields">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>告警屏蔽管理</span>
              <el-button type="primary" @click="handleAddShield">新增屏蔽</el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="filter-form">
            <el-form-item label="点位">
              <el-select v-model="shieldFilters.point_id" placeholder="全部（含全局）" clearable filterable>
                <el-option label="全局屏蔽" :value="null" />
                <el-option
                  v-for="point in pointOptions"
                  :key="point.id"
                  :label="point.point_name"
                  :value="point.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="告警级别">
              <el-select v-model="shieldFilters.alarm_level" placeholder="全部" clearable>
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadShields">查询</el-button>
              <el-button @click="resetShieldFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 屏蔽列表 -->
          <el-table :data="shields" stripe border>
            <el-table-column prop="point_code" label="点位编码" width="120">
              <template #default="{ row }">
                {{ row.point_code || '全局' }}
              </template>
            </el-table-column>
            <el-table-column prop="point_name" label="点位名称" width="150">
              <template #default="{ row }">
                {{ row.point_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="alarm_level" label="屏蔽级别" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.alarm_level" :type="getLevelTagType(row.alarm_level)" size="small">
                  {{ getLevelText(row.alarm_level) }}
                </el-tag>
                <el-tag v-else type="info" size="small">全部</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="start_time" label="开始时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.start_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="end_time" label="结束时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.end_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="屏蔽原因" min-width="200" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '生效中' : '已过期' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" link @click="handleDeleteShield(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="shieldPagination.page"
            v-model:page-size="shieldPagination.pageSize"
            :total="shieldPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadShields"
            @current-change="loadShields"
          />
        </el-card>
      </el-tab-pane>

      <!-- 升级规则标签 -->
      <el-tab-pane label="升级规则" name="escalations">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>升级规则管理</span>
              <el-button type="primary" @click="handleAddEscalation">新增规则</el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="filter-form">
            <el-form-item label="源级别">
              <el-select v-model="escalationFilters.source_level" placeholder="全部" clearable>
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item label="启用状态">
              <el-select v-model="escalationFilters.is_enabled" placeholder="全部" clearable>
                <el-option label="启用" :value="true" />
                <el-option label="禁用" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadEscalations">查询</el-button>
              <el-button @click="resetEscalationFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 升级规则列表 -->
          <el-table :data="escalations" stripe border>
            <el-table-column prop="rule_name" label="规则名称" min-width="150" />
            <el-table-column prop="source_level" label="源级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getLevelTagType(row.source_level)" size="small">
                  {{ getLevelText(row.source_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="timeout_minutes" label="超时时间" width="120">
              <template #default="{ row }">
                {{ row.timeout_minutes }} 分钟
              </template>
            </el-table-column>
            <el-table-column prop="target_level" label="目标级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getLevelTagType(row.target_level)" size="small">
                  {{ getLevelText(row.target_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notify_user_ids" label="通知人数" width="100">
              <template #default="{ row }">
                {{ row.notify_user_ids ? row.notify_user_ids.length : 0 }} 人
              </template>
            </el-table-column>
            <el-table-column prop="is_enabled" label="启用" width="80">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_enabled"
                  :before-change="() => handleToggleEscalation(row)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditEscalation(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeleteEscalation(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="escalationPagination.page"
            v-model:page-size="escalationPagination.pageSize"
            :total="escalationPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadEscalations"
            @current-change="loadEscalations"
          />
        </el-card>
      </el-tab-pane>

      <!-- 阈值规则标签 -->
      <el-tab-pane label="阈值规则" name="thresholds">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>阈值规则管理</span>
              <el-button type="primary" @click="handleAddThreshold">新增阈值</el-button>
            </div>
          </template>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="filter-form">
            <el-form-item label="阈值类型">
              <el-select v-model="thresholdFilters.threshold_type" placeholder="全部" clearable>
                <el-option label="高高" value="high_high" />
                <el-option label="高" value="high" />
                <el-option label="低" value="low" />
                <el-option label="低低" value="low_low" />
                <el-option label="等于" value="equal" />
                <el-option label="变化" value="change" />
              </el-select>
            </el-form-item>
            <el-form-item label="启用状态">
              <el-select v-model="thresholdFilters.is_enabled" placeholder="全部" clearable>
                <el-option label="启用" :value="true" />
                <el-option label="禁用" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadThresholds">查询</el-button>
              <el-button @click="resetThresholdFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 阈值列表 -->
          <el-table :data="thresholds" stripe border>
            <el-table-column prop="point_name" label="点位名称" min-width="150" />
            <el-table-column prop="threshold_type" label="阈值类型" width="100">
              <template #default="{ row }">
                <el-tag :type="getThresholdTypeTagType(row.threshold_type)" size="small">
                  {{ getThresholdTypeText(row.threshold_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="threshold_value" label="阈值" width="100" />
            <el-table-column prop="alarm_level" label="告警级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getLevelTagType(row.alarm_level)" size="small">
                  {{ getLevelText(row.alarm_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="delay_seconds" label="延迟(秒)" width="100" />
            <el-table-column prop="is_enabled" label="启用" width="80">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_enabled"
                  :before-change="() => handleToggleThreshold(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditThreshold(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeleteThreshold(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="thresholdPagination.page"
            v-model:page-size="thresholdPagination.pageSize"
            :total="thresholdPagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadThresholds"
            @current-change="loadThresholds"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 告警规则对话框 -->
    <el-dialog append-to-body
      v-model="ruleDialogVisible"
      :title="isEditRule ? '编辑告警规则' : '新增告警规则'"
      width="600px"
    >
      <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleFormRules" label-width="100px">
        <el-form-item label="规则名称" prop="rule_name">
          <el-input v-model="ruleForm.rule_name" placeholder="请输入规则名称" />
        </el-form-item>
        <el-form-item label="规则类型" prop="rule_type">
          <el-select v-model="ruleForm.rule_type" placeholder="请选择规则类型">
            <el-option label="与" value="and" />
            <el-option label="或" value="or" />
            <el-option label="序列" value="sequence" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件表达式" prop="condition_expr">
          <el-input
            v-model="ruleForm.condition_expr"
            type="textarea"
            :rows="3"
            placeholder="请输入条件表达式"
          />
        </el-form-item>
        <el-form-item label="告警级别" prop="alarm_level">
          <el-select v-model="ruleForm.alarm_level" placeholder="请选择告警级别">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警消息" prop="alarm_message">
          <el-input
            v-model="ruleForm.alarm_message"
            type="textarea"
            :rows="2"
            placeholder="请输入告警消息"
          />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="ruleForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRuleForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 告警屏蔽对话框 -->
    <el-dialog append-to-body
      v-model="shieldDialogVisible"
      title="新增告警屏蔽"
      width="600px"
    >
      <el-form ref="shieldFormRef" :model="shieldForm" :rules="shieldFormRules" label-width="100px">
        <el-form-item label="点位" prop="point_id">
          <el-select v-model="shieldForm.point_id" placeholder="请选择点位（空表示全局屏蔽）" clearable filterable>
            <el-option label="全局屏蔽（所有点位）" :value="null" />
            <el-option
              v-for="point in pointOptions"
              :key="point.id"
              :label="point.point_name"
              :value="point.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="屏蔽级别" prop="alarm_level">
          <el-select v-model="shieldForm.alarm_level" placeholder="请选择屏蔽级别（空表示全部）" clearable>
            <el-option label="全部级别" :value="null" />
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-date-picker
            v-model="shieldForm.start_time"
            type="datetime"
            placeholder="选择开始时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-date-picker
            v-model="shieldForm.end_time"
            type="datetime"
            placeholder="选择结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="屏蔽原因" prop="reason">
          <el-input
            v-model="shieldForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入屏蔽原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shieldDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitShieldForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 确认告警对话框 -->
    <el-dialog append-to-body v-model="ackDialogVisible" title="确认告警" width="500px">
      <el-form label-width="80px">
        <el-form-item label="备注">
          <el-input
            v-model="ackRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入确认备注（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ackDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAck">确认</el-button>
      </template>
    </el-dialog>

    <!-- 处理告警对话框 -->
    <el-dialog append-to-body v-model="processDialogVisible" title="处理告警" width="500px">
      <el-form label-width="80px">
        <el-form-item label="处理描述">
          <el-input
            v-model="processRemark"
            type="textarea"
            :rows="4"
            placeholder="请输入处理过程描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProcess">提交</el-button>
      </template>
    </el-dialog>

    <!-- 解除告警对话框 -->
    <el-dialog append-to-body v-model="resolveDialogVisible" title="解除告警" width="500px">
      <el-form label-width="80px">
        <el-form-item label="解决类型">
          <el-select v-model="resolveType">
            <el-option label="手动解除" value="manual" />
            <el-option label="超时解除" value="timeout" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="resolveRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入解除备注（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResolve">确认解除</el-button>
      </template>
    </el-dialog>

    <!-- 批量确认对话框 -->
    <el-dialog append-to-body v-model="batchAckDialogVisible" title="批量确认告警" width="500px">
      <p>即将确认 {{ selectedIds.length }} 条告警</p>
      <el-form label-width="80px">
        <el-form-item label="备注">
          <el-input
            v-model="batchAckRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入确认备注（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchAckDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatchAck">确认</el-button>
      </template>
    </el-dialog>

    <!-- 升级规则对话框 -->
    <el-dialog append-to-body
      v-model="escalationDialogVisible"
      :title="isEditEscalation ? '编辑升级规则' : '新增升级规则'"
      width="600px"
    >
      <el-form ref="escalationFormRef" :model="escalationForm" :rules="escalationFormRules" label-width="100px">
        <el-form-item label="规则名称" prop="rule_name">
          <el-input v-model="escalationForm.rule_name" placeholder="请输入规则名称" />
        </el-form-item>
        <el-form-item label="源级别" prop="source_level">
          <el-select v-model="escalationForm.source_level" placeholder="请选择源级别">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="超时时间" prop="timeout_minutes">
          <el-input-number v-model="escalationForm.timeout_minutes" :min="1" placeholder="分钟" />
          <span style="margin-left: 8px">分钟</span>
        </el-form-item>
        <el-form-item label="目标级别" prop="target_level">
          <el-select v-model="escalationForm.target_level" placeholder="请选择目标级别">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="通知用户ID" prop="notify_user_ids">
          <el-input v-model="escalationForm.notify_user_ids_str" placeholder="多个ID用逗号分隔，如: 1,2,3" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="escalationForm.is_enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="escalationForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="escalationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEscalationForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 阈值规则对话框 -->
    <el-dialog append-to-body
      v-model="thresholdDialogVisible"
      :title="isEditThreshold ? '编辑阈值规则' : '新增阈值规则'"
      width="600px"
    >
      <el-form ref="thresholdFormRef" :model="thresholdForm" :rules="thresholdFormRules" label-width="100px">
        <el-form-item label="点位" prop="point_id">
          <el-select v-model="thresholdForm.point_id" placeholder="请选择点位" filterable>
            <el-option
              v-for="point in pointOptions"
              :key="point.id"
              :label="point.point_name"
              :value="point.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值类型" prop="threshold_type">
          <el-select v-model="thresholdForm.threshold_type" placeholder="请选择阈值类型">
            <el-option label="高高" value="high_high" />
            <el-option label="高" value="high" />
            <el-option label="低" value="low" />
            <el-option label="低低" value="low_low" />
            <el-option label="等于" value="equal" />
            <el-option label="变化" value="change" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值" prop="threshold_value">
          <el-input-number v-model="thresholdForm.threshold_value" :precision="2" placeholder="请输入阈值" />
        </el-form-item>
        <el-form-item label="告警级别" prop="alarm_level">
          <el-select v-model="thresholdForm.alarm_level" placeholder="请选择告警级别">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警消息">
          <el-input v-model="thresholdForm.alarm_message" placeholder="请输入告警消息（可选）" />
        </el-form-item>
        <el-form-item label="延迟秒数">
          <el-input-number v-model="thresholdForm.delay_seconds" :min="0" placeholder="秒" />
        </el-form-item>
        <el-form-item label="死区">
          <el-input-number v-model="thresholdForm.dead_band" :min="0" :precision="2" placeholder="死区值" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="thresholdForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="thresholdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitThresholdForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  getAlarmList, getAlarmCount, acknowledgeAlarm,
  resolveAlarm, batchAcknowledgeAlarms, processAlarm,
  getAlarmRules, createAlarmRule, updateAlarmRule,
  deleteAlarmRule, toggleAlarmRule,
  getAlarmShields, createAlarmShield, deleteAlarmShield,
  getEscalations, createEscalation, updateEscalation,
  deleteEscalation, toggleEscalation,
  type AlarmInfo, type AlarmCount, type AlarmRuleInfo, type AlarmShieldInfo,
  type AlarmEscalationInfo
} from '@/api/modules/alarm'
import {
  getThresholdList, createThreshold, updateThreshold, deleteThreshold,
  type ThresholdInfo
} from '@/api/modules/threshold'
import { getPointList, type PointInfo } from '@/api/modules/point'
import { useAlarm } from '@/composables/useAlarm'

// WebSocket 订阅（不自动拉取数据，不播放声音/通知，仅订阅消息）
useAlarm({ autoFetch: false, autoSubscribe: true, playSound: false, showNotification: false })

// ==================== 标签页 ====================
const activeTab = ref('records')

// ==================== 告警记录 ====================
const alarms = ref<AlarmInfo[]>([])
const alarmCount = ref<AlarmCount>({ critical: 0, major: 0, minor: 0, info: 0, total: 0 })
const selectedIds = ref<number[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const filters = reactive({
  status: '',
  level: '',
  device_type: ''
})

// 设备类型选项（从点位列表提取去重）
const deviceTypeOptions = computed(() => {
  const types = new Set<string>()
  pointOptions.value.forEach(p => {
    if (p.device_type) {
      types.add(p.device_type)
    }
  })
  return Array.from(types)
})

// WebSocket 状态变更事件处理
const handleAlarmStatusChanged = () => {
  loadAlarms()
  loadAlarmCount()
}

onMounted(() => {
  loadAlarms()
  loadAlarmCount()
  loadRules()
  loadShields()
  loadPointOptions()
  loadEscalations()
  loadThresholds()
  window.addEventListener('alarm-status-changed', handleAlarmStatusChanged)
})

onUnmounted(() => {
  window.removeEventListener('alarm-status-changed', handleAlarmStatusChanged)
})

async function loadAlarms() {
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.status) params.status = filters.status
    if (filters.level) params.alarm_level = filters.level
    if (filters.device_type) params.device_type = filters.device_type
    const result = await getAlarmList(params)
    alarms.value = result.items || []
    pagination.total = result.total || 0
  } catch (e) {
    console.error('加载告警失败', e)
    ElMessage.error('加载告警失败')
  }
}

async function loadAlarmCount() {
  try {
    alarmCount.value = await getAlarmCount()
  } catch (e) {
    console.error('获取告警统计失败', e)
  }
}

function resetFilters() {
  filters.status = ''
  filters.level = ''
  filters.device_type = ''
  pagination.page = 1
  loadAlarms()
}

function handleSelectionChange(selection: AlarmInfo[]) {
  selectedIds.value = selection.map(item => item.id)
}

// ==================== 确认对话框 ====================
const ackDialogVisible = ref(false)
const ackTargetId = ref<number | null>(null)
const ackRemark = ref('')

function handleAck(id: number) {
  ackTargetId.value = id
  ackRemark.value = ''
  ackDialogVisible.value = true
}

async function submitAck() {
  if (ackTargetId.value === null) return
  try {
    await acknowledgeAlarm(ackTargetId.value, { remark: ackRemark.value || undefined })
    ElMessage.success('确认成功')
    ackDialogVisible.value = false
    loadAlarms()
    loadAlarmCount()
  } catch (e) {
    console.error('确认失败', e)
    ElMessage.error('确认失败')
  }
}

// ==================== 处理对话框 ====================
const processDialogVisible = ref(false)
const processTargetId = ref<number | null>(null)
const processRemark = ref('')

function handleProcess(id: number) {
  processTargetId.value = id
  processRemark.value = ''
  processDialogVisible.value = true
}

async function submitProcess() {
  if (processTargetId.value === null) return
  if (!processRemark.value.trim()) {
    ElMessage.warning('请输入处理描述')
    return
  }
  try {
    await processAlarm(processTargetId.value, { process_remark: processRemark.value })
    ElMessage.success('处理成功')
    processDialogVisible.value = false
    loadAlarms()
  } catch (e) {
    console.error('处理失败', e)
    ElMessage.error('处理失败')
  }
}

// ==================== 解除对话框 ====================
const resolveDialogVisible = ref(false)
const resolveTargetId = ref<number | null>(null)
const resolveRemark = ref('')
const resolveType = ref<'manual' | 'timeout'>('manual')

function handleResolve(id: number) {
  resolveTargetId.value = id
  resolveRemark.value = ''
  resolveType.value = 'manual'
  resolveDialogVisible.value = true
}

async function submitResolve() {
  if (resolveTargetId.value === null) return
  try {
    await resolveAlarm(resolveTargetId.value, {
      resolve_type: resolveType.value,
      remark: resolveRemark.value || undefined
    })
    ElMessage.success('解除成功')
    resolveDialogVisible.value = false
    loadAlarms()
    loadAlarmCount()
  } catch (e) {
    console.error('解除失败', e)
    ElMessage.error('解除失败')
  }
}

// ==================== 批量确认 ====================
const batchAckDialogVisible = ref(false)
const batchAckRemark = ref('')

function batchAck() {
  if (selectedIds.value.length === 0) return
  batchAckRemark.value = ''
  batchAckDialogVisible.value = true
}

async function submitBatchAck() {
  if (selectedIds.value.length === 0) return
  try {
    await batchAcknowledgeAlarms(selectedIds.value, batchAckRemark.value || undefined)
    ElMessage.success('批量确认成功')
    batchAckDialogVisible.value = false
    loadAlarms()
    loadAlarmCount()
    selectedIds.value = []
  } catch (e) {
    console.error('批量确认失败', e)
    ElMessage.error('批量确认失败')
  }
}

// ==================== 告警规则 ====================
const rules = ref<AlarmRuleInfo[]>([])
const rulePagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const ruleFilters = reactive({
  rule_type: '',
  alarm_level: '',
  is_enabled: undefined as boolean | undefined
})

async function loadRules() {
  try {
    const params: Record<string, string | number | boolean> = {
      page: rulePagination.page,
      page_size: rulePagination.pageSize
    }
    if (ruleFilters.rule_type) params.rule_type = ruleFilters.rule_type
    if (ruleFilters.alarm_level) params.alarm_level = ruleFilters.alarm_level
    if (typeof ruleFilters.is_enabled === 'boolean') params.is_enabled = ruleFilters.is_enabled
    const result = await getAlarmRules(params)
    rules.value = result.items || []
    rulePagination.total = result.total || 0
  } catch (e) {
    console.error('加载告警规则失败', e)
    ElMessage.error('加载告警规则失败')
  }
}

function resetRuleFilters() {
  ruleFilters.rule_type = ''
  ruleFilters.alarm_level = ''
  ruleFilters.is_enabled = undefined
  rulePagination.page = 1
  loadRules()
}

// 规则表单
const ruleDialogVisible = ref(false)
const isEditRule = ref(false)
const currentRuleId = ref<number | null>(null)
const ruleFormRef = ref()

const ruleForm = reactive({
  rule_name: '',
  rule_type: 'and' as 'and' | 'or' | 'sequence',
  condition_expr: '',
  alarm_level: 'minor' as 'critical' | 'major' | 'minor' | 'info',
  alarm_message: '',
  is_enabled: true
})

const ruleFormRules = {
  rule_name: [
    { required: true, message: '请输入规则名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  rule_type: [
    { required: true, message: '请选择规则类型', trigger: 'change' }
  ],
  alarm_level: [
    { required: true, message: '请选择告警级别', trigger: 'change' }
  ],
  alarm_message: [
    { max: 200, message: '长度不超过 200 个字符', trigger: 'blur' }
  ]
}

function handleAddRule() {
  isEditRule.value = false
  currentRuleId.value = null
  ruleForm.rule_name = ''
  ruleForm.rule_type = 'and'
  ruleForm.condition_expr = ''
  ruleForm.alarm_level = 'minor'
  ruleForm.alarm_message = ''
  ruleForm.is_enabled = true
  ruleDialogVisible.value = true
}

function handleEditRule(row: AlarmRuleInfo) {
  isEditRule.value = true
  currentRuleId.value = row.id
  ruleForm.rule_name = row.rule_name
  ruleForm.rule_type = row.rule_type as 'and' | 'or' | 'sequence'
  ruleForm.condition_expr = row.condition_expr || ''
  ruleForm.alarm_level = row.alarm_level
  ruleForm.alarm_message = row.alarm_message || ''
  ruleForm.is_enabled = row.is_enabled
  ruleDialogVisible.value = true
}

async function submitRuleForm() {
  const valid = await ruleFormRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    if (isEditRule.value && currentRuleId.value) {
      await updateAlarmRule(currentRuleId.value, ruleForm)
      ElMessage.success('更新成功')
    } else {
      await createAlarmRule(ruleForm)
      ElMessage.success('创建成功')
    }
    ruleDialogVisible.value = false
    loadRules()
  } catch (e) {
    console.error('保存告警规则失败', e)
    ElMessage.error('保存失败')
  }
}

async function handleDeleteRule(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该告警规则？', '提示', {
      type: 'warning'
    })
    await deleteAlarmRule(id)
    ElMessage.success('删除成功')
    loadRules()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除告警规则失败', e)
      ElMessage.error('删除失败')
    }
  }
}

async function handleToggleRule(row: AlarmRuleInfo): Promise<boolean> {
  try {
    await toggleAlarmRule(row.id)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadRules()
    return true
  } catch (e) {
    console.error('切换状态失败', e)
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 告警屏蔽 ====================
const shields = ref<AlarmShieldInfo[]>([])
const shieldPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const shieldFilters = reactive({
  point_id: undefined as number | null | undefined,
  alarm_level: ''
})

// 点位选项（用于下拉选择）
const pointOptions = ref<PointInfo[]>([])

async function loadPointOptions() {
  try {
    // 系统最大点位数 100，一次加载即可
    const result = await getPointList({ page_size: 100 })
    pointOptions.value = result.items || []
  } catch (e) {
    console.error('加载点位列表失败', e)
  }
}

async function loadShields() {
  try {
    const params: Record<string, string | number> = {
      page: shieldPagination.page,
      page_size: shieldPagination.pageSize
    }
    if (shieldFilters.point_id) params.point_id = shieldFilters.point_id
    if (shieldFilters.alarm_level) params.alarm_level = shieldFilters.alarm_level
    const result = await getAlarmShields(params)
    shields.value = result.items || []
    shieldPagination.total = result.total || 0
  } catch (e) {
    console.error('加载告警屏蔽失败', e)
    ElMessage.error('加载告警屏蔽失败')
  }
}

function resetShieldFilters() {
  shieldFilters.point_id = undefined
  shieldFilters.alarm_level = ''
  shieldPagination.page = 1
  loadShields()
}

// 屏蔽表单
const shieldDialogVisible = ref(false)
const shieldFormRef = ref()

const shieldForm = reactive({
  point_id: null as number | null,
  alarm_level: null as 'critical' | 'major' | 'minor' | 'info' | null,
  start_time: '',
  end_time: '',
  reason: ''
})

const shieldFormRules = {
  start_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' }
  ],
  end_time: [
    { required: true, message: '请选择结束时间', trigger: 'change' }
  ]
}

function handleAddShield() {
  // 加载点位选项
  loadPointOptions()
  // 重置表单
  shieldForm.point_id = null
  shieldForm.alarm_level = null
  shieldForm.start_time = ''
  shieldForm.end_time = ''
  shieldForm.reason = ''
  shieldDialogVisible.value = true
}

async function submitShieldForm() {
  const valid = await shieldFormRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    // 验证时间
    if (new Date(shieldForm.end_time) <= new Date(shieldForm.start_time)) {
      ElMessage.error('结束时间必须晚于开始时间')
      return
    }
    await createAlarmShield(shieldForm)
    ElMessage.success('创建成功')
    shieldDialogVisible.value = false
    loadShields()
  } catch (e) {
    console.error('保存告警屏蔽失败', e)
    ElMessage.error('保存失败')
  }
}

async function handleDeleteShield(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该告警屏蔽？', '提示', {
      type: 'warning'
    })
    await deleteAlarmShield(id)
    ElMessage.success('删除成功')
    loadShields()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除告警屏蔽失败', e)
      ElMessage.error('删除失败')
    }
  }
}

// ==================== 升级规则 ====================
const escalations = ref<AlarmEscalationInfo[]>([])
const escalationPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const escalationFilters = reactive({
  source_level: '',
  is_enabled: undefined as boolean | undefined
})

async function loadEscalations() {
  try {
    const params: Record<string, string | number | boolean> = {
      page: escalationPagination.page,
      page_size: escalationPagination.pageSize
    }
    if (escalationFilters.source_level) params.source_level = escalationFilters.source_level
    if (typeof escalationFilters.is_enabled === 'boolean') params.is_enabled = escalationFilters.is_enabled
    const result = await getEscalations(params)
    escalations.value = result.items || []
    escalationPagination.total = result.total || 0
  } catch (e) {
    console.error('加载升级规则失败', e)
    ElMessage.error('加载升级规则失败')
  }
}

function resetEscalationFilters() {
  escalationFilters.source_level = ''
  escalationFilters.is_enabled = undefined
  escalationPagination.page = 1
  loadEscalations()
}

// 升级规则表单
const escalationDialogVisible = ref(false)
const isEditEscalation = ref(false)
const currentEscalationId = ref<number | null>(null)
const escalationFormRef = ref()

const escalationForm = reactive({
  rule_name: '',
  source_level: 'minor' as string,
  timeout_minutes: 30,
  target_level: 'major' as string,
  notify_user_ids_str: '',
  is_enabled: true,
  description: ''
})

const escalationFormRules = {
  rule_name: [
    { required: true, message: '请输入规则名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  source_level: [
    { required: true, message: '请选择源级别', trigger: 'change' }
  ],
  timeout_minutes: [
    { required: true, message: '请输入超时时间', trigger: 'blur' }
  ],
  target_level: [
    { required: true, message: '请选择目标级别', trigger: 'change' }
  ]
}

function handleAddEscalation() {
  isEditEscalation.value = false
  currentEscalationId.value = null
  escalationForm.rule_name = ''
  escalationForm.source_level = 'minor'
  escalationForm.timeout_minutes = 30
  escalationForm.target_level = 'major'
  escalationForm.notify_user_ids_str = ''
  escalationForm.is_enabled = true
  escalationForm.description = ''
  escalationDialogVisible.value = true
}

function handleEditEscalation(row: AlarmEscalationInfo) {
  isEditEscalation.value = true
  currentEscalationId.value = row.id
  escalationForm.rule_name = row.rule_name
  escalationForm.source_level = row.source_level
  escalationForm.timeout_minutes = row.timeout_minutes
  escalationForm.target_level = row.target_level
  escalationForm.notify_user_ids_str = row.notify_user_ids ? row.notify_user_ids.join(',') : ''
  escalationForm.is_enabled = row.is_enabled
  escalationForm.description = row.description || ''
  escalationDialogVisible.value = true
}

async function submitEscalationForm() {
  const valid = await escalationFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const notify_user_ids = escalationForm.notify_user_ids_str
    ? escalationForm.notify_user_ids_str.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
    : []

  try {
    const payload = {
      rule_name: escalationForm.rule_name,
      source_level: escalationForm.source_level,
      timeout_minutes: escalationForm.timeout_minutes,
      target_level: escalationForm.target_level,
      notify_user_ids,
      is_enabled: escalationForm.is_enabled,
      description: escalationForm.description || undefined
    }
    if (isEditEscalation.value && currentEscalationId.value) {
      await updateEscalation(currentEscalationId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createEscalation(payload)
      ElMessage.success('创建成功')
    }
    escalationDialogVisible.value = false
    loadEscalations()
  } catch (e) {
    console.error('保存升级规则失败', e)
    ElMessage.error('保存失败')
  }
}

async function handleDeleteEscalation(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该升级规则？', '提示', {
      type: 'warning'
    })
    await deleteEscalation(id)
    ElMessage.success('删除成功')
    loadEscalations()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除升级规则失败', e)
      ElMessage.error('删除失败')
    }
  }
}

async function handleToggleEscalation(row: AlarmEscalationInfo): Promise<boolean> {
  try {
    await toggleEscalation(row.id)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadEscalations()
    return true
  } catch (e) {
    console.error('切换状态失败', e)
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 阈值规则 ====================
const thresholds = ref<ThresholdInfo[]>([])
const thresholdPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const thresholdFilters = reactive({
  threshold_type: '',
  is_enabled: undefined as boolean | undefined
})

async function loadThresholds() {
  try {
    const params: Record<string, string | number | boolean> = {
      page: thresholdPagination.page,
      page_size: thresholdPagination.pageSize
    }
    if (thresholdFilters.threshold_type) params.threshold_type = thresholdFilters.threshold_type
    if (typeof thresholdFilters.is_enabled === 'boolean') params.is_enabled = thresholdFilters.is_enabled
    const result = await getThresholdList(params)
    thresholds.value = result.items || []
    thresholdPagination.total = result.total || 0
  } catch (e) {
    console.error('加载阈值规则失败', e)
    ElMessage.error('加载阈值规则失败')
  }
}

function resetThresholdFilters() {
  thresholdFilters.threshold_type = ''
  thresholdFilters.is_enabled = undefined
  thresholdPagination.page = 1
  loadThresholds()
}

// 阈值表单
const thresholdDialogVisible = ref(false)
const isEditThreshold = ref(false)
const currentThresholdId = ref<number | null>(null)
const thresholdFormRef = ref()

const thresholdForm = reactive({
  point_id: undefined as number | undefined,
  threshold_type: 'high' as string,
  threshold_value: 0,
  alarm_level: 'minor' as string,
  alarm_message: '',
  delay_seconds: 0,
  dead_band: 0,
  is_enabled: true
})

const thresholdFormRules = {
  point_id: [
    { required: true, message: '请选择点位', trigger: 'change' }
  ],
  threshold_type: [
    { required: true, message: '请选择阈值类型', trigger: 'change' }
  ],
  threshold_value: [
    { required: true, message: '请输入阈值', trigger: 'blur' }
  ],
  alarm_level: [
    { required: true, message: '请选择告警级别', trigger: 'change' }
  ]
}

function handleAddThreshold() {
  isEditThreshold.value = false
  currentThresholdId.value = null
  thresholdForm.point_id = undefined
  thresholdForm.threshold_type = 'high'
  thresholdForm.threshold_value = 0
  thresholdForm.alarm_level = 'minor'
  thresholdForm.alarm_message = ''
  thresholdForm.delay_seconds = 0
  thresholdForm.dead_band = 0
  thresholdForm.is_enabled = true
  thresholdDialogVisible.value = true
}

function handleEditThreshold(row: ThresholdInfo) {
  isEditThreshold.value = true
  currentThresholdId.value = row.id
  thresholdForm.point_id = row.point_id
  thresholdForm.threshold_type = row.threshold_type
  thresholdForm.threshold_value = row.threshold_value
  thresholdForm.alarm_level = row.alarm_level
  thresholdForm.alarm_message = row.alarm_message || ''
  thresholdForm.delay_seconds = row.delay_seconds
  thresholdForm.dead_band = row.dead_band
  thresholdForm.is_enabled = row.is_enabled
  thresholdDialogVisible.value = true
}

async function submitThresholdForm() {
  const valid = await thresholdFormRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    const payload = {
      point_id: thresholdForm.point_id!,
      threshold_type: thresholdForm.threshold_type as ThresholdInfo['threshold_type'],
      threshold_value: thresholdForm.threshold_value,
      alarm_level: thresholdForm.alarm_level as ThresholdInfo['alarm_level'],
      alarm_message: thresholdForm.alarm_message || undefined,
      delay_seconds: thresholdForm.delay_seconds,
      dead_band: thresholdForm.dead_band,
      is_enabled: thresholdForm.is_enabled
    }
    if (isEditThreshold.value && currentThresholdId.value) {
      await updateThreshold(currentThresholdId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createThreshold(payload)
      ElMessage.success('创建成功')
    }
    thresholdDialogVisible.value = false
    loadThresholds()
  } catch (e) {
    console.error('保存阈值规则失败', e)
    ElMessage.error('保存失败')
  }
}

async function handleDeleteThreshold(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该阈值规则？', '提示', {
      type: 'warning'
    })
    await deleteThreshold(id)
    ElMessage.success('删除成功')
    loadThresholds()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除阈值规则失败', e)
      ElMessage.error('删除失败')
    }
  }
}

async function handleToggleThreshold(row: ThresholdInfo): Promise<boolean> {
  try {
    await updateThreshold(row.id, { is_enabled: !row.is_enabled })
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadThresholds()
    return true
  } catch (e) {
    console.error('切换状态失败', e)
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 工具函数 ====================
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function getLevelTagType(level: string): TagType {
  const map: Record<string, TagType> = {
    critical: 'danger',
    major: 'warning',
    minor: 'primary',
    info: 'info'
  }
  return map[level] || 'info'
}

function getLevelText(level: string) {
  const map: Record<string, string> = {
    critical: '紧急',
    major: '重要',
    minor: '一般',
    info: '提示'
  }
  return map[level] || level
}

function getStatusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    active: 'danger',
    acknowledged: 'warning',
    resolved: 'success'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    active: '活动',
    acknowledged: '已确认',
    resolved: '已解决'
  }
  return map[status] || status
}

function getRuleTypeTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    and: 'primary',
    or: 'warning',
    sequence: 'success'
  }
  return map[type] || 'info'
}

function getRuleTypeText(type: string) {
  const map: Record<string, string> = {
    and: '与',
    or: '或',
    sequence: '序列'
  }
  return map[type] || type
}

function formatDate(date: string | null) {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}小时${mins}分`
}

function getThresholdTypeTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    high_high: 'danger',
    high: 'warning',
    low: 'primary',
    low_low: 'info',
    equal: 'success',
    change: 'warning'
  }
  return map[type] || 'info'
}

function getThresholdTypeText(type: string) {
  const map: Record<string, string> = {
    high_high: '高高',
    high: '高',
    low: '低',
    low_low: '低低',
    equal: '等于',
    change: '变化'
  }
  return map[type] || type
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.alarm-page {
  @include page-list;
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .filter-form {
    margin-bottom: 20px;
  }

  .alarm-stats {
    margin-bottom: 20px;
    display: flex;
    gap: 10px;
  }

  .pagination {
    margin-top: 20px;
    justify-content: flex-end;
  }
}
</style>
