<script setup lang="ts">
import type { Dish, FeedbackRow, LearningStatus, LearningResult, ImportPreview, ImportResult, SourceEvidence } from "../api/types";
import PageHeader from "../components/PageHeader.vue";
import { computed, onMounted, ref, watch } from "vue";
import { createWriteIntent } from "../api/write-intent";
import { getAllPages, getApi, postApi, postFormApi } from "../utils/vue-api";
import { RouterLink, useRoute } from "vue-router";
import { publicPath } from "../utils/public-base";
const route = useRoute();

function todayLocal() {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}

const dishes = ref<Dish[]>([]);
const history = ref<FeedbackRow[]>([]);
const ledgerTotal = ref(0);
const historyPage = ref(1);
const historyPages = computed(() => Math.max(1, Math.ceil(history.value.length / 14)));
const visibleHistory = computed(() => history.value.slice((historyPage.value - 1) * 14, historyPage.value * 14));
const status = ref<LearningStatus>({});
const submitted = ref<LearningResult | null>(null);
const writeIntent = createWriteIntent();
const error = ref("");
const busy = ref(false);
const mode = ref<"single" | "import">("single");
const form = ref({ businessDate: todayLocal(), mealPeriod: "午餐", dishId: 0, plannedQty: 0, preparedQty: 0, soldQty: 0, discountSoldQty: 0, leftoverQty: 0, revenue: 0, weather: "晴", eventTag: "", recommendationAdopted: false, safetyConfirmed: false, operatorName: "", note: "", predictionId: null as number | null, adjustedQty: 0, adjustmentReason: "" });
const linkedScope = ref("");
const scopeKey = () => `${form.value.businessDate}|${form.value.mealPeriod}|${form.value.dishId}`;
const adjustmentValid = computed(() => !form.value.predictionId ||
  (form.value.adjustedQty >= 0 && Number.isInteger(form.value.adjustedQty) &&
    ((form.value.recommendationAdopted && form.value.adjustedQty === form.value.plannedQty) || Boolean(form.value.adjustmentReason.trim()))));
const quantityValid = computed(() => form.value.preparedQty === form.value.soldQty + form.value.leftoverQty
  && form.value.discountSoldQty <= form.value.soldQty);
const quantityDifference = computed(() => form.value.preparedQty - form.value.soldQty - form.value.leftoverQty);
const soldShare = computed(() => form.value.preparedQty > 0 ? Math.min(100, Math.max(0, form.value.soldQty / form.value.preparedQty * 100)) : 0);
const leftoverShare = computed(() => form.value.preparedQty > 0 ? Math.min(100 - soldShare.value, Math.max(0, form.value.leftoverQty / form.value.preparedQty * 100)) : 0);
const valid = computed(() => adjustmentValid.value && Boolean(form.value.dishId && form.value.operatorName.trim())
  && form.value.preparedQty > 0
  && form.value.preparedQty === form.value.soldQty + form.value.leftoverQty
  && form.value.discountSoldQty <= form.value.soldQty
  && [form.value.plannedQty, form.value.soldQty, form.value.discountSoldQty, form.value.leftoverQty, form.value.revenue].every((value) => value >= 0));

const dataFile = ref<File | null>(null);
const preview = ref<ImportPreview | null>(null);
const batchResult = ref<ImportResult | null>(null);
const importError = ref("");
const previewing = ref(false);
const importing = ref(false);
const importIntent = createWriteIntent();
const importSafetyConfirmed = ref(false);
const importOperatorName = ref("");
const sourceDeclaration = ref({ sourceName: "", provider: "", region: "", authorizationReference: "" });
const sourceEvidence = ref<SourceEvidence[]>([]);
const sourceError = ref("");
const sourceLoading = ref(false);
async function refreshSources() {
  sourceLoading.value = true; sourceError.value = "";
  try { sourceEvidence.value = await getApi<SourceEvidence[]>("/operations/source-evidence"); }
  catch (e) { sourceError.value = e instanceof Error ? e.message : "来源登记加载失败"; }
  finally { sourceLoading.value = false; }
}
const sourceComplete = computed(() => Object.values(sourceDeclaration.value).every(value => value.trim()));

