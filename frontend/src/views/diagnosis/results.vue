<script setup lang="ts">
// Auto-imports enabled: ref, reactive, computed, onMounted, etc.
import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { getDiagnosisResults } from '@/api/modules/diagnosis';

type Cause = { cause: string; confidence: number; suggested_actions: string[]; rule_code?: string };
type DiagnosisRow = {
  alarm_no: string;
  device_type: string;
  zone: string;
  causes_count?: number;
  top_confidence?: number;
  diagnosis_time_ms?: number;
  created_at?: string;
  causes?: Cause[];
};

const route = useRoute();

const loading = ref(false);
const diagnosisResults = ref<DiagnosisRow[]>([]);
const total = ref(0);

const deviceTypeMap: Record<string, string> = {
  TH: '温湿度',
  UPS: 'UPS电源',
  PDU: '配电柜',
  AC: '精密空调',
  DOOR: '门禁',
  SMOKE: '烟感',
  WATER: '漏水',
  IR: '红外',
  FAN: '风机',
  LIGHT: '照明',
};

const categoryMap: Record<string, string> = {
  temperature: '温度',
  humidity: '湿度',
  power: '电力',
  communication: '通信',
  security: '安防',
  cooling: '制冷',
  environment: '环境',
  composite: '综合',
};

const filters = reactive({
  device_type: '',
  zone: '',
  dateRange: [] as string[],
  search: '',
  alarm_id: '',
  page: 1,
  pageSize: 10,
});

const zones = computed(() => {
  const s = diagnosisResults.value.map((r) => r.zone).filter(Boolean);
  return Array.from(new Set(s));
});

async function loadResults() {
  loading.value = true;
  try {
    const params: any = {
      device_type: filters.device_type,
      zone: filters.zone,
      start_date: filters.dateRange?.[0],
      end_date: filters.dateRange?.[1],
      search: filters.search,
      alarm_id: filters.alarm_id,
      page: filters.page,
      page_size: filters.pageSize,
    };
    const res = await getDiagnosisResults(params);
    diagnosisResults.value = res?.items ?? [];
    total.value = res?.total ?? 0;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  filters.page = 1;
  loadResults();
}

function onReset() {
  filters.device_type = '';
  filters.zone = '';
  filters.dateRange = [];
  filters.search = '';
  filters.alarm_id = '';
  filters.page = 1;
  loadResults();
}

function onPageChange(page: number) {
  filters.page = page;
  loadResults();
}

function formatDeviceType(row: DiagnosisRow) {
  return deviceTypeMap[row.device_type] ?? row.device_type;
}

function categoryLabel(cat: string) {
  return categoryMap[cat] ?? cat;
}

onMounted(() => {
  const q = route.query as any;
  if (q?.alarm_id) {
    filters.alarm_id = q.alarm_id;
  }
  loadResults();
});
</script>

<template>
  <el-card shadow="never" class="box-card" bordered>
    <div class="filter-bar" style="display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap;">
      <el-form inline label-width="110px" class="filter-form">
        <el-form-item label="设备类型">
          <el-select v-model="filters.device_type" placeholder="全部" clearable style="width: 180px;">
            <el-option v-for="(label, key) in deviceTypeMap" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-select v-model="filters.zone" placeholder="全部" clearable style="width: 180px;">
            <el-option v-for="z in zones" :key="z" :label="z" :value="z" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="filters.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="filters.search" placeholder="告警号/设备/区域" size="small" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="small" @click="onSearch">查询</el-button>
          <el-button size="small" @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="diagnosisResults" style="width: 100%" :loading="loading" row-key="alarm_no">
      <el-table-column prop="alarm_no" label="告警号" width="140" />
      <el-table-column label="设备类型" width="120">
        <template #default="scope">{{ formatDeviceType(scope.row) }}</template>
      </el-table-column>
      <el-table-column prop="zone" label="区域" width="120" />
      <el-table-column label="原因数量" width="120">
        <template #default="scope">{{ (scope.row.causes?.length ?? 0) }}</template>
      </el-table-column>
      <el-table-column label="最高置信度" width="150">
        <template #default="scope">
          <el-tag type="success" :plain="true">{{ ((scope.row.top_confidence ?? 0) * 100).toFixed(1) }}%</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="diagnosis_time_ms" label="诊断耗时 (ms)" width="180" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column type="expand">
        <template #content="scope">
          <el-table :data="scope.row.causes" size="small" border style="width: 100%">
            <el-table-column prop="category" label="类别" width="120">
              <template #default="rowScope">{{ categoryLabel(rowScope.row.category) }}</template>
            </el-table-column>
            <el-table-column label="置信度" width="120">
              <template #default="rowScope">
                <el-progress :percentage="(rowScope.row.confidence ?? 0) * 100"></el-progress>
              </template>
            </el-table-column>
            <el-table-column prop="suggested_actions" label="建议动作" />
          </el-table>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="filters.page"
      :page-size="filters.pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="onPageChange"
      style="margin-top: 12px;"
    />
  </el-card>
</template>

<style scoped>
.filter-bar { padding: 0; margin-bottom: 8px; }
.filter-form { display: flex; gap: 12px; align-items: center; }
</style>
