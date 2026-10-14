<script setup lang="ts">withDefaults(defineProps<{ tone?: 'neutral' | 'warning' | 'success' | 'error' }>(),{ tone:'neutral' });</script>
<template><span class="fw-status" :class="tone"><slot /></span></template>
<style scoped>.fw-status{display:inline-block;padding:5px 9px;border-radius:5px;font-size:13px;background:#eaf3ff;color:#245986}.warning{background:#fff1dd;color:#85521c}.success{background:#e8f5ec;color:#24653c}.error{background:#fde9e7;color:#9e332b}</style>
