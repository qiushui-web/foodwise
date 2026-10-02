<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getApi } from "../utils/vue-api";

const loading = ref(true);
const error = ref("");
const summary = ref<any>({});
const metadata = ref<any>({});
const trend = ref<any[]>([]);
const alerts = ref<any[]>([]);
const orders = ref<any[]>([]);
const session = ref<{ role: string; demo: boolean } | null>(null);
const dataDate = computed(() => metadata.value.period_end ? String(metadata.value.period_end).slice(0, 10) : "暂无经营记录");
const pendingAlerts = computed(() => alerts.value.filter((item) => item.status !== "已处理").length);
const pendingOrders = computed(() => orders.value.filter((item) => item.status === "待取餐").length);
const soldRate = computed(() => summary.value.prepared ? Math.round(summary.value.sold * 1000 / summary.value.prepared) / 10 : 0);
const accuracy = computed(() => Number(summary.value.accuracy || 0).toFixed(1));

onMounted(async () => {
  try {
    [summary.value, metadata.value, trend.value] = await Promise.all([
      getApi("/operations/summary"), getApi("/analytics/metadata"), getApi("/operations/trend"),
    ]);
    const extras = await Promise.allSettled([getApi<any[]>("/alerts"), getApi<any[]>("/orders"), getApi<any>("/session")]);
    if (extras[0].status === "fulfilled") alerts.value = extras[0].value;
    if (extras[1].status === "fulfilled") orders.value = extras[1].value;
    if (extras[2].status === "fulfilled") session.value = extras[2].value;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "经营数据加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-if="loading" class="state" role="status">正在加载经营数据…</div>
  <div v-else-if="error" class="state error" role="alert">{{ error }}。请稍后刷新，或联系管理员检查数据连接。</div>
  <template v-else>
    <section class="workbench" aria-label="经营工作台">
      <div><span class="workbench-label">经营工作台</span><h2>先处理当下的事</h2><p>当前台账截至 <strong>{{ dataDate }}</strong>；{{ session?.demo ? '演示数据仅用于熟悉流程。' : '请核对日期后再操作。' }}</p></div>
      <div class="workbench-actions"><RouterLink v-if="session?.role !== 'ANALYST'" class="btn primary" to="/app/prediction">生成备餐建议</RouterLink><RouterLink v-if="session?.role !== 'ANALYST'" class="btn ghost" to="/app/operations/feedback">回填经营数据</RouterLink></div>
    </section>
    <div class="task-strip" aria-label="待办事项">
      <RouterLink to="/app/alerts"><strong>{{ pendingAlerts }}</strong><span>条待处理预警</span></RouterLink>
      <RouterLink to="/app/orders"><strong>{{ pendingOrders }}</strong><span>笔待核销订单</span></RouterLink>
      <RouterLink to="/app/operations/feedback"><strong>{{ dataDate }}</strong><span>最新台账日期</span></RouterLink>
    </div>
    <section class="data-context" aria-label="数据范围">
      <div><strong>当前显示的是最近一个有记录的营业日</strong><p>日期：{{ dataDate }} · 历史 {{ metadata.records ?? 0 }} 条 · {{ metadata.dishes ?? 0 }} 道菜品。{{ metadata.statement }}</p></div>
      <RouterLink to="/app/operations/feedback">更新台账 →</RouterLink>
    </section>

    <div class="metrics-grid" aria-label="最近营业日经营结果">
      <article class="metric-card"><i class="metric-icon green">餐</i><div><span>实际备餐</span><strong>{{ summary.prepared ?? 0 }}</strong><small>份 · 最近营业日</small></div></article>
      <article class="metric-card"><i class="metric-icon teal">售</i><div><span>实际售出</span><strong>{{ summary.sold ?? 0 }}</strong><small>份 · 占备餐 {{ soldRate }}%</small></div></article>
      <article class="metric-card"><i class="metric-icon orange">余</i><div><span>闭餐剩余</span><strong>{{ summary.leftover ?? 0 }}</strong><small>份 · 未售出的成品</small></div></article>
      <article class="metric-card featured"><i class="metric-icon light">惠</i><div><span>优惠售出</span><strong>{{ summary.rescued ?? 0 }}</strong><small>份 · 已计入实际售出</small></div></article>
    </div>

    <details class="workflow-help"><summary>查看完整餐次流程</summary><div class="guide-steps"><RouterLink to="/app/prediction">营业前 · 生成备餐建议</RouterLink><RouterLink to="/app/offers">营业中 · 处理可售剩余</RouterLink><RouterLink to="/app/operations/feedback">闭餐后 · 回填真实结果</RouterLink><RouterLink to="/app/reports">定期 · 查看经营复盘</RouterLink></div></details>

    <div class="dashboard-grid">
      <article class="panel span-6"><div class="panel-head"><div><span class="kicker">如何读这些数字</span><h3>先确认数据，再判断趋势</h3></div></div><p class="plain-explain">以上四项来自 {{ dataDate }} 的台账；售出和剩余相加应等于实际备餐。预测准确度不是实时监控指标，请在复盘报告中结合样本量查看。</p><p class="plain-explain">当前已记录 {{ trend.length }} 个营业日。没有真实台账时，预置数据只用于演示流程。</p></article>
      <article class="panel span-6"><div class="panel-head"><div><span class="kicker">遇到问题怎么办</span><h3>先检查这三项</h3></div></div><ul class="quick-check"><li>找不到菜品：先到“档口与菜品”核对菜品编号。</li><li>无法预测：该菜品需要至少一条历史销量记录。</li><li>无法提交：检查“备餐 = 售出 + 剩余”，并确认食品安全。</li></ul><RouterLink class="text-link" to="/app/about">查看完整使用说明 →</RouterLink></article>
    </div>
  </template>
</template>

<style scoped>
.workbench{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px 26px;border:1px solid #cbdfee;border-radius:8px;background:#edf6fd}.workbench-label{font-size:12px;font-weight:700;color:#3478c9}.workbench h2{margin:5px 0;font-size:25px;color:#183d62}.workbench p{margin:0;color:#526f88;font-size:13px;line-height:1.6}.workbench-actions{display:flex;gap:10px;flex-wrap:wrap}.workbench-actions .btn{white-space:nowrap}.task-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}.task-strip a{display:flex;align-items:baseline;gap:8px;padding:15px 18px;background:#fff;border:1px solid #d8e7f2;border-radius:8px}.task-strip strong{font-size:22px;color:#2469ae;white-space:nowrap}.task-strip span{font-size:13px;color:#526f88}.data-context{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:16px 0;padding:14px 18px;border:1px solid #cbdfee;border-radius:8px;background:#f4f9fe}.data-context strong{font-size:14px;color:#24496d}.data-context p{margin:6px 0 0;font-size:12px;line-height:1.7;color:#55718d}.data-context a{flex:none;color:#286daf;font-size:13px;font-weight:700}.workflow-help{margin:16px 0;padding:14px;border:1px solid #d7e7f4;border-radius:8px;background:#fff}.workflow-help summary{cursor:pointer;font-size:13px;font-weight:700;color:#286daf}.guide-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.guide-steps a{padding:12px;background:#f5f9fd;border-radius:6px;font-size:12px;color:#355f85}.plain-explain,.quick-check{font-size:13px;line-height:1.8;color:#526d83}.plain-explain{margin:8px 0}.quick-check{padding-left:20px;margin:6px 0 12px}.quick-check li{margin-bottom:7px}.text-link{font-size:13px}.state{padding:28px;background:#fff;border-radius:8px}.error{color:#ae3f39}@media(max-width:820px){.workbench{display:block;padding:18px}.workbench h2{font-size:21px}.workbench-actions{margin-top:15px}.workbench-actions .btn{flex:1;text-align:center}.task-strip{grid-template-columns:1fr 1fr}.task-strip a:last-child{grid-column:1/-1}.task-strip a{padding:12px;flex-direction:column;gap:2px}.task-strip strong{font-size:19px}.data-context{align-items:flex-start;flex-direction:column}.guide-steps{grid-template-columns:1fr}}
</style>
