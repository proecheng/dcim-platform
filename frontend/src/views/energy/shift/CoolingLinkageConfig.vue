<template>
  <div class="cooling-linkage-config">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>制冷联动配置</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>联动参数配置</span>
          <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
        </div>
      </template>

      <el-form :model="config" :rules="rules" ref="formRef" label-width="180px">
        <el-divider content-position="left">基础参数</el-divider>
        
        <el-form-item label="启用制冷联动" prop="enabled">
          <el-switch v-model="config.enabled" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            开启后，负荷转移时自动调整制冷系统
          </span>
        </el-form-item>

        <el-form-item label="制冷滞后时间" prop="lag_time_minutes">
          <el-input-number 
            v-model="config.lag_time_minutes" 
            :min="15" 
            :max="30" 
            :step="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            分钟（建议 15-30 分钟，考虑制冷系统响应延迟）
          </span>
        </el-form-item>

        <el-divider content-position="left">COP 参数</el-divider>

        <el-form-item label="目标 COP" prop="target_cop">
          <el-input-number 
            v-model="config.target_cop" 
            :min="2.0" 
            :max="5.0" 
            :step="0.1"
            :precision="2"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            制冷系统能效比目标值（典型值 2.5-4.0）
          </span>
        </el-form-item>

        <el-form-item label="COP 下限阈值" prop="cop_lower_threshold">
          <el-input-number 
            v-model="config.cop_lower_threshold" 
            :min="1.5" 
            :max="3.0" 
            :step="0.1"
            :precision="2"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            低于此值触发告警
          </span>
        </el-form-item>

        <el-form-item label="COP 上限阈值" prop="cop_upper_threshold">
          <el-input-number 
            v-model="config.cop_upper_threshold" 
            :min="3.5" 
            :max="6.0" 
            :step="0.1"
            :precision="2"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            高于此值可能存在测量异常
          </span>
        </el-form-item>

        <el-divider content-position="left">温度参数</el-divider>

        <el-form-item label="供水温度目标值" prop="target_supply_temp">
          <el-input-number 
            v-model="config.target_supply_temp" 
            :min="5" 
            :max="15" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C（典型值 7-12°C）
          </span>
        </el-form-item>

        <el-form-item label="供水温度下限" prop="supply_temp_lower">
          <el-input-number 
            v-model="config.supply_temp_lower" 
            :min="3" 
            :max="10" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C（低于此值可能结冰）
          </span>
        </el-form-item>

        <el-form-item label="供水温度上限" prop="supply_temp_upper">
          <el-input-number 
            v-model="config.supply_temp_upper" 
            :min="12" 
            :max="20" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C（高于此值制冷效果不足）
          </span>
        </el-form-item>

        <el-form-item label="回水温度目标值" prop="target_return_temp">
          <el-input-number 
            v-model="config.target_return_temp" 
            :min="10" 
            :max="20" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C（典型值 12-18°C）
          </span>
        </el-form-item>

        <el-form-item label="回水温度下限" prop="return_temp_lower">
          <el-input-number 
            v-model="config.return_temp_lower" 
            :min="8" 
            :max="15" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C
          </span>
        </el-form-item>

        <el-form-item label="回水温度上限" prop="return_temp_upper">
          <el-input-number 
            v-model="config.return_temp_upper" 
            :min="18" 
            :max="25" 
            :step="0.5"
            :precision="1"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            °C
          </span>
        </el-form-item>

        <el-divider content-position="left">调整策略</el-divider>

        <el-form-item label="功率调整步长" prop="power_adjust_step">
          <el-input-number 
            v-model="config.power_adjust_step" 
            :min="5" 
            :max="50" 
            :step="5"
            :precision="0"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            kW（每次调整的功率增量）
          </span>
        </el-form-item>

        <el-form-item label="最大调整幅度" prop="max_adjust_ratio">
          <el-input-number 
            v-model="config.max_adjust_ratio" 
            :min="0.1" 
            :max="0.5" 
            :step="0.05"
            :precision="2"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            相对当前功率的最大调整比例（建议 0.2-0.3）
          </span>
        </el-form-item>

        <el-form-item label="调整间隔时间" prop="adjust_interval_minutes">
          <el-input-number 
            v-model="config.adjust_interval_minutes" 
            :min="5" 
            :max="30" 
            :step="5"
            :disabled="!config.enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            分钟（两次调整之间的最小间隔）
          </span>
        </el-form-item>

        <el-divider content-position="left">安全保护</el-divider>

        <el-form-item label="启用安全保护" prop="safety_protection_enabled">
          <el-switch v-model="config.safety_protection_enabled" :disabled="!config.enabled" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            异常情况下自动停止联动
          </span>
        </el-form-item>

        <el-form-item label="最小制冷功率" prop="min_cooling_power">
          <el-input-number 
            v-model="config.min_cooling_power" 
            :min="0" 
            :max="500" 
            :step="10"
            :disabled="!config.enabled || !config.safety_protection_enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            kW（低于此值停止联动）
          </span>
        </el-form-item>

        <el-form-item label="最大制冷功率" prop="max_cooling_power">
          <el-input-number 
            v-model="config.max_cooling_power" 
            :min="500" 
            :max="5000" 
            :step="100"
            :disabled="!config.enabled || !config.safety_protection_enabled"
          />
          <span style="margin-left: 10px; color: #909399; font-size: 12px">
            kW（高于此值停止联动）
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>配置说明</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="制冷滞后效应">
          负荷转移后，制冷系统需要 15-30 分钟才能达到新的稳态。配置滞后时间可避免过度调整。
        </el-descriptions-item>
        <el-descriptions-item label="COP 能效比">
          COP = 制冷量 / 制冷功耗。典型值 2.5-4.0，越高越节能。低于 2.0 表示系统效率异常。
        </el-descriptions-item>
        <el-descriptions-item label="供回水温差">
          正常情况下供回水温差 5-8°C。温差过小表示流量不足或负荷过低，温差过大表示负荷过高。
        </el-descriptions-item>
        <el-descriptions-item label="安全保护">
          启用后，当温度或功率超出安全范围时，系统自动停止联动并发出告警，防止设备损坏。
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCoolingConfig, updateCoolingConfig } from '@/api/modules/shift'

