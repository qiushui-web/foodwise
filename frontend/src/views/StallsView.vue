<script setup lang="ts">
import PageHeader from "../components/PageHeader.vue";
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getAllPages } from "../utils/vue-api";
import type { Stall, Dish } from "../api/types";
import { formatNumber } from "../utils/format";
import { dishPhoto } from "../utils/dish-photo";
const stalls = ref<Stall[]>([]); const dishes = ref<Dish[]>([]); const loading = ref(true); const error = ref("");
onMounted(async () => { try { [stalls.value, dishes.value] = await Promise.all([getAllPages<Stall>("/stalls"), getAllPages<Dish>("/dishes")]); } catch (e) { error.value = e instanceof Error ? e.message : "档口数据加载失败"; } finally { loading.value = false; } });
</script>
<template>
  <PageHeader title="看清每个档口" description="核对菜品名称、价格和编号；批量导入 CSV 需要正确的菜品 ID。" eyebrow="档口经营管理" />
  <div v-if="loading" class="state">正在加载档口数据…</div>
  <div v-else-if="error" class="state error">{{ error }}</div>
  <template v-else>
    <div class="stall-grid">
      <article v-for="stall in stalls" :key="stall.id ?? stall.name" class="panel">
        <div class="stall-top"><div class="stall-mark">{{ String(stall.name || "档").slice(0,1) }}</div><div><h3>{{ stall.name }}</h3><span>{{ stall.location || "经营档口" }}</span></div><b>{{ stall.status || "正常" }}</b></div>
        <div class="stall-stats"><span>菜品 <strong>{{ stall.dish_count ?? stall.dishCount ?? 0 }}</strong></span><span>评分 <strong>{{ stall.rating ?? "—" }}</strong></span><span>最近营业日收入 <strong>¥{{ stall.today_revenue ?? stall.todayRevenue ?? 0 }}</strong></span></div>
      </article>
    </div>
    <section class="panel">
      <div class="panel-head"><span class="kicker">菜品目录</span><h3>成本与历史表现</h3></div>
      <p class="photo-note">图片为同类菜品的实拍示意，不代表档口当日出品。<RouterLink to="/app/about#photo-credits">图片来源</RouterLink></p>
      <div class="table-wrap"><table><thead><tr><th>菜品 ID</th><th>菜品</th><th>档口</th><th>售价</th><th>单位成本</th><th>平均销量</th><th>剩余率</th></tr></thead><tbody>
        <tr v-for="dish in dishes" :key="dish.id"><td>{{ dish.id }}</td><td><div class="dish-cell"><img v-if="dishPhoto(dish.name)" :src="dishPhoto(dish.name)!" :alt="`${dish.name}同类菜品实拍示意`" width="58" height="58" loading="lazy"><strong>{{ dish.name }}</strong></div></td><td>{{ dish.stallName ?? dish.stall_name }}</td><td>¥{{ formatNumber(dish.price, 2) }}</td><td>¥{{ formatNumber(dish.unitCost ?? dish.unit_cost, 2) }}</td><td>{{ formatNumber(dish.avgSales ?? dish.avg_sales) }}</td><td>{{ formatNumber(dish.leftoverRate ?? dish.leftover_rate) }}%</td></tr>
      </tbody></table></div>
    </section>
  </template>
</template>
<style scoped>.kicker{font-size:13px;color:#286daf;font-weight:700}.stall-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:16px}.stall-top{display:flex;align-items:center;gap:11px}.stall-mark{display:grid;place-items:center;width:40px;height:40px;border-radius:10px;background:#e8f5f0;color:#286daf;font-weight:800}.stall-top h3{margin:0;font-size:15px}.stall-top span{font-size:13px;color:#496a85}.stall-top>b{margin-left:auto;color:#286daf;background:#eaf3ff;padding:6px 8px;border-radius:99px;font-size:13px}.stall-stats{display:flex;justify-content:space-between;border-top:1px solid #edf2f0;margin-top:18px;padding-top:14px;color:#496a85;font-size:13px}.stall-stats strong{display:block;color:#294e44;font:600 14px Manrope;margin-top:5px}.panel-head h3{margin:6px 0 18px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;background:#f2f7fc;color:#748a82;font-size:13px;padding:11px}td{padding:12px;border-top:1px solid #edf2f0}.state{padding:40px;background:#fff;border-radius:12px;color:#70877f}.error{color:#bd5c51}@media(max-width:700px){.stall-grid{grid-template-columns:1fr}}
</style>
<style scoped>
.photo-note{margin:-8px 0 14px;color:#5b7388;font-size:12px;line-height:1.5}.photo-note a{color:#286daf}.dish-cell{display:flex;align-items:center;gap:10px;min-width:160px}.dish-cell img{flex:none;width:58px;height:58px;object-fit:cover;border-radius:5px;background:#eef3f6}.dish-cell strong{font-weight:600;color:#28465f}
</style>
