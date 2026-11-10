<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useAppStore } from "../stores/app";
import type { Session, Alert } from "../api/types";
import { getAllPages, getApi } from "../utils/vue-api";
import { publicPath } from "../utils/public-base";

const route = useRoute();
const app = useAppStore();
const menuOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);
const sidebar = ref<HTMLElement | null>(null);
const sessionError = ref("");
watch(menuOpen, async (open) => {
  await nextTick();
  if (open) sidebar.value?.querySelector<HTMLElement>("a")?.focus();
  else menuButton.value?.focus();
});
function menuKey(event: KeyboardEvent) {
  if (!menuOpen.value) return;
  if (event.key === "Escape") { menuOpen.value = false; return; }
  if (event.key !== "Tab") return;
  const links = Array.from(sidebar.value?.querySelectorAll<HTMLElement>("a,button") ?? []);
  const first = links[0]; const last = links[links.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
onMounted(() => window.addEventListener("keydown", menuKey));
onUnmounted(() => window.removeEventListener("keydown", menuKey));
const session = ref<{ name: string; role: string; demo: boolean } | null>(null);
const title = computed(() => String(route.meta.title || "经营驾驶舱"));
const active = computed(() => String(route.meta.active || "dashboard"));

onMounted(async () => {
  try { session.value = await getApi<Session>("/session"); } catch { sessionError.value = "会话加载失败，请刷新页面；导航暂不可用。"; }
  try {
    const alerts = await getAllPages<Alert>("/alerts");
    app.setPendingAlertCount(alerts.filter((item) => item.status !== "已处理").length);
  } catch {
    // Individual views still show their own loading/error state.
  }
});

const workflow = [
  ["prediction", "备餐计划", "sparkles"],
  ["operation-feedback", "经营记录", "database-zap"],
  ["offers", "剩余处理", "badge-percent"],
  ["reports", "经营复盘", "chart-no-axes-combined"],
];
const visibleWorkflow = computed(() => !session.value ? [] : session.value.role === "ANALYST"
  ? workflow.filter((item) => item[0] === "reports")
  : workflow);

const sectionLinks = computed(() => {
  if (["offers", "orders", "alerts"].includes(active.value)) return [["/app/offers", "剩余优惠"], ["/app/orders", "订单核销"], ["/app/alerts", "经营预警"]];
  if (["reports", "insights-realtime", "insights-demand", "insights-waste"].includes(active.value)) return [["/app/reports", "经营复盘"], ["/app/insights/realtime", "营业概况"], ["/app/insights/demand", "需求分析"], ["/app/insights/waste", "剩余分析"]];
  if (["stalls", "onboarding"].includes(active.value)) return [["/app/stalls", "档口与菜品"], ["/app/onboarding", "新增档口"]];
  if (["about", "evidence"].includes(active.value)) return [["/app/about", "使用说明"], ["/app/evidence", "数据说明"]];
  return [];
});

const iconPaths: Record<string, string> = {
  "clipboard-plus": "M9 4h6v3H9zM7 5H5v16h14V5h-2M12 11v6M9 14h6",
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
    <aside id="app-navigation" ref="sidebar" class="sidebar">
      <RouterLink class="brand" to="/app/dashboard" @click="menuOpen = false">
        <span class="brand-mark"><img :src="publicPath('images/brand-logo-blue-transparent.png')" alt="" width="44" height="44" /></span><span><strong>食刻有数</strong><small>FOODWISE</small></span>
      </RouterLink>
      <p v-if="sessionError" role="alert">{{ sessionError }}</p><p v-else-if="!session">正在确认会话…</p><div v-else class="vue-nav-group">
        <nav class="nav-list overview-nav" aria-label="经营总览"><RouterLink to="/app/dashboard" :class="{ active: active === 'dashboard' }" @click="menuOpen = false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" /></svg><span>经营总览</span></RouterLink></nav><span class="sidebar-label">日常流程</span>
        <nav class="nav-list" aria-label="日常流程">
        <RouterLink v-for="item in visibleWorkflow" :key="item[0]" :to="`/app/${item[0]}`" :class="{ active: active === item[0] || (item[0] === 'offers' && ['orders','alerts'].includes(active)) || (item[0] === 'reports' && active.startsWith('insights-')) }" @click="menuOpen = false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="iconPaths[item[2]]" /></svg><span>{{ item[1] }}</span>
        </RouterLink>
        </nav>
        <nav v-if="session.role !== 'OPERATOR'" class="nav-list" aria-label="档口管理">
          <RouterLink to="/app/stalls" :class="{ active: ['stalls','onboarding'].includes(active) }" @click="menuOpen = false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 10h18M5 10V5h14v5M5 10v10h14V10M9 20v-6h6v6" /></svg><span>档口管理</span></RouterLink>
        </nav>
      </div>
      <div class="sidebar-foot"><strong>第一次使用？</strong><small>{{ session?.role === 'ANALYST' ? '查看经营记录和数据说明。' : session?.role === 'OPERATOR' ? '请负责人确认当餐菜品和营业信息。' : '先确认档口菜品，再开始当餐备餐计划。' }}</small><RouterLink class="sidebar-help" to="/app/about" @click="menuOpen = false">查看使用说明 →</RouterLink></div>
    </aside>
    <div v-if="menuOpen" class="vue-backdrop" @click="menuOpen = false"></div>
    <main id="main-content" class="main-shell" tabindex="-1">
      <header class="topbar">
        <button ref="menuButton" class="mobile-menu" aria-label="打开菜单" :aria-expanded="menuOpen" aria-controls="app-navigation" @click="menuOpen = !menuOpen">☰</button>
        <div class="topbar-title"><span class="eyebrow">{{ session?.demo ? '演示环境 · 非实时经营数据' : '高校食堂经营工作台' }}</span><h1>{{ title }}</h1></div>
        <div class="topbar-actions"><span v-if="session?.demo" class="demo-tag">演示</span><span v-if="session && !session.demo" class="session-role">{{ session.role === 'ADMIN' ? '管理员' : session.role === 'OPERATOR' ? '运营员' : '分析员' }}</span><RouterLink v-if="app.pendingAlertCount && session?.role !== 'ANALYST'" class="alert-link" to="/app/alerts">{{ app.pendingAlertCount }} 条待处理预警</RouterLink><RouterLink class="help-link" to="/app/about">使用说明</RouterLink></div>
      </header>
      <section class="content-wrap"><nav v-if="sectionLinks.length" class="section-tabs" aria-label="当前模块"><RouterLink v-for="item in sectionLinks" :key="item[0]" :to="item[0]" :aria-current="route.path === item[0] ? 'page' : undefined">{{ item[1] }}</RouterLink></nav><RouterView /></section>
    </main>
  </div>
</template>

<style scoped>
.skip-link{position:absolute;left:12px;top:-100px;z-index:100;padding:10px 14px;border-radius:8px;background:#fff;color:#155a98;font-weight:700}.skip-link:focus{top:12px}
.app-shell{min-height:100vh}.vue-nav-group{margin:8px 0}.mobile-menu{display:none;min-width:44px;min-height:44px;border:0;background:transparent;font-size:22px;color:var(--fw-primary)}.sidebar-help{display:block;margin-top:12px;font-size:12px;font-weight:700;color:var(--fw-primary)}.sidebar-foot small{display:block;line-height:1.6;margin-top:6px}.topbar-title{min-width:0}.topbar-actions{display:flex;align-items:center;gap:8px;margin-left:auto}.help-link,.alert-link,.session-role,.demo-tag{display:inline-flex;align-items:center;min-height:38px;padding:8px 11px;border:1px solid #dbe8f4;border-radius:8px;background:#fff;color:var(--fw-primary);font-size:12px;font-weight:700;white-space:nowrap}.demo-tag{display:none;background:#fff4dd;border-color:#f1d99d;color:#875e13}.alert-link{color:#a94a2e;background:#fff6f2;border-color:#f4d7cb}.session-role{color:#53708a;background:#f6f9fc}@media(max-width:820px){.sidebar{transform:translateX(-100%);transition:transform .22s ease}.menu-open .sidebar{transform:translateX(0)}.main-shell{margin-left:0}.mobile-menu{display:block}.vue-backdrop{display:block;position:fixed;inset:0;background:rgba(20,48,78,.35);z-index:35}.topbar{gap:8px}.topbar h1{font-size:18px;line-height:1.3}.topbar .eyebrow,.session-role,.help-link{display:none}.demo-tag{display:inline-flex}.alert-link{padding:7px 8px;font-size:11px}@media(max-width:390px){.alert-link{display:none}}}
</style>

<style scoped>
.section-tabs{display:flex;flex-wrap:wrap;gap:6px;padding:5px;margin-bottom:24px;border-bottom:1px solid var(--fw-border)}.section-tabs a{padding:11px 16px;min-height:44px;border-radius:8px 8px 0 0;color:var(--fw-muted);font-size:14px;text-decoration:none}.section-tabs a[aria-current=page]{background:#fff;color:var(--fw-primary);font-weight:700;box-shadow:inset 0 -3px var(--fw-primary)}.section-tabs a:focus-visible{outline:2px solid var(--fw-primary);outline-offset:2px}@media(max-width:520px){.section-tabs{gap:2px;margin-bottom:18px}.section-tabs a{padding:10px 12px;font-size:13px}}
</style>
