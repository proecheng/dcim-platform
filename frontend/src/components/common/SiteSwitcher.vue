<template>
  <el-select
    :model-value="modelValue"
    placeholder="选择站点"
    style="width: 180px"
    @change="handleChange"
  >
    <el-option label="全部站点" value="" />
    <el-option
      v-for="site in siteStore.sites"
      :key="site.id"
      :label="site.site_name"
      :value="site.id"
    >
      <span class="site-option">
        <span class="status-dot" :class="'status-' + site.status" />
        {{ site.site_name }}
        <span class="site-count">{{ site.gateway_count }}网关</span>
      </span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSiteStore } from '@/stores'

const siteStore = useSiteStore()

const modelValue = computed(() =>
  siteStore.currentSiteId !== null ? siteStore.currentSiteId : ''
)

function handleChange(val: string | number) {
  if (val === '' || val === null) {
    siteStore.switchSite(null)
  } else {
    siteStore.switchSite(Number(val))
  }
}

onMounted(() => {
  if (siteStore.sites.length === 0) {
    siteStore.fetchSites()
  }
})
</script>

<style scoped>
.site-option {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-active {
  background-color: #67c23a;
}

.status-maintenance {
  background-color: #e6a23c;
}

.status-inactive {
  background-color: #909399;
}

.site-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
</style>
