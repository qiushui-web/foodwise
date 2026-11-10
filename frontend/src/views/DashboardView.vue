<script setup lang="ts">
import type { Summary, Metadata, TrendPoint, Alert, Order, Session } from "../api/types";
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getAllPages, getApi } from "../utils/vue-api";
import { formatDate } from "../utils/format";
import { publicPath } from "../utils/public-base";

const loading = ref(true);
const error = ref("");
const summary = ref<Summary>({});
const metadata = ref<Metadata>({});
const trend = ref<TrendPoint[]>([]);
const alerts = ref<Alert[]>([]);
const orders = ref<Order[]>([]);
const session = ref<Session | null>(null);
const ledgerCount = ref<number | null>(null);
const dataDate = computed(() => {
  const end = metadata.value.period_end;
  if (!end) return "暂无经营记录";
  if (!String(end).includes("T")) return String(end).slice(0, 10);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date(end));
});
const pendingAlerts = computed(() => alerts.value.filter((item) => item.status !== "已处理").length);
const pendingOrders = computed(() => orders.value.filter((item) => item.status === "待取餐").length);
const soldRate = computed(() => summary.value.prepared ? Math.round((summary.value.sold ?? 0) * 100 / summary.value.prepared) : 0);
const chartPoints = computed(() => trend.value.slice(-10));
const chartMax = computed(() => Math.max(1, ...chartPoints.value.map((point) => Number(point.prepared) || 0)));
const chartHeight = (value: number) => `${Math.max(0, Math.min(100, (Number(value) || 0) / chartMax.value * 100))}%`;
const canOperate = computed(() => Boolean(session.value && session.value.role !== "ANALYST"));
const ledgerAgeDays = computed(() => {
  const end = metadata.value.period_end;
  if (!end) return null;
  const day = new Date(`${dataDate.value}T00:00:00+08:00`).getTime();
  if (Number.isNaN(day)) return null;
  return Math.max(0, Math.floor((Date.now() - day) / 86400000));
});
type ActionItem = { key: string; to: string; title: string; detail: string; tone: "warn" | "info" | "plan" };
const actions = computed<ActionItem[]>(() => {
  const list: ActionItem[] = [];
  if (pendingAlerts.value > 0) {
    const first = alerts.value.find((item) => item.status !== "已处理");
    list.push({
      key: "alerts", to: "/app/alerts", tone: "warn",
      title: `处理 ${pendingAlerts.value} 条待处理预警`,
      detail: first ? `${formatDate(first.business_date)} · ${first.dish_name} · ${first.alert_type}` : "按预警中心顺序处理",
    });
  }
  if (pendingOrders.value > 0) {
    const first = orders.value.find((item) => item.status === "待取餐");
    list.push({
      key: "orders", to: "/app/orders", tone: "info",
      title: `核销 ${pendingOrders.value} 笔待取餐订单`,
      detail: first ? `取餐码 ${first.pickup_code} · ${first.dish_name} × ${first.quantity}` : "窗口交付后核销",
    });
  }
  if (ledgerCount.value === 0) {
    list.push({ key: "ledger", to: "/app/operations/feedback", tone: "plan", title: "先录入第一条经营台账", detail: "没有历史记录时，备餐建议无法计算", });
  } else if (!session.value?.demo && ledgerAgeDays.value !== null && ledgerAgeDays.value >= 3) {
    list.push({ key: "ledger", to: "/app/operations/feedback", tone: "plan", title: `补齐台账（已 ${ledgerAgeDays.value} 天未更新）`, detail: `最近营业日 ${dataDate.value}；超过 14 天不建议据此排产`, });
  } else if (canOperate.value) {
    list.push({ key: "plan", to: "/app/prediction", tone: "plan", title: "生成下一餐备餐计划", detail: "核对菜品、餐次与现场条件，再确认制作量", });
  }
  if (list.length === 0) {
    list.push({ key: "reports", to: "/app/reports", tone: "info", title: "今天的待办已清空", detail: "去经营复盘看看这周的变化", });
  }
  return list.slice(0, 3);
});

