<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { getApi, postApi, postFormApi } from "../utils/vue-api";
import { useRoute } from "vue-router";
const route = useRoute();

function todayLocal() {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}

const dishes = ref<any[]>([]);
const history = ref<any[]>([]);
const status = ref<any>({});
const submitted = ref<any>(null);
const error = ref("");
const busy = ref(false);
const mode = ref<"single" | "import">("single");
const form = ref({ businessDate: todayLocal(), mealPeriod: "午餐", dishId: 0, plannedQty: 0, preparedQty: 0, soldQty: 0, discountSoldQty: 0, leftoverQty: 0, revenue: 0, weather: "晴", eventTag: "", recommendationAdopted: false, safetyConfirmed: false, operatorName: "", note: "" });
const quantityValid = computed(() => form.value.preparedQty === form.value.soldQty + form.value.leftoverQty
  && form.value.discountSoldQty <= form.value.soldQty);
const valid = computed(() => Boolean(form.value.dishId && form.value.operatorName.trim())
  && form.value.preparedQty > 0
  && form.value.preparedQty === form.value.soldQty + form.value.leftoverQty
  && form.value.discountSoldQty <= form.value.soldQty
  && [form.value.plannedQty, form.value.soldQty, form.value.discountSoldQty, form.value.leftoverQty, form.value.revenue].every((value) => value >= 0));

const csvFile = ref<File | null>(null);
const preview = ref<any>(null);
const batchResult = ref<any>(null);
const importError = ref("");
const previewing = ref(false);
const importing = ref(false);
const importSafetyConfirmed = ref(false);
const importOperatorName = ref("");

async function refreshHistory() {
  [history.value, status.value] = await Promise.all([getApi("/operations/feedback"), getApi("/operations/learning-status")]);
}
onMounted(async () => {
  try {
    const saved = sessionStorage.getItem("foodwise-feedback-draft");
    if (saved) form.value = { ...form.value, ...JSON.parse(saved), safetyConfirmed: false };
    [dishes.value, history.value, status.value] = await Promise.all([getApi("/dishes"), getApi("/operations/feedback"), getApi("/operations/learning-status")]);
    const requestedDish = Number(route.query.dishId);
    if (dishes.value.some((dish) => dish.id === requestedDish)) form.value.dishId = requestedDish;
    else if (!dishes.value.some((dish) => dish.id === form.value.dishId)) form.value.dishId = dishes.value[0]?.id ?? 0;
  } catch (e) { error.value = e instanceof Error ? e.message : "台账数据加载失败"; }
});
watch(form, (value) => sessionStorage.setItem("foodwise-feedback-draft", JSON.stringify({ ...value, safetyConfirmed: false })), { deep: true });
async function submit() {
  if (!valid.value || !form.value.safetyConfirmed) { error.value = "请填写实际记录，核对数量关系并确认食品安全"; return; }
  busy.value = true; error.value = ""; submitted.value = null;
  try { submitted.value = await postApi("/operations/feedback", form.value); sessionStorage.removeItem("foodwise-feedback-draft"); await refreshHistory(); }
  catch (e) { error.value = e instanceof Error ? e.message : "回传失败"; }
  finally { busy.value = false; }
}
function selectFile(event: Event) {
  csvFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  preview.value = null; batchResult.value = null; importError.value = ""; importSafetyConfirmed.value = false;
}
async function previewCsv() {
  if (!csvFile.value) return;
  previewing.value = true; importError.value = ""; preview.value = null;
  const body = new FormData(); body.append("file", csvFile.value);
  try { preview.value = await postFormApi("/operations/import/preview", body); }
  catch (e) { importError.value = e instanceof Error ? e.message : "预览失败"; }
  finally { previewing.value = false; }
}
async function importCsv() {
  if (!csvFile.value || !preview.value?.ready || !importOperatorName.value.trim() || !importSafetyConfirmed.value) return;
  importing.value = true; importError.value = ""; batchResult.value = null;
  const body = new FormData();
  body.append("file", csvFile.value);
  body.append("operatorName", importOperatorName.value.trim());
  body.append("safetyConfirmed", "true");
  try { batchResult.value = await postFormApi("/operations/import", body, true); await refreshHistory(); }
  catch (e) { importError.value = e instanceof Error ? e.message : "导入失败"; }
  finally { importing.value = false; }
}
</script>

