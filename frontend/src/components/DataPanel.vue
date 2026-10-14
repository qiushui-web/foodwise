<script setup lang="ts">defineProps<{ title?: string }>();</script>
<template><section class="panel fw-data-panel"><h3 v-if="title">{{ title }}</h3><slot /></section></template>
<style scoped>.fw-data-panel{padding:20px;margin-bottom:16px;background:#fff;border:1px solid #dce8f2;border-radius:12px;min-width:0}h3{margin:0 0 16px;font-size:18px}.fw-data-panel :deep(.panel-head){display:block;margin-bottom:16px}.fw-data-panel :deep(.panel-head h3){margin:6px 0 12px}</style>