onMounted(async () => {
  try {
    [summary.value, metadata.value, trend.value] = await Promise.all([
      getApi<Summary>("/operations/summary"), getApi<Metadata>("/analytics/metadata"), getApi<TrendPoint[]>("/operations/trend"),
    ]);
    const extras = await Promise.allSettled([getAllPages<Alert>("/alerts"), getAllPages<Order>("/orders"), getApi<Session>("/session"), getApi<{ total: number }>("/operations/rows?page=1&size=1")]);
    if (extras[0].status === "fulfilled") alerts.value = extras[0].value;
    if (extras[1].status === "fulfilled") orders.value = extras[1].value;
    if (extras[2].status === "fulfilled") session.value = extras[2].value;
    if (extras[3].status === "fulfilled") ledgerCount.value = extras[3].value.total;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "经营数据加载失败";
  } finally { loading.value = false; }
});
</script>

<template>
  <div v-if="loading" class="state" role="status">正在加载经营数据…</div>
  <div v-else-if="error" class="state error" role="alert">{{ error }}。请刷新页面或联系管理员检查数据连接。</div>
  <div v-else class="dashboard-page">
    <header class="dashboard-intro" :style="{ backgroundImage: `linear-gradient(95deg,rgba(246,251,255,.98),rgba(234,246,255,.88) 55%,rgba(231,244,255,.4)),url(${publicPath('images/canteen-wide.jpg')})` }">
      <div><span class="kicker">经营总览 · {{ dataDate }}</span><h2>先看数据，<em>再定备餐</em></h2><p>{{ session?.demo ? "当前为历史经营演示；从一份备餐计划，走完记录与复盘。" : "根据最近一条台账查看经营情况；请先核对营业日期。" }}</p></div>
      <RouterLink v-if="canOperate" class="btn primary" :to="ledgerCount === 0 ? '/app/operations/feedback' : '/app/prediction'">{{ ledgerCount === 0 ? "先录入台账" : "制定备餐计划" }} <span aria-hidden="true">→</span></RouterLink>
    </header>
    <section class="dashboard-summary" aria-label="最近营业日经营结果">
      <div><span>实际备餐</span><strong>{{ summary.prepared ?? 0 }}<small>份</small></strong><p>最近有记录的营业日</p></div>
      <div><span>实际售出</span><strong>{{ summary.sold ?? 0 }}<small>份</small></strong><p>占备餐 {{ soldRate }}%</p></div>
      <div><span>当前记录剩余</span><strong>{{ summary.leftover ?? 0 }}<small>份</small></strong><p>以最近一次盘点记录为准</p></div><div class="summary-featured"><span>优惠售出</span><strong>{{ summary.rescued ?? 0 }}<small>份</small></strong><p>已包含在实际售出中</p></div>
    </section>
    <div class="dashboard-scope"><span><b>{{ session?.demo ? "历史演示" : "台账概况" }}</b> {{ dataDate }} · {{ ledgerCount ?? "—" }} 条记录 · {{ metadata.dishes ?? "—" }} 道菜品</span><RouterLink to="/app/operations/feedback">查看经营台账 →</RouterLink></div>
    <div class="dashboard-main">
      <section class="dashboard-trend" aria-labelledby="trend-title">
        <div class="section-heading"><div><span class="kicker">经营走势</span><h3 id="trend-title">近期备餐与售出</h3></div><span class="chart-legend"><i></i>售出 <i></i>未售出</span></div>
        <div v-if="chartPoints.length" class="trend-chart" role="img" :aria-label="`最近 ${chartPoints.length} 个有记录营业日的备餐、售出与剩余柱状图`">
          <div v-for="point in chartPoints" :key="point.businessDay" class="trend-column" :title="`${point.businessDay}：备餐 ${point.prepared} 份，售出 ${point.sold} 份，未售出 ${Math.max(0, point.prepared - point.sold)} 份`">
            <span class="trend-value">{{ point.prepared }}</span>
            <div class="trend-track"><div class="trend-stack" :style="{ height: chartHeight(point.prepared) }"><span class="trend-leftover" :style="{ height: `${Math.max(0, Math.min(100, point.prepared ? (point.prepared - point.sold) / point.prepared * 100 : 0))}%` }"></span><span class="trend-sold"></span></div></div>
            <span class="trend-date">{{ String(point.businessDay).slice(5) }}</span>
          </div>
        </div>
        <div v-else class="dashboard-empty">还没有可展示的经营走势。先录入一条台账，图表会按真实记录更新。</div>
        <div class="chart-foot"><span>单位：份 · 仅显示有记录的营业日</span><RouterLink to="/app/reports">查看经营复盘 →</RouterLink></div>
      </section>
      <aside class="dashboard-next" aria-labelledby="next-title">
        <div class="next-photo" :style="{ backgroundImage: `url(${publicPath('images/canteen-wide.jpg')})` }"><span>从当天记录到下一餐计划</span></div>
        <div class="next-content"><span class="kicker">接下来</span><h3 id="next-title">先处理待办，再更新台账</h3>
          <RouterLink v-for="item in actions" :key="item.key" :to="item.to" :class="['action-link', item.tone]">
            <strong>{{ item.title }}</strong><span>{{ item.detail }}</span><span aria-hidden="true">→</span>
          </RouterLink>
    <RouterLink v-if="session?.role !== 'OPERATOR'" class="action-more" to="/app/evidence">查看数据说明 →</RouterLink>
        </div>
      </aside>
    </div>
    <details class="dashboard-context"><summary>数据范围与使用说明</summary><p>当前显示最近一个有记录的营业日：{{ dataDate }}。历史 {{ metadata.records ?? 0 }} 条，{{ metadata.dishes ?? 0 }} 道菜品。{{ metadata.statement }}</p><p>营业中的盘点可能尚未反映闭餐结果；以上数字不能直接解释为已验证的减损成效。</p></details>
  </div>
