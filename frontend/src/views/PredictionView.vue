<script setup lang="ts">
import type { AssistantAdvice, Dish, Session, Metadata, DecisionPreview, PredictionResponse, PreparationPlan } from "../api/types";
import PageHeader from "../components/PageHeader.vue";
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { createWriteIntent } from "../api/write-intent";
import { getAllPages, getApi, postApi } from "../utils/vue-api";
import { dishPhoto } from "../utils/dish-photo";

const dishes = ref<Dish[]>([]);
const dishId = ref<number | null>(null);
const weather = ref("晴");
const targetDate = ref(new Intl.DateTimeFormat("sv-SE").format(new Date(Date.now() + 86400000)));
const mealPeriod = ref("午餐");
const demoMode = ref(false);
const demoDate = ref("");
const demoInputsLoaded = ref(false);
function fillDemoConditions() {
  if (!demoMode.value) return;
  if (demoDate.value) targetDate.value = demoDate.value;
  mealPeriod.value = "午餐";
  planInputs.value = { stockServings: 120, capacityServings: 100, minimumBatch: 5, leadMinutes: 20, preparationStart: "09:30", serviceStart: "11:00", serviceEnd: "13:00" };
  demoInputsLoaded.value = true;
}

const examWeek = ref(false);
const campusEvent = ref(false);
const loading = ref(false);
const result = ref<PredictionResponse | null>(null);
const writeIntent = createWriteIntent();
const error = ref("");
const decision = ref({ adopted: true, adjustedQty: 0, reason: "" });
const decisionBusy = ref(false);
const decisionMessage = ref("");
const decisionIntent = createWriteIntent();
const replayBusy = ref(false);
const replayMessage = ref("");
type SourceEvidence = { revisionId:number; sourceEvidenceId:number|null; sourceRowNo:number|null; sourceSha256:string|null; sourceName:string|null; verificationStatus:string };
const replaySources = ref<SourceEvidence[]>([]);
const plan = ref<PreparationPlan | null>(null);
const planBusy = ref(false);
const planMessage = ref("");
const planIntent = createWriteIntent();
const planUsesDecisionRecord = ref(false);
const engine = ref("robust-baseline");
const preview = ref<DecisionPreview | null>(null);
const previewError = ref("");
const assistantPresets = ["为什么建议这么多份？", "如果成本降到 4 元会怎样？", "帮我复盘一下昨天的执行情况"];
const assistantQuestion = ref(assistantPresets[0]);
const assistantBusy = ref(false);
const assistantResult = ref<AssistantAdvice | null>(null);
const assistantError = ref("");
async function askAssistant(text?: string) {
  if (!dishId.value || assistantBusy.value) return;
  const question = (text ?? assistantQuestion.value).trim();
  if (!question) return;
  assistantQuestion.value = question;
  assistantBusy.value = true;
  assistantError.value = "";
  assistantResult.value = null;
  try {
    assistantResult.value = await postApi<AssistantAdvice>("/assistant/advice", {
      dishId: dishId.value,
      targetDate: targetDate.value,
      question,
      weather: weather.value,
      examWeek: examWeek.value,
      campusEvent: campusEvent.value,
    });
  } catch (e) {
    assistantError.value = e instanceof Error ? e.message : "参谋暂时不可用，请稍后再试";
  } finally {
    assistantBusy.value = false;
  }
}
const engineLabels: Record<string, string> = { "robust-baseline": "稳健参考" };
const band = computed(() => {
  const p = preview.value;
  if (!p) return null;
  const lo = Math.max(0, Math.min(p.q05, p.intervalLow) - 5);
  const hi = Math.max(p.q95, p.intervalHigh) + 5;
  const span = Math.max(hi - lo, 1);
  const pct = (value: number) => Math.min(100, Math.max(0, ((value - lo) / span) * 100));
  return {
    left: pct(p.intervalLow),
    width: Math.max(1.5, pct(p.intervalHigh) - pct(p.intervalLow)),
    point: pct(p.quantity),
  };
});
function printSheet() {
  window.print();
}

// 成本试算：只影响预览，不写进决策记录（记录必须用菜品主数据的成本参数才能重放）
const costTrial = ref({ enabled: false, price: "" as number | string, unitCost: "" as number | string, lossRate: "" as number | string });

function costQuery(): string {
  const t = costTrial.value;
  if (!t.enabled || t.price === "" || t.unitCost === "") return "";
  const parts = [`&price=${t.price}`, `&unitCost=${t.unitCost}`];
  if (t.lossRate !== "") parts.push(`&lossRate=${Number(t.lossRate) / 100}`);
  return parts.join("");
}

async function loadPreview() {
  if (!dishId.value) return;
  previewError.value = "";
  try {
    preview.value = await getApi<DecisionPreview>(`/decisions/preview?dishId=${dishId.value}`
      + `&weather=${encodeURIComponent(weather.value)}&examWeek=${examWeek.value}`
      + `&campusEvent=${campusEvent.value}&targetDate=${targetDate.value}&engine=${engine.value}`
      + costQuery());
  } catch (e) {
    preview.value = null;
    previewError.value = e instanceof Error ? e.message : "决策建议加载失败";
  }
}

async function applyCostTrial() {
  // 没填的价格/成本沿用当前预览值，避免"只改损耗"却因为缺参数被拒
  if (costTrial.value.price === "" && preview.value) costTrial.value.price = preview.value.price;
  if (costTrial.value.unitCost === "" && preview.value) costTrial.value.unitCost = preview.value.unitCost;
  costTrial.value.enabled = true;
  await loadPreview();
}

