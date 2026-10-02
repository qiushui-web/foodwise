<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getApi, postApi } from "../utils/vue-api";

type Order = { id: number; order_no: string; dish_name: string; title: string; quantity: number; amount: number; pickup_code: string; pickup_location: string; status: string };
const rows = ref<Order[]>([]);
const loading = ref(true);
const error = ref("");
const pickupCode = ref("");
const selected = ref<Order | null>(null);
const busy = ref(false);
const pending = computed(() => rows.value.filter((row) => row.status === "待取餐"));

onMounted(async () => {
  try { rows.value = await getApi("/orders"); }
  catch (e) { error.value = e instanceof Error ? e.message : "订单加载失败"; }
  finally { loading.value = false; }
});

async function lookup() {
  error.value = "";
  selected.value = null;
  if (!/^\d{6}$/.test(pickupCode.value.trim())) { error.value = "请输入6位取餐码"; return; }
  busy.value = true;
  try { selected.value = await getApi(`/orders/lookup?pickupCode=${encodeURIComponent(pickupCode.value.trim())}`); }
  catch (e) { error.value = e instanceof Error ? e.message : "未找到该订单"; }
  finally { busy.value = false; }
}

async function verify() {
  if (!selected.value || selected.value.status !== "待取餐") return;
  busy.value = true;
  error.value = "";
  try {
    await postApi(`/orders/${selected.value.id}/verify`, {});
    selected.value.status = "已核销";
    const row = rows.value.find((item) => item.id === selected.value?.id);
    if (row) row.status = "已核销";
  } catch (e) { error.value = e instanceof Error ? e.message : "核销失败，请重查订单状态"; }
  finally { busy.value = false; }
}
</script>

<template>
  <div class="view-head"><span class="kicker">现场执行</span><h2>订单核销</h2><p>顾客到窗口后输入取餐码，核对菜品和数量，交付餐品后再核销。</p></div>
  <section class="lookup-panel" aria-label="按取餐码查找订单">
    <form @submit.prevent="lookup"><label for="pickup-code">取餐码</label><div class="lookup-row"><input id="pickup-code" v-model="pickupCode" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="off" placeholder="输入6位取餐码"><button class="btn primary" :disabled="busy" type="submit">{{ busy ? '查询中…' : '查找订单' }}</button></div></form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="selected" class="match" role="status"><div class="match-head"><strong>{{ selected.dish_name }}</strong><span :class="selected.status === '待取餐' ? 'pending' : 'done'">{{ selected.status }}</span></div><p>{{ selected.quantity }} 份 · {{ selected.pickup_location }} · ¥{{ selected.amount }}</p><p>取餐码 {{ selected.pickup_code }} · 订单 {{ selected.order_no }}</p><button v-if="selected.status === '待取餐'" class="btn primary confirm" :disabled="busy" @click="verify">{{ busy ? '核销中…' : '餐品已交付，确认核销' }}</button></div>
  </section>
  <section class="queue" aria-label="近期待取餐订单"><h3>近期待取餐 <small>{{ pending.length }} 笔</small></h3><p v-if="loading">正在加载订单…</p><p v-else-if="!pending.length">当前列表没有待取餐订单。可使用上方取餐码查询。</p><div v-else class="order-list"><article v-for="row in pending" :key="row.id"><div><strong>{{ row.dish_name }}</strong><span>{{ row.quantity }} 份 · {{ row.pickup_location }}</span><small>订单 {{ row.order_no }}</small></div><button class="btn secondary" @click="pickupCode = row.pickup_code; lookup()">核对取餐</button></article></div></section>
</template>

<style scoped>
.view-head{margin-bottom:18px}.view-head h2{font-size:28px;margin:5px 0}.view-head p{font-size:14px;line-height:1.6;color:#56728c}.kicker{font-size:12px;color:#3478c9;font-weight:700}.lookup-panel,.queue{padding:22px;background:#fff;border:1px solid #d8e7f2;border-radius:8px;margin-bottom:16px}.lookup-panel label{display:block;font-weight:700;font-size:14px;margin-bottom:9px;color:#244d72}.lookup-row{display:flex;gap:10px}.lookup-row input{flex:1;min-width:0;min-height:48px;padding:10px 13px;border:1px solid #bcd2e5;border-radius:7px;font-size:20px;letter-spacing:2px}.btn{min-height:44px;padding:10px 16px;border-radius:7px;font-size:14px;font-weight:700;cursor:pointer}.primary{background:#2878c8;border:1px solid #2878c8;color:#fff}.secondary{background:#f1f7fc;border:1px solid #bdd9ec;color:#286dac}.btn:disabled{opacity:.55;cursor:wait}.error{color:#ae3f39;font-size:13px}.match{border-top:1px solid #dfebf4;margin-top:18px;padding-top:18px}.match-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.match-head strong{font-size:20px;color:#173d60}.match p{font-size:14px;color:#526f89}.confirm{width:100%;margin-top:7px}.pending,.done{padding:5px 9px;border-radius:5px;font-size:12px}.pending{background:#fff1dd;color:#a96923}.done{background:#e8f5ec;color:#287448}.queue h3{font-size:18px;margin:0 0 12px}.queue h3 small{font-size:13px;color:#687f93}.queue>p{font-size:14px;color:#607990}.order-list{display:grid;gap:0}.order-list article{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 0;border-top:1px solid #e3edf5}.order-list strong,.order-list span,.order-list small{display:block}.order-list strong{font-size:15px;color:#1d4569}.order-list span{font-size:13px;color:#4e718b;margin-top:3px}.order-list small{font-size:11px;color:#748ca1;margin-top:3px}@media(max-width:520px){.lookup-panel,.queue{padding:16px}.lookup-row{flex-direction:column}.lookup-row button{width:100%}.order-list article{align-items:flex-start}.order-list .btn{flex:none;padding-inline:10px;font-size:12px}}
</style>