type LedgerRow = {
  operationId: number; dishId: number; mealPeriod: string; dishName: string; businessDate: string; weather: string; eventTag: string;
  plannedQty: number; preparedQty: number; soldQty: number; discountSoldQty: number; leftoverQty: number;
  revenue: number; recommendationAdopted: boolean;
};
function fromLedger(row: LedgerRow): FeedbackRow {
  return {
    id: row.operationId, operation_id: row.operationId, business_date: row.businessDate,
    meal_period: row.mealPeriod, dish_id: row.dishId, dish_name: row.dishName,
    planned_qty: row.plannedQty, prepared_qty: row.preparedQty, sold_qty: row.soldQty,
    discount_sold_qty: row.discountSoldQty ?? 0, leftover_qty: row.leftoverQty, revenue: row.revenue,
    weather: row.weather, event_tag: row.eventTag, recommendation_adopted: row.recommendationAdopted,
    operator_name: "台账导入", submission_note: "", submission_type: "台账导入",
  };
}

async function refreshHistory() {
  // “最近经营记录”要展示的是台账本身。此前读的是反馈表（演示库为空），
  // 导致 98 条导入台账在这一页看不到；改读 /operations/rows 并映射成同一行结构。
  const [rows, learning] = await Promise.all([
    getAllPages<LedgerRow>("/operations/rows"),
    getApi<LearningStatus>("/operations/learning-status"),
  ]);
  history.value = rows.map(fromLedger).sort((a,b) => b.business_date.localeCompare(a.business_date) || b.id - a.id);
  ledgerTotal.value = rows.length;
  status.value = learning;
  if (mode.value === "import") await refreshSources();
}
function continueRecord(row: FeedbackRow) {
  mode.value = "single";
  submitted.value = null;
  error.value = "";
  linkedScope.value = "";
  form.value = {
    ...form.value,
    businessDate: row.business_date,
    mealPeriod: row.meal_period,
    dishId: row.dish_id,
    plannedQty: row.planned_qty,
    preparedQty: row.prepared_qty,
    soldQty: row.sold_qty,
    discountSoldQty: row.discount_sold_qty,
    leftoverQty: row.leftover_qty,
    revenue: row.revenue,
    weather: row.weather,
    eventTag: row.event_tag ?? "",
    recommendationAdopted: Boolean(row.recommendation_adopted),
    operatorName: row.operator_name ?? "",
    note: row.submission_note ?? "",
    predictionId: null,
    adjustedQty: 0,
    adjustmentReason: "",
    safetyConfirmed: false,
  };
  window.scrollTo({ top: 0, behavior: "smooth" });
}
onMounted(async () => {
  try {
    const saved = sessionStorage.getItem("foodwise-feedback-draft");
    if (saved) form.value = { ...form.value, ...JSON.parse(saved), safetyConfirmed: false };
    [dishes.value, status.value, sourceEvidence.value] = await Promise.all([getAllPages<Dish>("/dishes"), getApi<LearningStatus>("/operations/learning-status"), getApi<SourceEvidence[]>("/operations/source-evidence")]);
    await refreshHistory();
    const requestedDish = Number(route.query.dishId);
    if (dishes.value.some((dish) => dish.id === requestedDish)) form.value.dishId = requestedDish;
    else if (!dishes.value.some((dish) => dish.id === form.value.dishId)) form.value.dishId = dishes.value[0]?.id ?? 0;
    if (route.query.predictionId && route.query.businessDate && route.query.mealPeriod) {
      form.value.businessDate = String(route.query.businessDate);
      form.value.mealPeriod = String(route.query.mealPeriod);
      form.value.predictionId = Number(route.query.predictionId) || null;
      form.value.plannedQty = Number(route.query.plannedQty) || 0;
      form.value.adjustedQty = Number(route.query.adjustedQty ?? form.value.plannedQty);
      form.value.recommendationAdopted = route.query.adopted !== 'false';
      form.value.adjustmentReason = String(route.query.reason ?? "");
      linkedScope.value = scopeKey();
    } else if (form.value.predictionId) linkedScope.value = scopeKey();
  } catch (e) { error.value = e instanceof Error ? e.message : "台账数据加载失败"; }
});
watch(mode, value => { if (value === "import") void refreshSources(); });
watch(form, (value) => sessionStorage.setItem("foodwise-feedback-draft", JSON.stringify({ ...value, safetyConfirmed: false })), { deep: true });
watch(scopeKey, (value) => {
  if (linkedScope.value && value !== linkedScope.value) {
    form.value.predictionId = null;
    form.value.recommendationAdopted = false;
    linkedScope.value = "";
  }
});
async function submit() {
  if (!valid.value || !form.value.safetyConfirmed) { error.value = "请填写实际记录，核对数量关系、调整原因并确认食品安全"; return; }
  busy.value = true; error.value = ""; submitted.value = null;
  try { submitted.value = await postApi<LearningResult>("/operations/feedback", form.value, writeIntent.key(form.value)); writeIntent.complete(); sessionStorage.removeItem("foodwise-feedback-draft"); await refreshHistory(); }
  catch (e) { error.value = e instanceof Error ? e.message : "回传失败"; }
  finally { busy.value = false; }
}
function selectFile(event: Event) {
  dataFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  preview.value = null; batchResult.value = null; importError.value = ""; importSafetyConfirmed.value = false;
}
async function previewData() {
  if (!dataFile.value) return;
  previewing.value = true; importError.value = ""; preview.value = null;
  const body = new FormData(); body.append("file", dataFile.value);
  try { preview.value = await postFormApi<ImportPreview>("/operations/import/preview", body); }
  catch (e) { importError.value = e instanceof Error ? e.message : "预览失败"; }
  finally { previewing.value = false; }
}
async function importData() {
  if (!dataFile.value || !preview.value?.ready || !importOperatorName.value.trim() || !importSafetyConfirmed.value || !sourceComplete.value) return;
  importing.value = true; importError.value = ""; batchResult.value = null;
  const body = new FormData();
  body.append("file", dataFile.value);
  body.append("operatorName", importOperatorName.value.trim());
  body.append("safetyConfirmed", "true");
  for (const [key, value] of Object.entries(sourceDeclaration.value)) body.append(key, value.trim());
  try { batchResult.value = await postFormApi<ImportResult>("/operations/import", body, importIntent.key({ content: Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await dataFile.value.arrayBuffer()))).map(value => value.toString(16).padStart(2, "0")).join(""), operator: importOperatorName.value, source: sourceDeclaration.value })); importIntent.complete(); await refreshHistory(); }
  catch (e) { importError.value = e instanceof Error ? e.message : "导入失败"; }
  finally { importing.value = false; }
}
</script>