async function resetCostTrial() {
  costTrial.value = { enabled: false, price: "", unitCost: "", lossRate: "" };
  await loadPreview();
}
const planInputs = ref({ stockServings: "" as number | string, capacityServings: "" as number | string, minimumBatch: "" as number | string, leadMinutes: "" as number | string, preparationStart: "", serviceStart: "", serviceEnd: "" });
const planChanged = computed(() => Boolean(plan.value && Object.entries(plan.value.inputs).some(([key, value]) => {
  const current = planInputs.value[key as keyof typeof planInputs.value];
  return typeof value === "string" ? value.slice(0, 5) !== String(current).slice(0, 5) : value !== current;
})));
watch([dishId, targetDate, mealPeriod, weather, examWeek, campusEvent], () => { result.value = null; plan.value = null; planMessage.value = ""; });
watch([dishId, targetDate, weather, examWeek, campusEvent, engine], () => { void loadPreview(); });
const prediction = computed(() => result.value?.prediction);
const selectedDish = computed(() => dishes.value.find((dish) => dish.id === dishId.value));
const canPlan = computed(() => Boolean(result.value && ["早餐", "午餐", "晚餐"].includes(result.value.mealPeriod || "")));
onMounted(async () => {
  try {
    const [list, session, metadata] = await Promise.all([getAllPages<Dish>("/dishes"), getApi<Session>("/session"), getApi<Metadata>("/analytics/metadata")]);
    dishes.value = list;
    demoMode.value = session.demo;
    if (session.demo && metadata.period_end) {
      const businessDate = String(metadata.period_end).includes("T") ? new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date(metadata.period_end)) : String(metadata.period_end).slice(0, 10);
      const next = new Date(`${businessDate}T00:00:00+08:00`); next.setDate(next.getDate() + 1);
      demoDate.value = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(next);
      targetDate.value = demoDate.value;
    }
    dishId.value = dishes.value[0]?.id ?? null;
    await loadPreview();
  } catch (e) { error.value = e instanceof Error ? e.message : "菜品加载失败"; }
});
async function predict() {
  if (!dishId.value || planBusy.value || decisionBusy.value) return;
  const requestSignature = JSON.stringify([dishId.value, targetDate.value, mealPeriod.value, weather.value, examWeek.value, campusEvent.value]);
  loading.value = true; error.value = ""; result.value = null; plan.value = null; planMessage.value = ""; decisionMessage.value = ""; replayMessage.value = "";
  replaySources.value = [];
  try {
    const payload = { dishId: dishId.value, weather: weather.value, examWeek: examWeek.value, campusEvent: campusEvent.value, engine: engine.value, targetDate: targetDate.value, mealPeriod: mealPeriod.value, sourceNature: "经营台账；来源待逐笔核验" };
    const response = await postApi<PredictionResponse>("/predictions", payload, writeIntent.key(payload)); writeIntent.complete();
    if (requestSignature !== JSON.stringify([dishId.value, targetDate.value, mealPeriod.value, weather.value, examWeek.value, campusEvent.value])) return;
    result.value = response;
    decision.value = { adopted: true, adjustedQty: result.value.prediction.predictedMid, reason: "" };
  } catch (e) { error.value = e instanceof Error ? e.message : "预测失败"; }
  finally { loading.value = false; }
}
async function createPreparationPlan() {
  const current = result.value;
  if (!current) return;
  if (!canPlan.value) { planMessage.value = "请先选择早餐、午餐或晚餐，再生成现场备餐计划。"; return; }
  if ([planInputs.value.stockServings, planInputs.value.capacityServings, planInputs.value.minimumBatch, planInputs.value.leadMinutes].some(v => typeof v !== "number" || !Number.isInteger(v))) { planMessage.value = "请填写现场核实的整数份数、批量和提前期。"; return; }
  planBusy.value = true; planMessage.value = "";
  const payload = { ...planInputs.value };
  try {
    const decisionRecord = current.engineKey !== "rule";
    planUsesDecisionRecord.value = decisionRecord;
    const endpoint = decisionRecord
      ? `/decisions/${current.prediction.predictionId}/preparation-plans?mealPeriod=${encodeURIComponent(current.mealPeriod || "")}`
      : `/predictions/${current.prediction.predictionId}/preparation-plans`;
    const saved = await postApi<PreparationPlan>(endpoint, payload, planIntent.key({ predictionId: current.prediction.predictionId, ...payload }));
    planIntent.complete();
    if (result.value !== current) return;
    plan.value = saved;
    decision.value.adjustedQty = saved.plan.plannedTotal;
    decision.value.reason = "按现场库存、产能、批量和时段约束调整";
    planMessage.value = `计划已留档（编号 #${plan.value.id}）。请现场负责人复核售速、原料和食品安全后执行。`;
  } catch (e) { planMessage.value = e instanceof Error ? e.message : "备餐计划生成失败，请重试"; }
  finally { planBusy.value = false; }
}
async function loadPreparationPlan() {
  if (!plan.value?.id) return;
  planBusy.value = true; planMessage.value = "";
  try { plan.value = await getApi<PreparationPlan>(`${planUsesDecisionRecord.value ? "/decision-preparation-plans" : "/preparation-plans"}/${plan.value.id}`); planMessage.value = "已从数据库读回本次备餐计划。"; }
  catch (e) { planMessage.value = e instanceof Error ? e.message : "计划读回失败，请重试"; }
  finally { planBusy.value = false; }
}
async function confirmDecision() {
  const current = result.value;
  if (!current?.targetDate || !current?.mealPeriod) return;
  if (plan.value && (planChanged.value || decision.value.adjustedQty > plan.value.plan.plannedTotal)) { decisionMessage.value = "现场参数已修改或执行量超过计划，请重新生成计划并核对数量。"; return; }
  if ((!decision.value.adopted || decision.value.adjustedQty !== current.prediction.predictedMid) && !decision.value.reason.trim()) {
    decisionMessage.value = "调整数量或未采用建议时，请填写原因。"; return;
  }
  decisionBusy.value = true; decisionMessage.value = "";
  try {
    const payload = { ...decision.value, dishId: current.prediction.dishId, targetDate: current.targetDate, mealPeriod: current.mealPeriod };
    const decisionRecord = current.engineKey !== "rule";
    planUsesDecisionRecord.value = decisionRecord;
    await postApi(decisionRecord ? `/decisions/${current.prediction.predictionId}/feedback` : `/predictions/${current.prediction.predictionId}/feedback`, payload, decisionIntent.key(payload));
    decisionIntent.complete(); decisionMessage.value = "执行计划已保存，闭餐后再填写实际结果。";
  } catch (e) { decisionMessage.value = e instanceof Error ? e.message : "确认失败，请重试"; }
  finally { decisionBusy.value = false; }
}
async function checkOriginalInputs() {
  const current = result.value;
  if (!current) return;
  replayBusy.value = true; replayMessage.value = "";
  try {
    const replay = await getApi<{ dataVerified: boolean; revisionIds: number[]; sourceEvidence?:SourceEvidence[] }>(`/predictions/${current.prediction.predictionId}/replay`);
    if (result.value !== current) return;
    replaySources.value = replay.sourceEvidence ?? [];
    replayMessage.value = replay.dataVerified
      ? `输入核对通过：${replay.revisionIds.length}个台账版本与原预测一致。此项核对不代表预测准确率或现场效果。`
      : "本次输入未通过核对，请联系管理员查看原始记录。";
  } catch (e) {
    if (result.value === current) replayMessage.value = e instanceof Error ? e.message : "输入核对失败，请重试";
  } finally { replayBusy.value = false; }
}
</script>

