<template>
  <div class="safe-rich-text" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderSafeMarkdown } from '@/security/html'

const props = defineProps<{
  markdown: string
}>()

const renderedHtml = computed(() => renderSafeMarkdown(props.markdown))
</script>
