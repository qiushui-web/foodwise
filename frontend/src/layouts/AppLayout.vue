<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useAppStore } from "../stores/app";
import { getApi } from "../utils/vue-api";
import { publicPath } from "../utils/public-base";

const route = useRoute();
const app = useAppStore();
const menuOpen = ref(false);
const session = ref<{ name: string; role: string; demo: boolean } | null>(null);
const title = computed(() => String(route.meta.title || "经营驾驶舱"));
const active = computed(() => String(route.meta.active || "dashboard"));

onMounted(async () => {
  try { session.value = await getApi("/session"); } catch { /* API error is shown by the active view. */ }
  try {
    const alerts = await getApi<any[]>("/alerts");
    app.setPendingAlertCount(alerts.filter((item) => item.status !== "已处理").length);
  } catch {
    // Individual views still show their own loading/error state.
  }
});

const groups = [
  { label: "先了解数据", items: [
    ["dashboard", "经营总览", "layout-dashboard"], ["stalls", "档口与菜品", "store"],
    ["operation-feedback", "录入或导入台账", "database-zap"],
  ]},
  { label: "按餐次操作", items: [
    ["prediction", "生成备餐建议", "sparkles"], ["offers", "处理剩余与优惠", "badge-percent"],
    ["orders", "核销订单", "scan-line"], ["alerts", "处理预警", "bell-ring"],
  ]},
  { label: "复盘与说明", items: [
    ["reports", "经营复盘", "chart-no-axes-combined"],
    ["insights/realtime", "实时经营", "radio-tower", "insights-realtime"], ["insights/demand", "需求分析", "chart-spline", "insights-demand"],
    ["insights/waste", "减损分析", "recycle", "insights-waste"], ["about", "服务说明", "circle-help"],
  ]},
];
const visibleGroups = computed(() => session.value?.role === "ANALYST"
  ? groups.map((group) => ({ ...group, items: group.items.filter((item) =>
      !["operation-feedback", "prediction", "offers", "orders", "alerts"].includes(item[0])) }))
      .filter((group) => group.items.length)
  : groups);

const iconPaths: Record<string, string> = {
  "layout-dashboard": "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  store: "M3 10h18M5 10v9h14v-9M4 10l2-5h12l2 5M9 19v-5h6v5",
  sparkles: "m12 3-1.2 4.2L7 8.5l3.8 1.3L12 14l1.2-4.2L17 8.5l-3.8-1.3L12 3ZM19 14l-.7 2.3L16 17l2.3.7L19 20l.7-2.3L22 17l-2.3-.7L19 14ZM5 14l-.6 1.9L2.5 17l1.9.6L5 19.5l.6-1.9 1.9-.6-1.9-.6L5 14Z",
  "chart-no-axes-combined": "M4 19V5M4 19h17M7 15l3-4 3 2 5-7",
  "badge-percent": "M7 3h10l4 4v10l-4 4H7l-4-4V7l4-4ZM8 16l8-8M9 9h.01M15 15h.01",
  "database-zap": "M5 5c0-1.1 3.1-2 7-2s7 .9 7 2-3.1 2-7 2-7-.9-7-2Zm0 0v7c0 1.1 3.1 2 7 2 .7 0 1.4 0 2-.1M5 9c0 1.1 3.1 2 7 2M19 9v2M17 15l-2 4h3l-2 4",
  "scan-line": "M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2M7 12h10",
  "bell-ring": "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4",
  "radio-tower": "M12 12h.01M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14M12 3v18",
  "chart-spline": "M4 19V5M4 19h17M7 15c2-6 4 3 6-2s4-5 7-7",
  recycle: "M7 19H4l2-4M4 19a8 8 0 0 0 13-3M17 5h3l-2 4M20 5a8 8 0 0 0-13 3M12 5l-2-2M12 5l2-2M12 19l-2 2M12 19l2 2",
  "circle-help": "M9.1 9a3 3 0 1 1 5.8 1c-.9 1.3-2.9 1.5-2.9 3M12 17h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
};
</script>

