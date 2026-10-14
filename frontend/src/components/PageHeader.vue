<script setup lang="ts">
defineProps<{ title: string; description?: string; eyebrow?: string }>();
</script>
<template><header class="view-head fw-page-header"><span v-if="eyebrow" class="kicker">{{ eyebrow }}</span><h2>{{ title }}</h2><p v-if="description">{{ description }}</p><slot /></header></template>
<style scoped>.fw-page-header{margin-bottom:22px}.kicker{font-size:13px;color:var(--fw-primary,#286daf);font-weight:700}h2{font-size:28px;margin:8px 0;line-height:1.3}p{color:#496a85;font-size:14px;line-height:1.7;margin:0}@media(max-width:600px){h2{font-size:24px}}</style>
