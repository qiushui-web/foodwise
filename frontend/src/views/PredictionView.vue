<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getApi, postApi } from "../utils/vue-api";
import { dishPhoto } from "../utils/dish-photo";

const dishes = ref<any[]>([]);
const dishId = ref<number | null>(null);
const weather = ref("晴");
const examWeek = ref(false);
const campusEvent = ref(false);
const loading = ref(false);
const result = ref<any>(null);
const error = ref("");
const prediction = computed(() => result.value?.prediction ?? result.value);
const selectedDish = computed(() => dishes.value.find((dish) => (dish.id ?? dish.dishId) === dishId.value));
onMounted(async () => {
  try {
    dishes.value = await getApi("/dishes");
    dishId.value = dishes.value[0]?.id ?? dishes.value[0]?.dishId ?? null;
  } catch (e) { error.value = e instanceof Error ? e.message : "菜品加载失败"; }
});
async function predict() {
  if (!dishId.value) return;
  loading.value = true; error.value = ""; result.value = null;
  try {
    result.value = await postApi("/predictions", { dishId: dishId.value, weather: weather.value, examWeek: examWeek.value, campusEvent: campusEvent.value, engine: "rule" });
  } catch (e) { error.value = e instanceof Error ? e.message : "预测失败"; }
  finally { loading.value = false; }
}
</script>

<template>
  <div class="view-head"><span class="kicker">营业前 · 第一步</span><h2>备餐决策中心</h2><p>选择菜品和预计营业条件，生成次日备餐参考。建议基于该菜品的历史销量，现场负责人仍需结合库存和产能判断。</p></div>
  <div class="prediction-grid">
    <section class="panel form-panel">
      <div class="panel-head"><span class="kicker">输入条件</span><h3>明天卖这道菜，需要备多少？</h3></div>
      <label>菜品<select v-model.number="dishId"><option v-for="dish in dishes" :key="dish.id ?? dish.dishId" :value="dish.id ?? dish.dishId">{{ dish.name ?? dish.dishName }}</option></select></label>
      <div v-if="dishPhoto(selectedDish?.name ?? selectedDish?.dishName)" class="dish-preview"><img :src="dishPhoto(selectedDish?.name ?? selectedDish?.dishName)!" :alt="`${selectedDish?.name ?? selectedDish?.dishName}同类菜品实拍示意`" width="88" height="68"><span>同类菜品实拍示意</span></div>
      <label>预计天气<select v-model="weather"><option>晴</option><option>小雨</option><option>大雨</option><option>高温</option><option>降温</option></select></label>
      <label class="check"><input v-model="examWeek" type="checkbox"> 明天是考试周</label>
      <label class="check"><input v-model="campusEvent" type="checkbox"> 明天有校园活动</label>
      <p class="form-help">请按次日情况选择。若没有历史销量，先到“录入或导入台账”添加该菜品记录。</p>
      <button class="btn primary" :disabled="loading || !dishId" @click="predict">{{ loading ? "计算中…" : "生成备餐建议" }}</button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
    <section class="panel result-panel">
      <div class="panel-head"><span class="kicker">怎么执行</span><h3>先做首批，再视销售补餐</h3></div>
      <div v-if="!prediction" class="empty">左侧选择条件并点击“生成备餐建议”，这里会显示参考数量。</div>
      <div v-else class="result">
        <div class="result-main"><span>预计销量区间</span><strong>{{ prediction.predictedLow }}–{{ prediction.predictedHigh }} <small>份</small></strong><em>模型参考值 {{ prediction.confidence }}%</em></div>
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
.view-head{margin-bottom:22px}.kicker{font-size:11px;color:#3478c9;font-weight:700}.view-head h2{font-size:30px;margin:8px 0}.view-head p{color:#57738b;font-size:13px;line-height:1.7}.prediction-grid{display:grid;grid-template-columns:minmax(300px,360px) minmax(0,1fr);gap:16px}.panel{background:#fff;border:1px solid #dce8f2;border-radius:12px;padding:22px}.panel-head h3{font-size:18px;margin:6px 0 22px}.form-panel label{display:block;color:#496a85;font-size:13px;font-weight:600;margin:17px 0}.form-panel select{display:block;width:100%;margin-top:7px;padding:11px;border:1px solid #cbdfee;border-radius:7px;background:#fff;color:#274f73;font-size:14px}.form-panel select:focus-visible{outline:2px solid #3478c9}.check{display:flex!important;gap:8px;align-items:center}.form-help{color:#59758f;font-size:12px;line-height:1.7;margin:15px 0}.btn{border:0;padding:12px 18px;border-radius:8px;font-weight:700;cursor:pointer;font-size:13px}.btn.primary{background:#3478c9;color:#fff}.btn:disabled{opacity:.5;cursor:not-allowed}.empty{padding:50px 10px;text-align:center;color:#607d96;font-size:13px}.result-main{padding:20px;border-radius:10px;background:#eaf3ff}.result-main span,.result-main strong,.result-main em{display:block}.result-main span{font-size:12px;color:#537997}.result-main strong{font:700 38px Manrope;color:#3478c9;margin:10px 0}.result-main small{font-size:14px}.result-main em{font-size:12px;color:#4b7eaa;font-style:normal}.result-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.result-kpis div{padding:14px;background:#f5f9fd;border-radius:8px}.result-kpis span,.result-kpis strong{display:block}.result-kpis span{font-size:12px;color:#59778f}.result-kpis strong{margin-top:8px;font-size:16px}.risk{display:flex;gap:10px;flex-wrap:wrap}.risk b{font-size:12px;color:#925d27;padding:8px 10px;background:#fff4e6;border-radius:6px}.result>p{font-size:13px;line-height:1.7;color:#59758f}.error{color:#b7433d;font-size:13px}.next-link{display:inline-block;margin-top:8px;font-size:13px;font-weight:700;color:#286daf}@media(max-width:800px){.prediction-grid{grid-template-columns:1fr}.result-kpis{grid-template-columns:1fr 1fr}}
</style>
<style scoped>
.dish-preview{display:flex;align-items:center;gap:10px;color:#5b7388;font-size:12px}.dish-preview img{width:88px;height:68px;object-fit:cover;border-radius:5px;background:#eef3f6}
</style>
