<template>
  <div class="floor-selector">
    <div class="floor-tabs">
      <el-radio-group v-model="currentFloor" size="small">
        <el-radio-button label="B1">B1 制冷机房</el-radio-button>
        <el-radio-button label="F1">F1 机房区A</el-radio-button>
        <el-radio-button label="F2">F2 机房区B</el-radio-button>
        <el-radio-button label="F3">F3 办公监控</el-radio-button>
      </el-radio-group>
    </div>

    <div class="floor-content">
      <FloorB1Layout v-if="currentFloor === 'B1'" v-bind="$attrs" />
      <FloorF1Layout v-else-if="currentFloor === 'F1'" v-bind="$attrs" />
      <FloorF2Layout v-else-if="currentFloor === 'F2'" v-bind="$attrs" />
      <FloorF3Layout v-else-if="currentFloor === 'F3'" v-bind="$attrs" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FloorB1Layout from './FloorB1Layout.vue'
import FloorF1Layout from './FloorF1Layout.vue'
import FloorF2Layout from './FloorF2Layout.vue'
import FloorF3Layout from './FloorF3Layout.vue'

const currentFloor = ref('F1')
</script>

<style scoped lang="scss">
.floor-selector {
  .floor-tabs {
    margin-bottom: 16px;
    text-align: center;
  }
}
</style>