<template>
      <PageHeader title="确定下一餐备多少" description="先选具体餐次，再核对库存、产能和准备时间。建议只作参考，由当班负责人确认后执行。" eyebrow="营业前" />
  <div v-if="demoMode" class="demo-context"><div><strong>历史场景演示</strong><span>演示日期接续已有台账，不是今天的经营数据。库存与产能可载入示例后体验，现场使用须重新核实。</span></div><button type="button" class="btn secondary" @click="fillDemoConditions">载入示例条件</button><small v-if="demoInputsLoaded" role="status">已载入示例：原料 120 份、产能 100 份、每批 5 份；请生成建议后核对计划。</small></div>
  <div class="prediction-grid">
    <section class="panel form-panel">
      <div class="panel-head"><span class="kicker">输入条件</span><h3>所选营业日，需要备多少？</h3></div>
      <label>菜品<select v-model.number="dishId"><option v-for="dish in dishes" :key="dish.id" :value="dish.id">{{ dish.name }}</option></select></label>
      <div v-if="dishPhoto(selectedDish?.name)" class="dish-preview"><img :src="dishPhoto(selectedDish?.name)!" :alt="`${selectedDish?.name}同类菜品实拍示意`" width="124" height="90"><span><strong>{{ selectedDish?.name }}</strong>同类菜品实拍示意</span></div>
      <label>预计天气<select v-model="weather"><option>晴</option><option>小雨</option><option>大雨</option><option>高温</option><option>降温</option></select></label>
      <label>目标营业日<input v-model="targetDate" type="date"></label>
      <label>餐次<select v-model="mealPeriod"><option>全日</option><option>早餐</option><option>午餐</option><option>晚餐</option></select></label>
      <label class="check"><input v-model="examWeek" type="checkbox"> 目标日是考试周</label>
      <label class="check"><input v-model="campusEvent" type="checkbox"> 目标日有校园活动</label>
      <p class="form-help">请按目标营业日情况选择。若没有历史销量，先到“录入或导入台账”添加该菜品记录。</p>
      <button class="btn primary" :disabled="loading || planBusy || decisionBusy || !dishId" @click="predict">{{ loading ? "计算中…" : "生成备餐建议" }}</button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>
    <section class="panel result-panel">
      <div class="panel-head"><span class="kicker">怎么执行</span><h3>先做首批，再视销售补餐</h3></div>
      <section v-if="preview && preview.status === 'ready'" class="decision-card" aria-labelledby="decision-card-title">
        <div class="dc-head">
          <div><span class="kicker">备餐参考</span><h4 id="decision-card-title">建议备餐数量与成本口径</h4></div>
        </div>
        <div v-if="band" class="band" role="img" :aria-label="`区间 ${preview.intervalLow} 到 ${preview.intervalHigh} 份，建议 ${preview.quantity} 份`">
          <div class="band-track">
            <span class="band-range" :style="{ left: band.left + '%', width: band.width + '%' }"></span>
            <span class="band-point" :style="{ left: band.point + '%' }"></span>
          </div>
          <div class="band-labels"><span>区间下限 {{ preview.intervalLow }}</span><span>建议 {{ preview.quantity }} 份</span><span>区间上限 {{ preview.intervalHigh }}</span></div>
        </div>
        <dl class="dc-cost">
          <div><dt>售价 / 成本</dt><dd>{{ preview.price }} / {{ preview.unitCost }} 元</dd></div>
          <div><dt>少备一份的估算影响</dt><dd>{{ preview.underage }} 元<small>包含缺货影响估算</small></dd></div>
          <div><dt>多备一份的估算影响</dt><dd>{{ preview.overage }} 元<small>扣除预估折价回收</small></dd></div>
          <div v-if="preview.lossRate > 0"><dt>制作损耗</dt><dd>{{ (preview.lossRate * 100).toFixed(0) }}%，有效成本 {{ preview.effectiveUnitCost.toFixed(2) }} 元</dd></div>
        </dl>
        <details class="cost-details"><summary>调整售价与成本，试算备餐变化</summary><div class="dc-trial">
          <span class="kicker">成本试算</span>
          <label>售价<input v-model="costTrial.price" type="number" min="0" step="0.1" :placeholder="String(preview.price)"></label>
          <label>成本<input v-model="costTrial.unitCost" type="number" min="0" step="0.1" :placeholder="String(preview.unitCost)"></label>
          <label>制作损耗 %<input v-model="costTrial.lossRate" type="number" min="0" max="80" step="1" placeholder="0"></label>
          <button type="button" @click="applyCostTrial">按此成本试算</button>
          <button v-if="costTrial.enabled" type="button" class="ghost" @click="resetCostTrial">恢复菜品价格</button>
          <small>试算不修改菜品定价；确认计划时仍使用已登记的价格和成本。</small>
        </div>
        </details><p class="dc-formula">少备可能提前售罄，多备可能留下剩余；请结合当餐原料、设备和现场客流核对。</p>
        <details class="calculation-details"><summary>查看数据依据与复核信息</summary><dl><div><dt>建议计算方式</dt><dd>{{ engineLabels[engine] ?? engine }} · {{ preview.modelVersion }}</dd></div><div><dt>成本权衡参考值</dt><dd>{{ preview.criticalRatio.toFixed(3) }}</dd></div><div><dt>需求参考范围计算</dt><dd>{{ preview.calibrationMethod }} · P5 {{ Math.round(preview.q05) }} / P95 {{ Math.round(preview.q95) }} · 校正 {{ preview.offset }} 份</dd></div><div><dt>历史样本内覆盖参考</dt><dd>{{ Math.round(preview.coverage * 100) }}%；不代表单次结果保证落在区间内</dd></div><div v-if="engine === 'robust-baseline'"><dt>历史波动</dt><dd>同菜品同星期近四周中位数 {{ Math.round(preview.center) }} 份；σ {{ preview.sigma }} 份</dd></div></dl></details>
        <details v-if="preview.notes?.length" class="calculation-details"><summary>查看计算方法与适用限制</summary><p class="dc-notes">{{ preview.notes.join(" ") }}</p></details>
      </section>
      <p v-if="previewError" class="error" role="alert">{{ previewError }}</p>
      <details class="assistant"><summary>有疑问？询问经营参谋</summary><div aria-labelledby="assistant-title">
        <div class="assistant-head">
          <div><span class="kicker">经营参谋</span><h4 id="assistant-title">问一句，答案带出处</h4></div>
          <span class="assistant-tag">依据当前记录回答</span>
        </div>
        <div class="assistant-presets" role="group" aria-label="常见问题">
          <button v-for="preset in assistantPresets" :key="preset" type="button" class="assistant-chip"
                  :disabled="assistantBusy || !dishId" @click="askAssistant(preset)">{{ preset }}</button>
        </div>
        <form class="assistant-ask" @submit.prevent="askAssistant()">
          <input v-model.trim="assistantQuestion" maxlength="120" :disabled="assistantBusy"
                 placeholder="例如：这个建议量怎么算的" aria-label="向参谋提问">
          <button class="btn primary" type="submit" :disabled="assistantBusy || !assistantQuestion">
            {{ assistantBusy ? "思考中…" : "问参谋" }}
          </button>
        </form>
        <p v-if="assistantError" class="error" role="alert">{{ assistantError }}</p>
        <div v-if="assistantResult" class="assistant-answer" role="status">
          <p class="assistant-text">{{ assistantResult.answer }}</p>
          <p v-if="assistantResult.suggestedAction" class="assistant-action">
            建议量 {{ assistantResult.suggestedAction.quantity }} 份 · {{ assistantResult.suggestedAction.reason }}
          </p>
          <p v-if="assistantResult.refusal" class="assistant-refusal">
            {{ assistantResult.refusal.reason }}
          </p>
          <ul v-if="assistantResult.citations.length" class="assistant-cites">
            <li v-for="cite in assistantResult.citations" :key="cite.type + cite.ref">
              <b>{{ cite.type }}</b> {{ cite.ref }}
            </li>
          </ul>
        </div>
        <p class="assistant-note">可以询问建议依据、调整成本试算或核对执行记录。食品安全仍需现场人员确认。</p>
      </div></details>
      <p v-if="preview && preview.status !== 'ready'" class="preview-unavailable" role="status">{{ preview.unavailableReason || "暂时无法计算参考数量，请先核对该菜品的历史记录。" }}</p>
      <div v-if="!prediction" class="empty"><strong>{{ preview?.status === "ready" ? "参考已就绪，下一步安排当餐" : "先核对菜品与营业条件" }}</strong><span>点击左侧“生成备餐建议”，查看首批制作与补餐安排。</span></div>
      <div v-else class="result">
        <div class="result-main"><span>建议参考范围（单位：份）</span><strong>{{ prediction.predictedLow }}–{{ prediction.predictedHigh }} <small>份</small></strong><em>这是历史数据下的参考范围，不是保证值；请按现场情况确认。</em></div>
        <div class="result-kpis"><div><span>先制作</span><strong>{{ prediction.firstBatch }} 份</strong></div><div><span>视销售补餐</span><strong>{{ prediction.replenishQty }} 份</strong></div><div><span>停做时间</span><strong>{{ result?.mealPeriod === "午餐" ? "午餐演示 " + String(prediction.stopHour).padStart(2,"0") + ":" + String(prediction.stopMinute).padStart(2,"0") : "按当餐规定" }}</strong></div></div>
        <div class="batch-visual" role="img" :aria-label="`建议首批 ${prediction.firstBatch} 份，视销售补餐 ${prediction.replenishQty} 份`">
          <div class="batch-head"><strong>分批备餐构成</strong><span>参考总量 {{ prediction.firstBatch + prediction.replenishQty }} 份</span></div>
          <div class="batch-track"><span class="batch-first" :style="{ flex: Math.max(0, prediction.firstBatch) }"></span><span class="batch-replenish" :style="{ flex: Math.max(0, prediction.replenishQty) }"></span></div>
          <div class="batch-labels"><span><i></i>首批 {{ prediction.firstBatch }} 份</span><span><i></i>视销售补餐 {{ prediction.replenishQty }} 份</span></div>
        </div>
        <div class="risk"><b>售罄风险：{{ prediction.soldOutRisk }}</b><b>剩余风险：{{ prediction.leftoverRisk }}</b></div>
        <p v-if="prediction.advice">{{ prediction.advice.summary }}</p>
        <details class="prediction-evidence"><summary>查看数据范围与计算依据</summary><div class="prediction-meta"><span>模型 {{ result?.modelVersion }}</span><span>历史营业日截止 {{ result?.historyCutoff ?? "未记录" }}</span><span>最近台账 {{ result?.historyLatestDate ?? "未记录" }} · {{ result?.historySampleCount ?? 0 }} 个营业日</span><span v-if="result?.predictionCutoffAt">台账可用截止 {{ new Date(result.predictionCutoffAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}（北京时间） · {{ result.revisionIds?.length ?? 0 }} 个版本</span><span>来源 {{ result?.sourceNature }}</span></div></details>
        <section class="preparation-plan" aria-labelledby="plan-title">
          <div class="plan-head"><div><span class="kicker">当餐安排</span><h4 id="plan-title">按现场条件安排制作</h4></div><span class="plan-state">只做参考，不自动扣库存</span></div>
          <p class="form-help">请填写本菜品独占分配的原料折算份数和产能，不要把共享额度重复填给多个菜品。计划按整批取整，单独标出参考缺口。</p>
          <fieldset class="constraint-fields" :disabled="planBusy || loading"><legend>核对原料、产能与时间</legend>
            <label>可用库存（份）<input v-model.number="planInputs.stockServings" type="number" min="0" step="1"></label>
            <label>当餐产能上限（份）<input v-model.number="planInputs.capacityServings" type="number" min="0" step="1"></label>
            <label>最小批量（份）<input v-model.number="planInputs.minimumBatch" type="number" min="1" step="1"></label>
            <label>提前期（分钟）<input v-model.number="planInputs.leadMinutes" type="number" min="1" max="240" step="1"></label>
            <div class="time-grid"><label>开始准备<input v-model="planInputs.preparationStart" type="time"></label><label>开餐时间<input v-model="planInputs.serviceStart" type="time"></label><label>结束营业<input v-model="planInputs.serviceEnd" type="time"></label></div>
          </fieldset>
          <button class="btn primary" :disabled="planBusy || !canPlan" @click="createPreparationPlan">{{ planBusy ? "生成中…" : (canPlan ? "生成并留档备餐计划" : "先选择具体餐次") }}</button>
          <p v-if="planChanged" class="error" role="status">现场参数已修改，下方是旧计划，请重新生成后再确认执行。</p>
          <div v-if="plan" class="plan-result">
            <div class="plan-kpis"><div><span>首批制作</span><strong>{{ plan.plan.firstBatch }} 份</strong></div><div><span>可补餐</span><strong>{{ plan.plan.replenishQty }} 份</strong></div><div><span>计划总量</span><strong>{{ plan.plan.plannedTotal }} 份</strong></div><div><span>参考缺口</span><strong>{{ plan.plan.uncoveredDemand }} 份</strong></div></div>
            <p v-if="plan.plan.canReplenish">最晚补餐准备时间：{{ plan.plan.latestReplenishStart?.slice(0,5) }}</p><p v-else>当前条件下不安排补餐，需现场根据售速人工复核。</p>
            <ul><li v-for="warning in plan.plan.warnings" :key="warning">{{ warning }}</li></ul>
            <div class="plan-actions"><span>计划编号 #{{ plan.id }} · {{ new Date(plan.createdAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}（北京时间）</span><button class="btn" type="button" :disabled="planBusy" @click="loadPreparationPlan">查看已保存计划</button></div>
          </div>
          <p v-if="planMessage" role="status">{{ planMessage }}</p>
        </section>
        <button class="btn" :disabled="replayBusy" @click="checkOriginalInputs">{{ replayBusy ? "核对中…" : "核对本次预测输入" }}</button>
        <p v-if="replayMessage" role="status">{{ replayMessage }}</p>
        <div v-if="replaySources.length" class="source-evidence" role="status"><strong>输入来源证据（声明待核验）</strong><span v-for="source in replaySources" :key="source.revisionId">版本 #{{ source.revisionId }} · 来源 #{{ source.sourceEvidenceId ?? "无" }} · 原文件第 {{ source.sourceRowNo ?? "无" }} 行 · {{ source.sourceName ?? "无来源登记" }} · {{ source.sourceSha256 ?? "无哈希" }}</span></div>
        <p v-if="result?.historyLatestDate && result.historyLatestDate < (result.targetDate ?? targetDate).slice(0, 10) && Date.parse(result.targetDate ?? targetDate) - Date.parse(result.historyLatestDate) > 14 * 86400000" class="error">历史台账距目标日已超过14天，请先补齐近期记录，再据此安排现场备餐。</p>
        <p class="form-help">建议依据历史经营记录计算；请核对当餐原料和客流后确认。闭餐后回填实际制作、售出与剩余，便于下次复盘。</p>
        <details class="form-help"><summary>查看建议依据</summary><ul><li v-for="factor in prediction.factors" :key="factor.name">{{ factor.name }}：{{ factor.detail }}</li></ul></details>
        <form class="decision-form" @submit.prevent="confirmDecision"><h4>确认本次执行计划</h4><label>使用方式<select v-model="decision.adopted"><option :value="true">采用建议（可调整数量）</option><option :value="false">自行制定计划</option></select></label><label>计划总备餐量（份）<input v-model.number="decision.adjustedQty" type="number" min="0" step="1" required></label><label>调整或未采用的原因<input v-model.trim="decision.reason" maxlength="300" placeholder="库存、产能或现场客流变化"></label><button class="btn primary" :disabled="decisionBusy || loading || planBusy || planChanged">{{ decisionBusy ? '保存中…' : '确认执行计划' }}</button><p v-if="decisionMessage" role="status">{{ decisionMessage }}</p></form>
        <div class="print-actions"><button class="btn" type="button" @click="printSheet">打印执行单</button><span>执行单含菜品与备餐信息，请按档口管理要求保管</span></div>
        <div class="print-sheet" aria-hidden="true">
          <h2>备餐执行单</h2>
          <p class="print-meta">{{ result?.targetDate ?? targetDate }} · {{ result?.mealPeriod ?? mealPeriod }} · {{ engineLabels[engine] ?? engine }}</p>
          <table>
            <tbody>
              <tr><th>菜品</th><td>{{ prediction.dishName }}</td><th>建议总量</th><td>{{ preview?.quantity ?? prediction.predictedMid }} 份</td></tr>
              <tr><th>首批制作</th><td>{{ preview?.firstBatch ?? prediction.firstBatch }} 份</td><th>视销售补餐</th><td>{{ preview?.replenish ?? prediction.replenishQty }} 份</td></tr>
              <tr><th>参考区间</th><td>[{{ preview?.intervalLow ?? prediction.predictedLow }}, {{ preview?.intervalHigh ?? prediction.predictedHigh }}] 份</td><th>停做时间</th><td>{{ String(prediction.stopHour).padStart(2, "0") }}:{{ String(prediction.stopMinute).padStart(2, "0") }}</td></tr>
            </tbody>
          </table>
          <p class="print-note">依据：{{ preview ? `临界比 ${preview.criticalRatio.toFixed(3)}，缺货损失 ${preview.underage} 元/份，剩余损失 ${preview.overage} 元/份` : "规则模型参考范围" }}。区间为统计参考，不是安全库存承诺。</p>
          <p class="print-sign">现场负责人签字：____________　实际备餐：______ 份　实际售出：______ 份　剩余：______ 份</p>
        </div>
        <RouterLink class="next-link" :to="{ path: '/app/operations/feedback', query: { predictionId: prediction.predictionId, dishId: prediction.dishId, businessDate: result?.targetDate, mealPeriod: result?.mealPeriod, plannedQty: prediction.predictedMid, adjustedQty: decision.adjustedQty, adopted: String(decision.adopted), reason: decision.reason } }">关联本次建议，回填经营结果 →</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prediction-grid{display:grid;grid-template-columns:minmax(300px,360px) minmax(0,1fr);gap:16px}.panel-head h3{font-size:18px;margin:6px 0 22px}.form-panel label{display:block;color:var(--fw-muted);font-size:13px;font-weight:600;margin:17px 0}.form-panel select{display:block;width:100%;margin-top:7px;padding:11px;border:1px solid #cbdfee;border-radius:7px;background:#fff;color:#274f73;font-size:14px}.form-panel select:focus-visible{outline:2px solid #28698f}.check{display:flex!important;gap:8px;align-items:center}.form-help{color:var(--fw-muted);font-size:12px;line-height:1.7;margin:15px 0}.btn{border:0;padding:12px 18px;border-radius:8px;font-weight:700;cursor:pointer;font-size:13px}.btn.primary{background:var(--fw-primary);color:#fff}.btn:disabled{opacity:.5;cursor:not-allowed}.empty{padding:50px 10px;text-align:center;color:#607d96;font-size:13px}.result-main{padding:20px;border-radius:10px;background:#edf4f8}.result-main span,.result-main strong,.result-main em{display:block}.result-main span{font-size:12px;color:#537997}.result-main strong{font:700 38px Manrope;color:var(--fw-primary);margin:10px 0}.result-main small{font-size:14px}.result-main em{font-size:12px;color:#4b7eaa;font-style:normal}.result-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.result-kpis div{padding:14px;background:#f7fafc;border-radius:8px}.result-kpis span,.result-kpis strong{display:block}.result-kpis span{font-size:12px;color:#59778f}.result-kpis strong{margin-top:8px;font-size:16px}.risk{display:flex;gap:10px;flex-wrap:wrap}.risk b{font-size:12px;color:#925d27;padding:8px 10px;background:#fff4e6;border-radius:6px}.result>p{font-size:13px;line-height:1.7;color:#59758f}.error{color:#b7433d;font-size:13px}.next-link{display:inline-block;margin-top:8px;font-size:13px;font-weight:700;color:var(--fw-primary)}@media(max-width:800px){.prediction-grid{grid-template-columns:1fr}.result-kpis{grid-template-columns:1fr 1fr}}.prediction-meta{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0;color:#55758e;font-size:11px}.prediction-meta span{padding:6px 8px;background:#f1f6f9;border-radius:6px}
</style>
<style scoped>
.decision-form{display:grid;gap:10px;margin-top:16px;padding:16px;background:#f7fafc;border-radius:8px}.decision-form h4{margin:0}.decision-form label{font-size:13px;color:#496a85}.decision-form input,.decision-form select{display:block;width:100%;box-sizing:border-box;padding:10px;margin-top:5px;border:1px solid #cbdfee;border-radius:6px;background:#fff}.decision-form p{font-size:13px;line-height:1.6;color:#496a85}
.dish-preview{display:flex;align-items:center;gap:10px;color:#5b7388;font-size:12px}.dish-preview img{width:88px;height:68px;object-fit:cover;border-radius:5px;background:#eef3f6}
.source-evidence{display:grid;gap:5px;margin:10px 0;padding:10px 12px;border:1px solid #e8d5ad;background:#fffaf0;color:#765b2a;font-size:11px;line-height:1.5}.source-evidence strong{font-size:12px}
.constraint-fields{border:1px solid #dbe8f2;border-radius:8px;padding:8px 12px 2px;margin:16px 0}.constraint-fields legend{padding:0 5px;color:var(--fw-muted);font-size:12px;font-weight:700}.constraint-fields label{margin:10px 0!important}.constraint-fields input{display:block;width:100%;box-sizing:border-box;margin-top:5px;padding:9px;border:1px solid #cbdfee;border-radius:6px;background:#fff;color:#274f73}.time-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.preparation-plan{margin:16px 0;padding:16px;border:1px solid #cbdfee;border-radius:9px;background:#fbfdff}.plan-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.plan-head h4{margin:6px 0 0;font-size:16px}.plan-state{font-size:11px;color:#52728b;background:#edf5fb;padding:6px 8px;border-radius:5px;white-space:nowrap}.plan-result{margin-top:14px}.plan-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.plan-kpis div{padding:10px;background:#f1f6f9;border-radius:6px}.plan-kpis span,.plan-kpis strong{display:block}.plan-kpis span{font-size:11px;color:#5b7890}.plan-kpis strong{margin-top:5px;font-size:16px;color:var(--fw-primary)}.plan-result ul{margin:10px 0;padding-left:18px;color:#765b2a;font-size:12px;line-height:1.7}.plan-actions{display:flex;justify-content:space-between;align-items:center;gap:10px;color:var(--fw-muted);font-size:11px;margin-top:12px}.plan-actions .btn{padding:8px 10px;font-size:11px}
@media(max-width:800px){.time-grid,.plan-kpis{grid-template-columns:1fr 1fr}.plan-head,.plan-actions{display:grid;justify-content:stretch}.plan-state{width:max-content}}
</style>
<style scoped>
.prediction-grid{grid-template-columns:minmax(285px,330px) minmax(0,1fr);align-items:start;gap:18px}.prediction-grid>.panel{border-color:#dbe5eb}.form-panel{background:#fff}.form-panel .panel-head h3{margin-bottom:13px}.dish-preview{padding:7px;background:#f3f7fa;border-radius:6px}.dish-preview img{width:124px;height:90px}.dish-preview span{display:grid;gap:5px}.dish-preview strong{font-size:14px;color:#294b63}.result-panel{min-height:380px}.result-panel>.panel-head h3{margin-bottom:14px}.empty{min-height:260px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;background:repeating-linear-gradient(0deg,#f8fafc 0,#f8fafc 32px,#eff4f7 33px);border:1px dashed #cfdfd3;border-radius:6px}.empty strong{font-size:18px;color:#294b63}.empty span{max-width:250px;line-height:1.6}.result-main{background:var(--fw-tint);border-left:4px solid #28698f;border-radius:4px;padding:18px 20px}.result-main strong{color:var(--fw-primary);margin:5px 0}.result-main em{color:#627d8d}.result-kpis{border-bottom:1px solid #dbe5eb;padding-bottom:14px}.result-kpis div{background:transparent;padding:4px 12px;border-left:1px solid #dbe5eb;border-radius:0}.result-kpis div:first-child{border:0;padding-left:0}.result-kpis strong{color:#294b63}.batch-visual{margin:12px 0 16px}.batch-head,.batch-labels{display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:12px;color:#657c8a}.batch-head strong{font-size:13px;color:#294b63}.batch-track{display:flex;height:20px;margin:9px 0;border-radius:3px;overflow:hidden;background:#ecf1ec}.batch-first{background:#3b84ad}.batch-replenish{background:#ddab68}.batch-labels{justify-content:flex-start;gap:20px}.batch-labels i{display:inline-block;width:8px;height:8px;margin-right:5px;background:#3b84ad;border-radius:2px}.batch-labels span:nth-child(2) i{background:#ddab68}.prediction-evidence{padding:11px 0;border-top:1px solid #e4ebe4;border-bottom:1px solid #e4ebe4;margin:15px 0;color:#5b7688;font-size:12px}.prediction-evidence summary{cursor:pointer;font-weight:700}.prediction-meta span{background:#f0f5f1;color:#607a8c}.preparation-plan{padding:16px 0;border:0;border-top:1px solid #dbe5eb;border-radius:0;background:transparent}.decision-form{border-top:1px solid #dbe5eb;background:transparent;border-radius:0;padding:17px 0}.constraint-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 12px;border-color:#dbe5eb}.constraint-fields .time-grid{grid-column:1/-1}@media(max-width:800px){.prediction-grid{grid-template-columns:1fr}}@media(max-width:520px){.constraint-fields{grid-template-columns:1fr}.batch-labels{flex-wrap:wrap}}
</style>


<style scoped>
.calculation-details{margin-top:10px;padding-top:10px;border-top:1px dashed #dbe7ea;color:#4f6873;font-size:12px}.calculation-details summary{cursor:pointer;font-weight:700;color:var(--fw-primary)}.calculation-details dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin:9px 0 0}.calculation-details dl div{padding:7px 8px;background:#f7fafb;border-radius:5px}.calculation-details dt{font-size:11px;color:var(--fw-muted)}.calculation-details dd{margin:3px 0 0;line-height:1.5}@media(max-width:640px){.calculation-details dl{grid-template-columns:1fr}}
.decision-card{margin:16px 0;padding:14px 16px;border:1px solid var(--fw-border);border-radius:8px;background:linear-gradient(180deg,#f7fbfc,#ffffff)}
.dc-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}
.dc-head h4{margin:2px 0 0;font-size:15px;color:var(--fw-ink)}
.dc-engine{font-size:11px;font-weight:700;color:var(--fw-primary-strong);background:var(--fw-tint);border-radius:999px;padding:3px 10px;white-space:nowrap}
.band-track{position:relative;height:26px;background:#eef4f6;border-radius:4px;overflow:hidden}
.band-range{position:absolute;top:0;bottom:0;background:rgba(75,140,146,.28);border-left:1px solid #4b8c92;border-right:1px solid #4b8c92}
.band-point{position:absolute;top:-2px;bottom:-2px;width:3px;margin-left:-1.5px;background:var(--fw-primary);border-radius:2px}
.band-labels{display:flex;justify-content:space-between;margin-top:5px;font-size:11.5px;color:var(--fw-muted)}
.band-labels span:nth-child(2){font-weight:700;color:var(--fw-primary-strong)}
.dc-cost{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0 8px}
.dc-cost div{background:#fff;border:1px solid #e3ecef;border-radius:6px;padding:8px 10px}
.dc-cost dt{font-size:11px;color:var(--fw-muted);margin-bottom:3px}
.dc-cost dd{margin:0;font-size:13.5px;font-weight:700;color:var(--fw-ink)}
.dc-formula,.dc-notes{margin:6px 0 0;font-size:12px;line-height:1.7;color:#4f6873}
.dc-cost dd small{display:block;font-weight:400;font-size:10.5px;color:var(--fw-muted)}
.dc-trial{display:flex;flex-wrap:wrap;align-items:end;gap:8px;margin-top:10px;padding-top:10px;border-top:1px dashed #dbe7ea}
.dc-trial label{display:flex;flex-direction:column;font-size:11px;color:var(--fw-muted);gap:3px}
.dc-trial input{width:78px;padding:5px 7px;border:1px solid var(--fw-border);border-radius:5px;font-size:12.5px}
.dc-trial button{padding:6px 12px;border:1px solid var(--fw-accent);background:var(--fw-accent);color:#fff;border-radius:5px;font-size:12px;cursor:pointer}
.dc-trial button.ghost{background:#fff;color:var(--fw-ink);border-color:var(--fw-border)}
.dc-trial small{flex-basis:100%;font-size:11px;color:var(--fw-muted)}
.dc-notes{color:#8a5a12}
.print-actions{display:flex;align-items:center;gap:10px;margin:10px 0;flex-wrap:wrap}
.print-actions span{font-size:12px;color:var(--fw-muted)}
@media(max-width:640px){ .dc-cost{grid-template-columns:repeat(2,minmax(0,1fr))} }
.assistant{margin:16px 0;padding:14px 16px;border:1px solid var(--fw-border);border-radius:8px;background:#fbfdfe}
.assistant-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}
.assistant-head h4{margin:2px 0 0;font-size:15px;color:var(--fw-ink)}
.assistant-tag{font-size:11px;font-weight:700;color:#2f6d4f;background:#eaf6ee;border-radius:999px;padding:3px 10px;white-space:nowrap}
.assistant-presets{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.assistant-chip{border:1px solid #cfdfe4;background:#fff;color:#2f5a70;border-radius:999px;padding:6px 12px;font-size:12px;cursor:pointer}
.assistant-chip:hover:not(:disabled){border-color:var(--fw-primary);color:var(--fw-primary-strong)}
.assistant-chip:disabled{opacity:.5;cursor:not-allowed}
.assistant-ask{display:flex;gap:8px;margin-bottom:10px}
.assistant-ask input{flex:1;min-width:0;padding:9px 11px;border:1px solid #cbdfee;border-radius:6px;background:#fff}
.assistant-answer{padding:12px 14px;border-left:3px solid var(--fw-primary);background:#f2f8fa;border-radius:4px}
.assistant-text{margin:0 0 8px;font-size:13px;line-height:1.75;color:#26485c}
.assistant-action{margin:0 0 6px;font-size:12.5px;font-weight:700;color:var(--fw-primary-strong)}
.assistant-refusal{margin:0 0 6px;font-size:12px;color:#8a5a12}
.assistant-refusal code{background:#fff4e6;border-radius:4px;padding:1px 5px}
.assistant-cites{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:3px;font-size:11.5px;color:#5c7484}
.assistant-cites b{color:#2f6d4f;font-weight:700;margin-right:6px}
.assistant-note{margin:10px 0 0;font-size:11.5px;line-height:1.6;color:var(--fw-muted)}
</style>
