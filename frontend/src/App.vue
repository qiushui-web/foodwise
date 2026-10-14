<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { RouterView } from "vue-router";
const route = useRoute();
const isLogin = computed(() => route.path === "/login");
</script>

<template>
  <div class="app-root" :class="{ 'login-root': isLogin }"><RouterView /></div>
</template>

<style>
.app-root{min-height:100vh}
 .login-root{min-height:100vh;display:grid;place-items:center;background:linear-gradient(120deg,#eef7ff,#f9fcff 52%,#e6f4ff)!important}
</style>