<template>
  <div class="view-head"><span class="kicker">经营台账</span><h2>把实际经营结果记下来</h2><p>每个营业日按餐次和菜品填写；已有历史 CSV 时先预览，再批量导入。记录会影响后续预测。</p></div>
  <div class="method-tabs" role="tablist" aria-label="录入方式"><button type="button" role="tab" :aria-selected="mode === 'single'" @click="mode = 'single'">单条录入</button><button type="button" role="tab" :aria-selected="mode === 'import'" @click="mode = 'import'">CSV 批量导入</button></div>
  <div v-if="mode === 'single'" class="method-guide"><strong>闭餐后核对</strong><span>按真实日期和餐次填写。未提交内容保存在当前浏览器标签页；关闭标签页后不会长期保留。</span></div>

  <div v-if="mode === 'single'" class="feedback-grid">
    <section class="panel">
      <div class="panel-head"><div><span class="kicker">方式一 · 单条录入</span><h3>闭餐后填写真实结果</h3></div></div>
      <p class="helper">下方数值默认是 0，请按现场台账填写。优惠售出已经包含在实际售出中，不要重复相加。</p>
      <form @submit.prevent="submit">
        <div class="form-grid">
          <label>营业日期<input v-model="form.businessDate" type="date" required></label>
          <label>餐次<select v-model="form.mealPeriod" required><option>早餐</option><option>午餐</option><option>晚餐</option></select></label>
          <label>菜品<select v-model.number="form.dishId" required><option v-for="dish in dishes" :key="dish.id" :value="dish.id">{{ dish.stallName ?? dish.stall_name }} · {{ dish.name }}（ID {{ dish.id }}）</option></select></label>
          <label>建议备餐量（份）<input v-model.number="form.plannedQty" type="number" min="0" required></label>
          <label>实际备餐量（份）<input v-model.number="form.preparedQty" type="number" min="0" required></label>
          <label>实际售出（份）<input v-model.number="form.soldQty" type="number" min="0" required></label>
          <label>闭餐剩余（份）<input v-model.number="form.leftoverQty" type="number" min="0" required></label>
          <label>其中优惠售出（份）<input v-model.number="form.discountSoldQty" type="number" min="0" required></label>
          <label>当餐收入（元）<input v-model.number="form.revenue" type="number" min="0" step="0.01" required></label>
          <label>天气<select v-model="form.weather"><option>晴</option><option>小雨</option><option>大雨</option><option>高温</option><option>降温</option></select></label>
          <label>操作人员<input v-model.trim="form.operatorName" placeholder="填写实际记录人" required></label>
        </div>
        <label class="wide">校园事件或特殊情况<input v-model="form.eventTag" placeholder="例如：考试周、运动会；没有可不填"></label>
        <label class="wide">备注<textarea v-model="form.note" rows="2" placeholder="记录与常规营业不同的情况"></textarea></label>
        <p :class="['check', { invalid: !quantityValid }]">{{ form.preparedQty === form.soldQty + form.leftoverQty ? '数量关系：实际备餐 = 实际售出 + 闭餐剩余' : '数量不守恒：请核对备餐、售出和剩余' }}<br>优惠售出不能超过实际售出。</p>
        <label class="checkbox"><input v-model="form.recommendationAdopted" type="checkbox"> 本次采用过系统备餐建议</label>
        <label class="checkbox"><input v-model="form.safetyConfirmed" type="checkbox"> 我已核对数据，并确认食品安全要求</label>
        <button class="btn primary" type="submit" :disabled="busy || !valid || !form.safetyConfirmed">{{ busy ? "写入中…" : "校验并写入台账" }}</button>
        <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="submitted" class="success" role="status">已写入：{{ submitted.summary }}</p>
      </form>
    </section>
    <aside class="panel side-note"><span class="kicker">填写提示</span><h3>这三个数字最重要</h3><ol><li>实际备餐：当餐最终制作多少份。</li><li>实际售出：含原价和优惠销售。</li><li>闭餐剩余：当餐结束未售出多少份。</li></ol><p>同一日期、餐次和菜品再次提交会修正已有记录，请核对后操作。</p></aside>
  </div>

  <section v-if="mode === 'import'" class="panel import-panel">
    <div class="panel-head"><div><span class="kicker">方式二 · 批量导入</span><h3>用 CSV 导入历史台账</h3></div></div>
    <p class="helper">请使用 UTF-8 编码的 CSV。表头至少包含下面九列；每行对应一个日期的一道菜品。菜品 ID 可在“档口与菜品”页面核对。</p>
    <code class="csv-header">business_date,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather</code>
    <p class="helper">可选列：meal_period（早餐/午餐/晚餐）、event_tag、recommendation_adopted。没有 meal_period 的旧文件会标为“未标注餐次”。日期格式为 YYYY-MM-DD；预览检查表头和最多 20 行样例，正式导入逐行校验。</p>
    <div class="import-actions"><label>选择 CSV 文件<input type="file" accept=".csv,text/csv" @change="selectFile"></label><button class="btn secondary" type="button" :disabled="!csvFile || previewing" @click="previewCsv">{{ previewing ? "预览中…" : "先预览文件" }}</button></div>
    <div v-if="preview" class="preview-box"><strong>{{ preview.ready ? "表头齐全，可以继续核对" : "缺少必填字段" }}</strong><p>已查看前 {{ preview.sampleCount }} 行样例；这不是全部记录数。</p><p v-if="preview.missingFields?.length" class="error">缺少：{{ preview.missingFields.join("、") }}</p><p v-else>列名：{{ preview.headers?.join("、") }}</p></div>
    <label class="import-operator">导入记录人<input v-model.trim="importOperatorName" autocomplete="name" placeholder="填写本次导入的实际操作人" required></label>
    <label class="checkbox"><input v-model="importSafetyConfirmed" type="checkbox"> 我已核对 CSV 来源和食品安全要求</label>
    <p class="helper">导入时若同一日期、餐次和菜品已存在，会更新该记录。</p>
    <button class="btn primary" type="button" :disabled="!preview?.ready || !importOperatorName.trim() || !importSafetyConfirmed || importing" @click="importCsv">{{ importing ? "导入中…" : "确认导入台账" }}</button>
    <p v-if="importError" class="error" role="alert">{{ importError }}</p>
    <div v-if="batchResult" class="preview-box" role="status"><strong>导入完成：{{ batchResult.imported }} 行成功，{{ batchResult.rejected }} 行被拒绝</strong><p>其中 {{ batchResult.duplicates }} 行更新了同日期、同菜品的已有记录。</p><ul v-if="batchResult.errors?.length"><li v-for="(item, index) in batchResult.errors" :key="index">{{ item }}</li></ul></div>
  </section>

  <section class="panel history-panel"><div class="panel-head"><div><span class="kicker">写入后核对</span><h3>最近经营回传</h3></div></div><p v-if="!history.length" class="helper">还没有人工回传记录。可以先录入一条或导入 CSV。</p><div v-else class="table-wrap"><table><thead><tr><th>日期 / 餐次</th><th>菜品</th><th>备餐 / 售出 / 剩余</th><th>预测基线变化</th><th>类型</th></tr></thead><tbody><tr v-for="row in history" :key="row.id ?? row.operation_id"><td>{{ row.business_date }}<small>{{ row.meal_period || '未标注' }}</small></td><td>{{ row.dish_name }}</td><td>{{ row.prepared_qty }} / {{ row.sold_qty }} / {{ row.leftover_qty }}</td><td>{{ row.baseline_before }} → {{ row.baseline_after }}</td><td>{{ row.submission_type }}</td></tr></tbody></table></div></section>
