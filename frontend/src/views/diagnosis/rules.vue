<script setup lang="ts">
// Admin-only YAML reload and CRUD for diagnosis rules
import { ref, reactive, computed, onMounted } from 'vue';
import { getDiagnosisRules, createDiagnosisRule, updateDiagnosisRule, deleteDiagnosisRule, toggleDiagnosisRule, reloadDiagnosisRules } from '@/api/modules/diagnosis';
import { useUserStore } from '@/stores/user';
import { ElMessage } from 'element-plus';

const userStore = useUserStore();

const rules = ref<Array<any>>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const dialogVisible = ref(false);
const dialogMode = ref<'create'|'edit'>('create');
const defaultTriggerCondition = () => ({
  expression: 'true',
  source: 'manual'
});
const defaultDiagnosisLogic = () => ({
  causes: [],
  suggested_actions: []
});
const defaultRule = () => ({
  rule_code: '',
  name: '',
  description: '',
  category: 'temperature',
  is_enabled: true,
  is_system: false,
  priority: 0,
  trigger_condition: defaultTriggerCondition(),
  diagnosis_logic: defaultDiagnosisLogic()
});
const currentRule = reactive<any>(defaultRule());
const ruleForm = ref(null);

const categoryLabelMap: Record<string, string> = {
  temperature: '温度',
  humidity: '湿度',
  power: '电力',
  communication: '通信',
  security: '安防',
  cooling: '制冷',
  environment: '环境',
  composite: '综合'
};

const isAdmin = computed(() => userStore.isAdmin);

async function loadRules() {
  loading.value = true;
  try {
    const res = await getDiagnosisRules({ page: page.value, page_size: pageSize.value });
    rules.value = res?.items ?? [];
    total.value = res?.total ?? 0;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  dialogMode.value = 'create';
  Object.assign(currentRule, defaultRule());
  dialogVisible.value = true;
}

function editRule(rule: any) {
  dialogMode.value = 'edit';
  Object.assign(currentRule, rule);
  dialogVisible.value = true;
}

async function saveRule() {
  try {
    const payload = {
      name: currentRule.name,
      description: currentRule.description || '',
      category: currentRule.category || 'temperature',
      trigger_condition: currentRule.trigger_condition ?? defaultTriggerCondition(),
      diagnosis_logic: currentRule.diagnosis_logic ?? defaultDiagnosisLogic(),
      priority: currentRule.priority ?? 0,
      is_enabled: currentRule.is_enabled ?? true
    };
    if (dialogMode.value === 'create') {
      await createDiagnosisRule({
        rule_code: currentRule.rule_code,
        ...payload
      });
      ElMessage({ type: 'success', message: '创建成功' });
    } else {
      await updateDiagnosisRule(currentRule.id, payload);
      ElMessage({ type: 'success', message: '更新成功' });
    }
    await loadRules();
    dialogVisible.value = false;
  } catch (e) {
    console.error(e);
    ElMessage({ type: 'error', message: '保存失败' });
  }
}

async function deleteRule(rule: any) {
  if (rule.is_system) return;
  try {
    await deleteDiagnosisRule(rule.id);
    await loadRules();
  } catch (e) {
    console.error(e);
  }
}

async function onToggle(rule: any) {
  try {
    await toggleDiagnosisRule(rule.id);
    await loadRules();
  } catch (e) {
    console.error(e);
    // 恢复开关状态
    rule.is_enabled = !rule.is_enabled;
  }
}

async function reloadRulesYaml() {
  if (!isAdmin.value) return;
  try {
    await reloadDiagnosisRules();
    ElMessage({ type: 'success', message: '规则 YAML 已重新加载' });
    await loadRules();
  } catch (e) {
    console.error(e);
  }
}

function onPageChange(newPage: number) {
  page.value = newPage;
  loadRules();
}

onMounted(() => {
  loadRules();
});
</script>

<template>
  <el-card shadow="never" class="box-card" bordered>
    <div class="toolbar" style="display:flex; gap:8px; align-items:center; margin-bottom:12px;">
      <el-button type="primary" size="small" @click="openCreate">新建规则</el-button>
      <el-button v-if="isAdmin" size="small" @click="reloadRulesYaml">Reload YAML</el-button>
    </div>

    <el-table :data="rules" style="width: 100%" :loading="loading" row-key="rule_code">
      <el-table-column prop="rule_code" label="规则编码" width="140" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="类别" width="120">
        <template #default="scope">{{ categoryLabelMap[scope.row.category] ?? scope.row.category }}</template>
      </el-table-column>
      <el-table-column label="启用" width="100">
        <template #default="scope">
          <el-switch v-model="scope.row.is_enabled" @change="() => onToggle(scope.row)" />
        </template>
      </el-table-column>
      <el-table-column label="系统" width="100">
        <template #default="scope">
          <el-tag v-if="scope.row.is_system" type="danger">系统</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="100" />
      <el-table-column label="操作" width="140">
        <template #default="scope">
          <el-button size="small" @click="editRule(scope.row)" :disabled="scope.row.is_system">编辑</el-button>
          <el-button size="small" type="danger" @click="() => deleteRule(scope.row)" :disabled="scope.row.is_system">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="onPageChange"
      style="margin-top: 12px;"
    />

    <el-dialog append-to-body :title="dialogMode === 'create' ? '新建规则' : '编辑规则'" v-model="dialogVisible">
      <el-form :model="currentRule" ref="ruleForm" label-width="120px">
        <el-form-item label="规则编码" prop="rule_code">
          <el-input v-model="currentRule.rule_code" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="currentRule.name" />
        </el-form-item>
        <el-form-item label="类别" prop="category">
          <el-select v-model="currentRule.category" placeholder="请选择">
            <el-option v-for="(label, key) in categoryLabelMap" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用" prop="is_enabled">
          <el-switch v-model="currentRule.is_enabled" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-input-number v-model="currentRule.priority" :min="0" :max="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 8px; }
</style>
