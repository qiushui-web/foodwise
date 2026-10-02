<script setup lang="ts">
import { RouterView } from "vue-router";
</script>

<template>
  <div class="app-root"><RouterView /></div>
</template>

<style>
.app-root{min-height:100vh}
body:has(.login-shell){min-height:100vh;display:grid;place-items:center;background:linear-gradient(120deg,#eef7ff,#f9fcff 52%,#e6f4ff)!important}
</style>
