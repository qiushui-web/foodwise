<script setup lang="ts">
import type { Dish, PredictionResponse } from "../api/types";
import PageHeader from "../components/PageHeader.vue";
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { createWriteIntent } from "../api/write-intent";
import { getAllPages, getApi, postApi } from "../utils/vue-api";
import { dishPhoto } from "../utils/dish-photo";

const dishes = ref<Dish[]>([]);
const dishId = ref<number | null>(null);
const weather = ref("晴");
const targetDate = ref(new Intl.DateTimeFormat("sv-SE").format(new Date(Date.now() + 86400000)));
const mealPeriod = ref("全日");
const examWeek = ref(false);
const campusEvent = ref(false);
const loading = ref(false);
const result = ref<PredictionResponse | null>(null);
const writeIntent = createWriteIntent();
const error = ref("");
const prediction = computed(() => result.value?.prediction);
const selectedDish = computed(() => dishes.value.find((dish) => dish.id === dishId.value));
onMounted(async () => {
  try {
    dishes.value = await getAllPages<Dish>("/dishes");
    dishId.value = dishes.value[0]?.id ?? null;
  } catch (e) { error.value = e instanceof Error ? e.message : "菜品加载失败"; }
});
async function predict() {
  if (!dishId.value) return;
  loading.value = true; error.value = ""; result.value = null;
  try {
    const payload = { dishId: dishId.value, weather: weather.value, examWeek: examWeek.value, campusEvent: campusEvent.value, engine: "rule", targetDate: targetDate.value, mealPeriod: mealPeriod.value, sourceNature: "经营台账；来源待逐笔核验" };
    result.value = await postApi<PredictionResponse>("/predictions", payload, writeIntent.key(payload)); writeIntent.complete();
  } catch (e) { error.value = e instanceof Error ? e.message : "预测失败"; }
  finally { loading.value = false; }
}
</script>

<template>
  <PageHeader title="备餐决策中心" description="选择菜品和预计营业条件，生成所选日期的备餐参考。建议基于该菜品的历史销量，现场负责人仍需结合库存和产能判断。" eyebrow="营业前 · 第一步" />
  <div class="prediction-grid">
    <section class="panel form-panel">
      <div class="panel-head"><span class="kicker">输入条件</span><h3>所选营业日，需要备多少？</h3></div>
      <label>菜品<select v-model.number="dishId"><option v-for="dish in dishes" :key="dish.id" :value="dish.id">{{ dish.name }}</option></select></label>
      <div v-if="dishPhoto(selectedDish?.name)" class="dish-preview"><img :src="dishPhoto(selectedDish?.name)!" :alt="`${selectedDish?.name}同类菜品实拍示意`" width="88" height="68"><span>同类菜品实拍示意</span></div>
      <label>预计天气<select v-model="weather"><option>晴</option><option>小雨</option><option>大雨</option><option>高温</option><option>降温</option></select></label>
      <label>目标营业日<input v-model="targetDate" type="date"></label>
      <label>餐次<select v-model="mealPeriod"><option>全日</option><option>早餐</option><option>午餐</option><option>晚餐</option></select></label>
      <label class="check"><input v-model="examWeek" type="checkbox"> 目标日是考试周</label>
      <label class="check"><input v-model="campusEvent" type="checkbox"> 目标日有校园活动</label>
      <p class="form-help">请按目标营业日情况选择。若没有历史销量，先到“录入或导入台账”添加该菜品记录。</p>
      <button class="btn primary" :disabled="loading || !dishId" @click="predict">{{ loading ? "计算中…" : "生成备餐建议" }}</button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
    <section class="panel result-panel">
      <div class="panel-head"><span class="kicker">怎么执行</span><h3>先做首批，再视销售补餐</h3></div>
      <div v-if="!prediction" class="empty">左侧选择条件并点击“生成备餐建议”，这里会显示参考数量。</div>
      <div v-else class="result">
        <div class="result-main"><span>销量经验参考范围</span><strong>{{ prediction.predictedLow }}–{{ prediction.predictedHigh }} <small>份</small></strong><em>尚未完成区间校准，不代表准确率或覆盖概率</em></div>
        <div class="result-kpis"><div><span>先制作</span><strong>{{ prediction.firstBatch }} 份</strong></div><div><span>视销售补餐</span><strong>{{ prediction.replenishQty }} 份</strong></div><div><span>参考停做时间</span><strong>{{ String(prediction.stopHour).padStart(2,"0") }}:{{ String(prediction.stopMinute).padStart(2,"0") }}</strong></div></div>
        <div class="risk"><b>售罄风险：{{ prediction.soldOutRisk }}</b><b>剩余风险：{{ prediction.leftoverRisk }}</b></div>
        <p v-if="prediction.advice">{{ prediction.advice.summary }}</p>
        <p class="form-help">这是规则模型的辅助建议，并非实时库存或食品安全判断。闭餐后请回填真实结果。</p>
        <RouterLink class="next-link" to="/app/operations/feedback">去回填经营结果 →</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prediction-grid{display:grid;grid-template-columns:minmax(300px,360px) minmax(0,1fr);gap:16px}.panel-head h3{font-size:18px;margin:6px 0 22px}.form-panel label{display:block;color:#496a85;font-size:13px;font-weight:600;margin:17px 0}.form-panel select{display:block;width:100%;margin-top:7px;padding:11px;border:1px solid #cbdfee;border-radius:7px;background:#fff;color:#274f73;font-size:14px}.form-panel select:focus-visible{outline:2px solid #286daf}.check{display:flex!important;gap:8px;align-items:center}.form-help{color:#59758f;font-size:12px;line-height:1.7;margin:15px 0}.btn{border:0;padding:12px 18px;border-radius:8px;font-weight:700;cursor:pointer;font-size:13px}.btn.primary{background:#286daf;color:#fff}.btn:disabled{opacity:.5;cursor:not-allowed}.empty{padding:50px 10px;text-align:center;color:#607d96;font-size:13px}.result-main{padding:20px;border-radius:10px;background:#eaf3ff}.result-main span,.result-main strong,.result-main em{display:block}.result-main span{font-size:12px;color:#537997}.result-main strong{font:700 38px Manrope;color:#286daf;margin:10px 0}.result-main small{font-size:14px}.result-main em{font-size:12px;color:#4b7eaa;font-style:normal}.result-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.result-kpis div{padding:14px;background:#f5f9fd;border-radius:8px}.result-kpis span,.result-kpis strong{display:block}.result-kpis span{font-size:12px;color:#59778f}.result-kpis strong{margin-top:8px;font-size:16px}.risk{display:flex;gap:10px;flex-wrap:wrap}.risk b{font-size:12px;color:#925d27;padding:8px 10px;background:#fff4e6;border-radius:6px}.result>p{font-size:13px;line-height:1.7;color:#59758f}.error{color:#b7433d;font-size:13px}.next-link{display:inline-block;margin-top:8px;font-size:13px;font-weight:700;color:#286daf}@media(max-width:800px){.prediction-grid{grid-template-columns:1fr}.result-kpis{grid-template-columns:1fr 1fr}}
</style>
<style scoped>
.dish-preview{display:flex;align-items:center;gap:10px;color:#5b7388;font-size:12px}.dish-preview img{width:88px;height:68px;object-fit:cover;border-radius:5px;background:#eef3f6}
</style>