<template>
  <div class="app-shell" :class="{ 'menu-open': menuOpen }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside class="sidebar">
      <RouterLink class="brand" to="/app/dashboard" @click="menuOpen = false">
        <span class="brand-mark"><img :src="publicPath('images/brand-logo-blue-transparent.png')" alt="" width="44" height="44" /></span><span><strong>食刻有数</strong><small>FOODWISE</small></span>
      </RouterLink>
      <div v-for="group in visibleGroups" :key="group.label" class="vue-nav-group">
        <span class="sidebar-label">{{ group.label }}</span>
        <nav class="nav-list">
        <RouterLink v-for="item in group.items" :key="item[0]" :to="`/app/${item[0]}`" :class="{ active: active === (item[3] || item[0]) }" @click="menuOpen = false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="iconPaths[item[2]]" /></svg><span>{{ item[1] }}</span>
        </RouterLink>
        </nav>
      </div>
      <div class="sidebar-foot"><strong>第一次使用？</strong><small>先核对菜品和历史台账，再生成备餐建议。</small><RouterLink class="sidebar-help" to="/app/about" @click="menuOpen = false">查看使用说明 →</RouterLink></div>
    </aside>
    <div v-if="menuOpen" class="vue-backdrop" @click="menuOpen = false"></div>
    <main id="main-content" class="main-shell" tabindex="-1">
      <header class="topbar">
        <button class="mobile-menu" aria-label="打开菜单" @click="menuOpen = !menuOpen">☰</button>
        <div class="topbar-title"><span class="eyebrow">{{ session?.demo ? '演示环境 · 非实时经营数据' : '高校食堂经营工作台' }}</span><h1>{{ title }}</h1></div>
        <div class="topbar-actions"><span v-if="session?.demo" class="demo-tag">演示</span><span v-if="session && !session.demo" class="session-role">{{ session.role === 'ADMIN' ? '管理员' : session.role === 'OPERATOR' ? '运营员' : '分析员' }}</span><RouterLink v-if="app.pendingAlertCount && session?.role !== 'ANALYST'" class="alert-link" to="/app/alerts">{{ app.pendingAlertCount }} 条待处理预警</RouterLink><RouterLink class="help-link" to="/app/about">使用说明</RouterLink></div>
      </header>
      <section class="content-wrap"><RouterView /></section>
    </main>
  </div>
</template>

<style scoped>
.skip-link{position:absolute;left:12px;top:-100px;z-index:100;padding:10px 14px;border-radius:8px;background:#fff;color:#155a98;font-weight:700}.skip-link:focus{top:12px}
.app-shell{min-height:100vh}.vue-nav-group{margin:8px 0}.mobile-menu{display:none;border:0;background:transparent;font-size:22px;color:#3478c9}.sidebar-help{display:block;margin-top:12px;font-size:12px;font-weight:700;color:#3478c9}.sidebar-foot small{display:block;line-height:1.6;margin-top:6px}.topbar-title{min-width:0}.topbar-actions{display:flex;align-items:center;gap:8px;margin-left:auto}.help-link,.alert-link,.session-role,.demo-tag{display:inline-flex;align-items:center;min-height:38px;padding:8px 11px;border:1px solid #dbe8f4;border-radius:8px;background:#fff;color:#2e6fae;font-size:12px;font-weight:700;white-space:nowrap}.demo-tag{display:none;background:#fff4dd;border-color:#f1d99d;color:#875e13}.alert-link{color:#a94a2e;background:#fff6f2;border-color:#f4d7cb}.session-role{color:#53708a;background:#f6f9fc}@media(max-width:820px){.sidebar{transform:translateX(-100%);transition:transform .22s ease}.menu-open .sidebar{transform:translateX(0)}.main-shell{margin-left:0}.mobile-menu{display:block}.vue-backdrop{display:block;position:fixed;inset:0;background:rgba(20,48,78,.35);z-index:35}.topbar{gap:8px}.topbar h1{font-size:18px;line-height:1.3}.topbar .eyebrow,.session-role,.help-link{display:none}.demo-tag{display:inline-flex}.alert-link{padding:7px 8px;font-size:11px}@media(max-width:390px){.alert-link{display:none}}}
</style>
