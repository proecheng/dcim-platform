<template>
  <div class="constraint-check-result">
    <el-alert
      :title="summaryTitle"
      :type="summaryPassed ? 'success' : 'error'"
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-descriptions :column="2" border v-if="result.constraint_details">
      <el-descriptions-item label="功率约束">
        <el-tag :type="result.constraint_details.power?.is_valid ? 'success' : 'danger'">
          {{ result.constraint_details.power?.is_valid ? '通过' : '未通过' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="时间约束">
        <el-tag :type="result.constraint_details.time?.is_valid ? 'success' : 'danger'">
          {{ result.constraint_details.time?.is_valid ? '通过' : '未通过' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="设备约束">
        <el-tag :type="result.constraint_details.device?.is_valid ? 'success' : 'danger'">
          {{ result.constraint_details.device?.is_valid ? '通过' : '未通过' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="安全约束">
        <el-tag :type="result.constraint_details.safety?.is_valid ? 'success' : 'danger'">
          {{ result.constraint_details.safety?.is_valid ? '通过' : '未通过' }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="result.violated_constraints && result.violated_constraints.length" style="margin-top: 16px">
      <h4>违反的约束：</h4>
      <el-alert
        v-for="(violation, index) in result.violated_constraints"
        :key="index"
        :title="violation.constraint_name || '约束违反'"
        :description="violation.message || violation.description"
        type="error"
        :closable="false"
        style="margin-bottom: 8px"
      />
    </div>

    <div v-if="result.warnings && result.warnings.length" style="margin-top: 16px">
      <h4>警告信息：</h4>
      <el-alert
        v-for="(warning, index) in result.warnings"
        :key="index"
        :title="warning"
        type="warning"
        :closable="false"
        style="margin-bottom: 8px"
      />
    </div>

    <div v-if="result.is_feasible !== undefined" style="margin-top: 16px">
      <h4>可行性评估：</h4>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="是否可行">
          <el-tag :type="result.is_feasible ? 'success' : 'danger'">
            {{ result.is_feasible ? '可行' : '不可行' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="可行性评分">
          {{ (result.feasibility_score * 100)?.toFixed(1) || 0 }}%
        </el-descriptions-item>
        <el-descriptions-item label="最大可转移功率">
          {{ result.max_shift_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="推荐设备数">
          {{ result.recommended_devices?.length || 0 }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="result.suggestions && result.suggestions.length" style="margin-top: 16px">
      <h4>优化建议：</h4>
      <ul>
        <li v-for="(suggestion, index) in result.suggestions" :key="index">{{ suggestion }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  result: any
}>()

const isFeasibilityResult = computed(() => props.result.is_feasible !== undefined)
const summaryPassed = computed(() =>
  isFeasibilityResult.value ? props.result.is_feasible : props.result.is_valid
)
const summaryTitle = computed(() => {
  if (isFeasibilityResult.value) {
    return summaryPassed.value ? '可行性分析通过' : '可行性分析未通过'
  }
  return summaryPassed.value ? '约束检查通过' : '约束检查未通过'
})
</script>

<style scoped lang="scss">
.constraint-check-result {
  h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: bold;
    color: #303133;
  }

  ul {
    margin: 0;
    padding-left: 20px;
    li {
      margin-bottom: 8px;
      color: #606266;
    }
  }
}
</style>
