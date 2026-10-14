<script setup lang="ts">defineProps<{ label: string; value: string | number; detail?: string }>();</script>
<template><article class="fw-metric"><span>{{ label }}</span><strong>{{ value }}</strong><small v-if="detail">{{ detail }}</small></article></template>
<style scoped>.fw-metric{padding:18px;background:#fff;border:1px solid #dce8f2;border-radius:12px}span,small{display:block;color:#496a85;font-size:13px}strong{display:block;margin:11px 0 6px;font-size:28px;overflow-wrap:anywhere}</style>
