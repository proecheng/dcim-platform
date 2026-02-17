<template>
  <el-tag :type="tagType" size="small" effect="light">
    {{ tagText }}
  </el-tag>
</template>

<script setup lang="ts">
const props = defineProps<{ quality: number }>()

const tagType = computed(() => {
  if (props.quality === 2) return 'danger'
  if (props.quality === 1) return 'warning'
  return 'success'
})

const tagText = computed(() => {
  if (props.quality === 2) return '不可靠'
  if (props.quality === 1) return '不确定'
  return '正常'
})
</script>