const loading = ref(false)
const saving = ref(false)
const formRef = ref()
const config = ref({
  enabled: true,
  lag_time_minutes: 20,
  target_cop: 3.0,
  cop_lower_threshold: 2.0,
  cop_upper_threshold: 4.5,
  target_supply_temp: 10.0,
  supply_temp_lower: 5.0,
  supply_temp_upper: 15.0,
  target_return_temp: 15.0,
  return_temp_lower: 10.0,
  return_temp_upper: 20.0,
  power_adjust_step: 20,
  max_adjust_ratio: 0.25,
  adjust_interval_minutes: 10,
  safety_protection_enabled: true,
  min_cooling_power: 100,
  max_cooling_power: 2000
})

const rules = {
  lag_time_minutes: [
    { required: true, message: '请输入制冷滞后时间', trigger: 'blur' }
  ],
  target_cop: [
    { required: true, message: '请输入目标COP', trigger: 'blur' }
  ],
  target_supply_temp: [
    { required: true, message: '请输入供水温度目标值', trigger: 'blur' }
  ],
  target_return_temp: [
    { required: true, message: '请输入回水温度目标值', trigger: 'blur' }
  ]
}

const fetchConfig = async () => {
  loading.value = true
  try {
    const res = await getCoolingConfig()
    if (res.data) {
      config.value = res.data
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取配置失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    
    saving.value = true
    try {
      await updateCoolingConfig(config.value)
      ElMessage.success('配置保存成功')
      await fetchConfig()
    } catch (error: any) {
      ElMessage.error(error.message || '保存配置失败')
    } finally {
      saving.value = false
    }
  })
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped lang="scss">
.cooling-linkage-config {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