</template>

<style scoped>
.method-tabs{display:inline-flex;gap:4px;padding:4px;margin-bottom:16px;border:1px solid #d3e3ef;border-radius:8px;background:#edf4fa}.method-tabs button{min-height:42px;padding:8px 16px;border:0;border-radius:5px;background:transparent;color:#426783;font-size:14px;font-weight:700;cursor:pointer}.method-tabs button[aria-selected=true]{background:#fff;color:#236bb0;box-shadow:0 1px 5px rgba(28,76,117,.14)}.history-panel td small{display:block;color:#647f96;margin-top:3px}.import-operator{max-width:400px;margin:12px 0}
.view-head{margin-bottom:20px}.kicker{font-size:12px;color:#3478c9;font-weight:700}.view-head h2{font-size:28px;margin:8px 0}.view-head p,.helper,.side-note p{color:#5f7890;font-size:14px;line-height:1.7}.method-guide{display:flex;gap:14px;align-items:flex-start;padding:16px 18px;margin-bottom:18px;border:1px solid #cfe3f3;border-radius:8px;background:#f1f8ff;font-size:14px;line-height:1.7;color:#446986}.method-guide strong{flex:none;color:#245e97}.feedback-grid{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:16px;margin-bottom:16px}.panel{background:#fff;border:1px solid #dce8f2;border-radius:8px;padding:22px;margin-bottom:16px}.panel h3{margin:6px 0 12px;font-size:18px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}label{display:block;font-size:14px;color:#486680;font-weight:600}input,select,textarea{display:block;width:100%;box-sizing:border-box;margin-top:7px;padding:10px 11px;border:1px solid #cbdfee;border-radius:8px;background:#fff;color:#29445e;font-size:14px}input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #3478c9;outline-offset:1px}.wide{margin-top:14px}.check{font-size:13px;color:#416b89;line-height:1.7}.check.invalid,.error{color:#b7433d}.checkbox{display:flex;align-items:flex-start;gap:8px;margin:12px 0;font-size:14px;line-height:1.5}.checkbox input{width:auto;margin:3px 0 0}.btn{border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer;font-size:14px}.primary{background:#3478c9;color:#fff}.secondary{border:1px solid #bcd6ea;background:#eef6ff;color:#286daf}.btn:disabled{opacity:.45;cursor:not-allowed}.success{color:#16734d;font-size:14px}.side-note ol{padding-left:20px;font-size:14px;line-height:1.8;color:#496780}.side-note li{margin-bottom:10px}.import-actions{display:flex;align-items:end;gap:12px;margin:16px 0}.import-actions label{flex:1}.csv-header{display:block;overflow-x:auto;padding:12px;border-radius:8px;background:#f1f6fb;color:#254d70;font-size:12px;white-space:nowrap}.preview-box{padding:14px 16px;margin:14px 0;background:#f3f9fe;border:1px solid #d5e8f6;border-radius:8px;font-size:13px;color:#476984;overflow-wrap:anywhere}.preview-box strong{font-size:14px}.preview-box p{line-height:1.6}.preview-box ul{padding-left:19px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;min-width:660px}th{text-align:left;background:#f2f7fc;padding:11px;color:#526f88}td{padding:12px;border-top:1px solid #e4edf5}.history-panel{margin-top:16px}@media(max-width:800px){.feedback-grid,.form-grid{grid-template-columns:1fr}.import-actions,.method-guide{display:block}.import-actions button{margin-top:10px}.side-note{margin-top:0}}
</style>