</template>

<style scoped>
.dashboard-page{display:grid;gap:18px}.dashboard-intro{display:flex;align-items:end;justify-content:space-between;gap:20px;padding:8px 0 4px}.dashboard-intro h2{margin:7px 0 5px;font-size:27px;line-height:1.3;color:#203d56}.dashboard-intro p{margin:0;color:#667989;font-size:13px}.dashboard-intro .btn{flex:none}.dashboard-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:#fff;border:1px solid #dbe5eb;border-radius:8px;overflow:hidden}.dashboard-summary>div{padding:19px 24px;border-right:1px solid #e6edf1;min-width:0}.dashboard-summary>div:last-child{border:0}.dashboard-summary span,.dashboard-summary p{font-size:12px;color:#667989}.dashboard-summary strong{display:block;margin-top:7px;font-size:34px;line-height:1.1;color:#214c6c;font-variant-numeric:tabular-nums}.dashboard-summary strong small{font-size:14px;margin-left:5px}.dashboard-summary p{margin:7px 0 0}.dashboard-main{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(260px,.85fr);gap:18px}.dashboard-trend,.dashboard-next{background:#fff;border:1px solid #dbe5eb;border-radius:8px;overflow:hidden}.dashboard-trend{padding:21px 23px 16px}.section-heading{display:flex;align-items:start;justify-content:space-between;gap:15px}.section-heading h3,.dashboard-next h3{margin:4px 0 0;font-size:18px;color:#203d56}.chart-legend{display:flex;align-items:center;gap:6px;color:#6a7c88;font-size:11px;white-space:nowrap}.chart-legend i{display:inline-block;width:8px;height:8px;border-radius:2px;background:#3b84ad}.chart-legend i:nth-of-type(2){margin-left:8px;background:#e2ad6a}.trend-chart{height:260px;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:12px;align-items:end;padding:12px 6px 0;background:repeating-linear-gradient(to top,transparent 0,transparent 63px,#edf3f6 64px,#edf3f6 65px);border-bottom:1px solid #dbe5eb;margin-top:14px}.trend-column{height:100%;display:flex;flex-direction:column;justify-content:end;align-items:center;min-width:0}.trend-track{height:calc(100% - 27px);width:min(100%,32px);display:flex;align-items:end}.trend-stack{display:flex;flex-direction:column;width:100%;min-height:2px;border-radius:3px 3px 0 0;overflow:hidden}.trend-leftover{display:block;flex:none;background:#e2ad6a}.trend-sold{display:block;flex:1;background:#3b84ad}.trend-date{height:27px;display:grid;place-items:center;white-space:nowrap;font-size:10px;color:#738591}.dashboard-empty{min-height:245px;display:grid;place-items:center;text-align:center;padding:30px;color:#6a7c88;font-size:13px}.chart-foot{display:flex;justify-content:space-between;gap:12px;margin-top:13px;color:#758794;font-size:11px}.chart-foot a{color:var(--fw-primary);font-weight:700}.next-photo{height:110px;background-size:cover;background-position:center;position:relative;display:flex;align-items:end;padding:13px 17px;color:#fff;font-size:12px;font-weight:700}.next-photo:before{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(20,52,39,.82),transparent 75%)}.next-photo span{position:relative}.next-content{padding:17px 19px}.next-content h3{margin-bottom:12px}.next-content a{display:flex;align-items:center;gap:9px;padding:12px 0;border-top:1px solid #e7edf1;color:#345c75;font-size:12px}.next-content a strong{min-width:37px;color:var(--fw-primary);font-size:16px}.next-content a span:last-child{margin-left:auto}.dashboard-context{padding:12px 3px;border-top:1px solid #dbe5eb;color:#6a7d88;font-size:12px}.dashboard-context summary{cursor:pointer;font-weight:700}.dashboard-context p{line-height:1.6;margin:7px 0}.state{padding:28px;background:#fff;border-radius:8px}.error{color:#ae3f39}@media(max-width:900px){.dashboard-main{grid-template-columns:1fr}.dashboard-next{display:grid;grid-template-columns:180px 1fr}.next-photo{height:auto}}@media(max-width:600px){.dashboard-intro{display:block}.dashboard-intro h2{font-size:22px}.dashboard-intro .btn{margin-top:15px}.dashboard-summary{grid-template-columns:1fr 1fr}.dashboard-summary>div{padding:14px;border-bottom:1px solid #e6edf1}.dashboard-summary>div:nth-child(2){border-right:0}.dashboard-summary>div:last-child{grid-column:1/-1;border-bottom:0}.dashboard-summary strong{font-size:27px}.dashboard-trend{padding:17px 13px}.trend-chart{gap:5px;height:215px}.trend-date{font-size:9px}.dashboard-next{display:block}.next-photo{height:100px}.chart-legend{font-size:10px}}
.trend-value{height:15px;font-size:10px;color:#55738a;font-variant-numeric:tabular-nums}.trend-track{height:calc(100% - 42px)}@media(max-width:600px){.trend-value{display:none}.trend-track{height:calc(100% - 27px)}}
</style>

<style scoped>
.next-content .action-link{display:grid;grid-template-columns:1fr auto;grid-template-areas:'title arrow' 'detail arrow';row-gap:3px;align-items:center;width:100%;text-align:left}
.next-content .action-link strong{grid-area:title;min-width:0;font-size:14px;line-height:1.45;color:#274b62}
.next-content .action-link span:not(:last-child){grid-area:detail;min-width:0;font-size:11.5px;line-height:1.5;color:#71838d}
.next-content .action-link span:last-child{grid-area:arrow}
.next-content .action-link.warn strong{color:#a2472c}
.next-content .action-link.warn{box-shadow:inset 3px 0 0 #c8623f;padding-left:10px;margin-left:-10px}
.next-content .action-link.plan strong{color:var(--fw-primary-strong)}
.next-content .action-more{display:block;padding:10px 0 0;border-top:1px solid #e7edf1;font-size:11.5px;font-weight:700;color:var(--fw-primary-strong);text-decoration:none}
</style>