<template>
  <PageHeader title="把实际经营结果记下来" description="每个营业日按餐次和菜品填写；已有经营数据文件可先预览，再批量导入。记录会影响后续预测。" eyebrow="经营台账" /><a class="btn secondary" :href="publicPath('api/v1/operations/export')">导出当前经营台账 CSV</a>
  <div class="method-tabs" role="tablist" aria-label="录入方式"><button type="button" role="tab" :aria-selected="mode === 'single'" @click="mode = 'single'">单条录入</button><button type="button" role="tab" :aria-selected="mode === 'import'" @click="mode = 'import'">数据批量导入</button></div>
  <div v-if="mode === 'single'" class="method-guide"><strong>按当餐实际盘点记录</strong><span>营业中要处理可售剩余时，先记录今天已备餐、已售和当前剩余；优惠结束后再按最终结果更新同一条记录。未提交内容只在当前浏览器标签页暂存。<RouterLink to="/app/offers">下一步：处理剩余 →</RouterLink></span></div>

  <div v-if="mode === 'single'" class="feedback-grid">
    <section class="panel">
      <div class="panel-head"><div><span class="kicker">方式一 · 单条录入</span><h3>记录当餐盘点或最终结果</h3></div></div>
      <p class="helper">下方数值默认是 0，请按现场台账填写。优惠售出已经包含在实际售出中，不要重复相加。</p>
      <form @submit.prevent="submit">
        <div class="form-grid">
          <label>营业日期<input v-model="form.businessDate" type="date" required></label>
          <label>餐次<select v-model="form.mealPeriod" required><option>早餐</option><option>午餐</option><option>晚餐</option><option>全日</option></select></label>
          <label>菜品<select v-model.number="form.dishId" required><option v-for="dish in dishes" :key="dish.id" :value="dish.id">{{ dish.stallName ?? dish.stall_name }} · {{ dish.name }}</option></select></label>
          <label>建议备餐量（份）<input v-model.number="form.plannedQty" type="number" min="0" required></label>
          <label>实际备餐量（份）<input v-model.number="form.preparedQty" type="number" min="0" required></label>
          <label>实际售出（份）<input v-model.number="form.soldQty" type="number" min="0" required></label>
          <label>当前剩余（份）<input v-model.number="form.leftoverQty" type="number" min="0" required></label>
          <label>其中优惠售出（份）<input v-model.number="form.discountSoldQty" type="number" min="0" required></label>
          <label>当餐收入（元）<input v-model.number="form.revenue" type="number" min="0" step="0.01" required></label>
          <label>天气<select v-model="form.weather"><option>晴</option><option>小雨</option><option>大雨</option><option>高温</option><option>降温</option></select></label>
          <label>操作人员<input v-model.trim="form.operatorName" placeholder="填写实际记录人" required></label>
        </div>
        <label class="wide">校园事件或特殊情况<input v-model="form.eventTag" placeholder="例如：考试周、运动会；没有可不填"></label>
        <label class="wide">备注<textarea v-model="form.note" rows="2" placeholder="记录与常规营业不同的情况"></textarea></label>
        <p :class="['check', { invalid: !quantityValid }]">{{ form.preparedQty === form.soldQty + form.leftoverQty ? '数量关系：实际备餐 = 实际售出 + 当前剩余' : '数量不守恒：请核对备餐、售出和剩余' }}<br>优惠售出不能超过实际售出。</p>
        <div class="prediction-link" v-if="form.predictionId"><strong>已关联预测 #{{ form.predictionId }}</strong><span>将把本次采用/调整记录写回该预测</span></div>
        <label class="checkbox"><input v-model="form.recommendationAdopted" type="checkbox"> 本次采用过系统备餐建议</label>
        <div v-if="form.predictionId" class="form-grid"><label>确认执行的总备餐计划（份）<input v-model.number="form.adjustedQty" type="number" min="0" step="1"></label><label>调整或未采用的原因<input v-model="form.adjustmentReason" maxlength="300" placeholder="例如：库存不足、现场客流变化"></label></div>
        <p v-if="!adjustmentValid" class="error">调整数量或未采用建议时，请填写原因。</p>
        <label class="checkbox"><input v-model="form.safetyConfirmed" type="checkbox"> 我已核对数据，并确认食品安全要求</label>
      <button class="btn primary" type="submit" :disabled="busy || !valid || !form.safetyConfirmed">{{ busy ? "保存中…" : "核对并保存当天记录" }}</button>
        <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="submitted" class="success" role="status">本次记录已写入。同一日期、餐次和菜品可在闭餐后更新最终结果。<RouterLink to="/app/offers">去处理剩余 →</RouterLink><RouterLink to="/app/reports">查看台账汇总 →</RouterLink></p>
      </form>
    </section>
    <aside class="balance-panel" aria-label="当餐数量核对"><span class="kicker">实时核对</span><h3>这餐的份数去向</h3><strong class="balance-total">{{ form.preparedQty }}<small>份已备餐</small></strong>
      <div class="balance-track" role="img" :aria-label="`已备餐 ${form.preparedQty} 份，售出 ${form.soldQty} 份，剩余 ${form.leftoverQty} 份`"><span :style="{ width: `${soldShare}%` }"></span><span :style="{ width: `${leftoverShare}%` }"></span></div>
      <div class="balance-key"><span><i></i>已售出 <strong>{{ form.soldQty }} 份</strong></span><span><i></i>当前剩余 <strong>{{ form.leftoverQty }} 份</strong></span></div>
      <p :class="form.preparedQty === 0 ? 'pending' : quantityDifference === 0 ? 'balanced' : 'unbalanced'">{{ form.preparedQty === 0 ? '填写实际备餐后开始核对' : quantityDifference === 0 ? '数量已对齐' : `还有 ${Math.abs(quantityDifference)} 份需要核对` }}</p>
      <p class="balance-help">优惠售出已经计入实际售出。闭餐后更新同一条记录，才能得到最终结果。</p>
    </aside>
  </div>

  <section v-if="mode === 'import'" class="panel import-panel">
    <div class="panel-head"><div><span class="kicker">方式二 · 批量导入</span><h3>导入已有经营数据</h3></div></div>
    <p class="helper">支持 Excel（XLSX/XLS）、CSV、TSV 和 JSON。表格首行为表头，JSON 使用对象数组或 records 数组；字段至少包含下面九项。支持常用中文列名，菜品 ID 可在“档口管理”页面核对。</p>
    <code class="data-header">business_date,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather</code>
    <p class="helper">可选列：meal_period（早餐/午餐/晚餐）、event_tag、recommendation_adopted。没有 meal_period 的旧文件会标为“未标注餐次”。日期格式为 YYYY-MM-DD，Excel日期单元格可直接使用；Excel仅导入第一个非空工作表，公式请先转为数值。每次最多10MB、10000条记录；CSV/TSV支持UTF-8或GB18030编码。</p>
    <div class="import-actions"><label>选择数据文件<input type="file" accept=".xlsx,.xls,.csv,.tsv,.json" :disabled="importing || previewing" @change="selectFile"></label><button class="btn secondary" type="button" :disabled="!dataFile || previewing || importing" @click="previewData">{{ previewing ? "预览中…" : "先预览文件" }}</button></div>
    <div v-if="preview" class="preview-box"><strong>{{ preview.ready ? "表头齐全，可以继续核对" : "缺少必填字段" }}</strong><p>格式：{{ preview.format }}<span v-if="preview.sheetName"> · 工作表：{{ preview.sheetName }}</span>。共 {{ preview.totalRows }} 条记录，预览前 {{ preview.sampleCount }} 条；正式导入逐行校验。</p><p v-if="preview.missingFields?.length" class="error">缺少：{{ preview.missingFields.join("、") }}</p><p v-else>列名：{{ preview.headers?.join("、") }}</p><details v-if="preview.sampleRows?.length"><summary>查看数据样例</summary><div class="table-wrap"><table><thead><tr><th v-for="header in preview.headers" :key="header">{{ header }}</th></tr></thead><tbody><tr v-for="(row, index) in preview.sampleRows" :key="index"><td v-for="(value, column) in row" :key="column">{{ value }}</td></tr></tbody></table></div></details></div>
    <label class="import-operator">导入记录人<input v-model.trim="importOperatorName" autocomplete="name" placeholder="填写本次导入的实际操作人" required></label>
    <div class="form-grid">
      <label>来源名称<input v-model.trim="sourceDeclaration.sourceName" maxlength="160" placeholder="例如：档口日结台账" required></label>
      <label>来源提供方<input v-model.trim="sourceDeclaration.provider" maxlength="160" placeholder="学校或档口；未知请填待核验" required></label>
      <label>来源地域或范围<input v-model.trim="sourceDeclaration.region" maxlength="160" placeholder="实际采集地点和范围" required></label>
      <label>授权或许可引用<input v-model.trim="sourceDeclaration.authorizationReference" maxlength="300" placeholder="授权文书编号；未取得请填待核验" required></label>
    </div>
    <p class="helper">请保留原文件和授权材料。系统会保存来源登记供以后核对；填写声明不等于来源和授权已经核实。</p>
    <label class="checkbox"><input v-model="importSafetyConfirmed" type="checkbox"> 我已核对数据来源和食品安全要求</label>
    <p class="helper">导入时若同一日期、餐次和菜品已存在，会更新该记录。导入数据应填写闭餐后的最终数字。</p>
    <button class="btn primary" type="button" :disabled="!preview?.ready || !importOperatorName.trim() || !importSafetyConfirmed || !sourceComplete || importing" @click="importData">{{ importing ? "导入中…" : "确认导入台账" }}</button>
    <p v-if="importError" class="error" role="alert">{{ importError }}</p>
    <div v-if="batchResult" class="preview-box" role="status"><strong>导入完成：{{ batchResult.imported }} 行成功，{{ batchResult.rejected }} 行被拒绝</strong><p>其中 {{ batchResult.duplicates }} 行更新了同日期、同菜品的已有记录。来源仍待核验。</p><ul v-if="batchResult.errors?.length"><li v-for="(item, index) in batchResult.errors" :key="index">{{ item }}</li></ul><details><summary>来源核对信息</summary><p>登记编号：{{ batchResult.sourceEvidenceId }}</p><p>文件 SHA-256：{{ batchResult.sourceSha256 }}</p></details></div>
  </section>

  <section class="panel history-panel"><div class="panel-head"><div><span class="kicker">写入后核对</span><h3>最近经营记录</h3></div><span v-if="ledgerTotal" class="ledger-count">共 {{ ledgerTotal }} 条台账</span></div><p v-if="!history.length" class="helper">还没有经营记录。可以先录入一条或导入数据文件。</p><template v-else><div class="table-wrap ledger-table"><table><thead><tr><th>日期 / 餐次</th><th>菜品</th><th>备餐 / 售出 / 剩余</th><th>录入情况</th><th>继续操作</th></tr></thead><tbody><tr v-for="row in visibleHistory" :key="row.id ?? row.operation_id"><td>{{ row.business_date }}<small>{{ row.meal_period || '未标注' }}</small></td><td>{{ row.dish_name }}</td><td>{{ row.prepared_qty }} / {{ row.sold_qty }} / {{ row.leftover_qty }}</td><td>{{ row.submission_type }}</td><td><button class="btn secondary" type="button" @click="continueRecord(row)">继续填写</button></td></tr></tbody></table></div><ul class="ledger-cards"><li v-for="row in visibleHistory" :key="'card-' + row.id"><div class="ledger-card-head"><strong>{{ row.dish_name }}</strong><span>{{ row.business_date }}</span></div><p class="ledger-card-nums">备餐 {{ row.prepared_qty }} · 售出 {{ row.sold_qty }} · 剩余 {{ row.leftover_qty }}</p><button class="btn secondary" type="button" @click="continueRecord(row)">继续填写</button></li></ul><div class="ledger-pagination"><span>按营业日期从近到远 · 第 {{ historyPage }} / {{ historyPages }} 页</span><button class="btn secondary" type="button" :disabled="historyPage <= 1" @click="historyPage--">上一页</button><button class="btn secondary" type="button" :disabled="historyPage >= historyPages" @click="historyPage++">下一页</button></div></template></section>
  <section v-if="mode === 'import'" class="panel history-panel" aria-labelledby="source-register-title">
    <h3 id="source-register-title">最近来源登记</h3>
    <p class="helper">最多显示最近 100 条。登记保存文件指纹与来源声明；请保留原文件及授权材料，逐项核验后再用于真实校园训练。</p>
    <button class="btn secondary" type="button" :disabled="sourceLoading" @click="refreshSources">{{ sourceLoading ? '加载中…' : '刷新来源登记' }}</button>
    <p v-if="sourceError" class="error" role="alert">{{ sourceError }}</p>
    <p v-else-if="!sourceLoading && !sourceEvidence.length" class="helper">还没有来源登记，完成数据导入后会在这里保留记录。</p>
    <details v-for="source in sourceEvidence" :key="source.source_evidence_id" class="preview-box">
      <summary>来源 #{{ source.source_evidence_id }} · {{ source.source_name }} · {{ source.verification_status === 'DECLARED_UNVERIFIED' ? '声明待核验' : '核验状态：' + source.verification_status }}</summary>
      <p>文件：{{ source.file_name }} · 提供方：{{ source.provider }}</p>
      <p>声明地域或范围：{{ source.declared_region }}</p>
      <p>授权或许可引用：{{ source.authorization_reference }}</p>
      <p>文件 SHA-256：{{ source.source_sha256 }}</p>
      <p>登记人：{{ source.created_by }} · 登记时间：{{ source.created_at }}</p>
    </details>
  </section>
</template>

<style scoped>
.prediction-link{display:grid;gap:5px;padding:12px;background:var(--fw-tint);color:#315f86;border-radius:8px;font-size:13px}
.method-tabs{display:inline-flex;gap:4px;padding:4px;margin-bottom:16px;border:1px solid #d3e3ef;border-radius:8px;background:#edf4fa}.method-tabs button{min-height:42px;padding:8px 16px;border:0;border-radius:5px;background:transparent;color:#426783;font-size:14px;font-weight:700;cursor:pointer}.method-tabs button[aria-selected=true]{background:#fff;color:#236bb0;box-shadow:0 1px 5px rgba(28,76,117,.14)}.history-panel td small{display:block;color:#647f96;margin-top:3px}.import-operator{max-width:400px;margin:12px 0}
.view-head p,.helper,.side-note p{color:#5f7890;font-size:14px;line-height:1.7}.method-guide{display:flex;gap:14px;align-items:flex-start;padding:16px 18px;margin-bottom:18px;border:1px solid #cfe3f3;border-radius:8px;background:#f1f8ff;font-size:14px;line-height:1.7;color:#446986}.method-guide strong{flex:none;color:var(--fw-primary-strong)}.feedback-grid{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:16px;margin-bottom:16px}.panel h3{margin:6px 0 12px;font-size:18px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}label{display:block;font-size:14px;color:var(--fw-muted);font-weight:600}input,select,textarea{display:block;width:100%;box-sizing:border-box;margin-top:7px;padding:10px 11px;border:1px solid #cbdfee;border-radius:8px;background:#fff;color:#29445e;font-size:14px}input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #28698f;outline-offset:1px}.wide{margin-top:14px}.check{font-size:13px;color:#416b89;line-height:1.7}.check.invalid,.error{color:#b7433d}.checkbox{display:flex;align-items:flex-start;gap:8px;margin:12px 0;font-size:14px;line-height:1.5}.checkbox input{width:auto;margin:3px 0 0}.btn{border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer;font-size:14px}.primary{background:var(--fw-primary);color:#fff}.secondary{border:1px solid #bcd6ea;background:var(--fw-tint);color:var(--fw-primary)}.btn:disabled{opacity:.45;cursor:not-allowed}.success{color:#16734d;font-size:14px}.side-note ol{padding-left:20px;font-size:14px;line-height:1.8;color:#496780}.side-note li{margin-bottom:10px}.import-actions{display:flex;align-items:end;gap:12px;margin:16px 0}.import-actions label{flex:1}.data-header{display:block;overflow-x:auto;padding:12px;border-radius:8px;background:var(--fw-tint);color:#254d70;font-size:12px;white-space:nowrap}.preview-box{padding:14px 16px;margin:14px 0;background:#f3f9fe;border:1px solid #d5e8f6;border-radius:8px;font-size:13px;color:#476984;overflow-wrap:anywhere}.preview-box strong{font-size:14px}.preview-box p{line-height:1.6}.preview-box ul{padding-left:19px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;min-width:660px}th{text-align:left;background:#f2f7fc;padding:11px;color:#526f88}td{padding:12px;border-top:1px solid #e4edf5}.history-panel{margin-top:16px}@media(max-width:800px){.feedback-grid,.form-grid{grid-template-columns:1fr}.import-actions,.method-guide{display:block}.import-actions button{margin-top:10px}.side-note{margin-top:0}}
</style>
<style scoped>
.feedback-grid{grid-template-columns:minmax(0,1fr) minmax(240px,290px);align-items:start}.balance-panel{position:sticky;top:92px;padding:20px;border:1px solid #dbe5eb;border-radius:8px;background:#fff}.balance-panel h3{margin:5px 0 18px;color:#2a485e;font-size:17px}.balance-total{display:block;color:var(--fw-primary-strong);font-size:36px;line-height:1.1;font-variant-numeric:tabular-nums}.balance-total small{display:block;margin-top:7px;color:#6d8190;font-size:12px}.balance-track{display:flex;height:18px;overflow:hidden;margin:20px 0 14px;background:#eef2ee;border-radius:3px}.balance-track span:first-child{background:#3b84ad}.balance-track span:nth-child(2){background:#dda96a}.balance-key{display:grid;gap:9px;color:#5d7382;font-size:12px}.balance-key span{display:flex;align-items:center;gap:6px}.balance-key i{display:inline-block;width:9px;height:9px;border-radius:2px;background:#3b84ad}.balance-key span:nth-child(2) i{background:#dda96a}.balance-key strong{margin-left:auto;font-size:13px;color:#2a485e}.balanced,.unbalanced,.pending{margin:20px 0 0;padding:10px 12px;border-left:3px solid #3b84ad;background:#edf5f9;color:#2d698b;font-weight:700;font-size:12px}.unbalanced{border-color:#bb6b44;background:#fff2ea;color:#9a4b33}.pending{border-color:#9bb8c9;background:#f1f5f8;color:#526f83}.balance-help{color:#6a7d8b;font-size:12px;line-height:1.6;margin-top:15px}.method-guide{border-radius:6px;border-color:var(--fw-border);background:#eef5f9;color:#496a7e}.method-guide strong{color:var(--fw-primary)}@media(max-width:800px){.feedback-grid{grid-template-columns:1fr}.balance-panel{position:static;order:-1}}
</style>

<style scoped>
.ledger-count{font-size:12px;color:var(--fw-muted);white-space:nowrap;align-self:center}
.ledger-cards{display:none;list-style:none;margin:12px 0 0;padding:0;gap:10px}
.ledger-cards li{border:1px solid var(--fw-border);border-radius:8px;padding:12px 14px;background:#fff}
.ledger-card-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.ledger-card-head strong{font-size:14px;color:var(--fw-ink)}
.ledger-card-head span{font-size:12px;color:var(--fw-muted);font-variant-numeric:tabular-nums}
.ledger-card-nums{margin:6px 0 10px;font-size:12.5px;color:#44606d}
.ledger-more{display:none}
@media(max-width:640px){
  .ledger-table{display:none}
  .ledger-cards{display:grid}
  .ledger-more{display:block;margin-top:10px}
  .history-panel .panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
}
</style>
