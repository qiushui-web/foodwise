<script setup lang="ts">
import PageHeader from "../components/PageHeader.vue";
import { formatNumber } from "../utils/format";
import { getApi } from "../utils/vue-api";
import { computed, onMounted, ref } from "vue";

type MethodRow = { picp: number; pinaw: number; winkler: number; n: number; alpha: number };
type DecisionMethodRow = {
  regret: number; loss_per_100: number; stockout_rate: number; leftover_rate: number; mean_prepared: number;
};
type Evidence = {
  engines: string[];
  loadError: string | null;
  manifest: {
    model_version: string; model_kind: string; schema_version: string;
    calibration?: { method?: string; alpha?: number; picp90?: number; artifact_sha256?: string };
    metrics?: { picp90?: number; pinaw90?: number; winkler90?: number; evaluated_on?: string };
    limits?: string[];
  };
  intervalExperiment: {
    dataset: string; label_note: string; rows: number;
    split: { train_rows: number; calib_rows: number; test_rows: number };
    alpha: number; methods: Record<string, MethodRow>; limits: string[];
  };
  decisionExperiment: {
    assumptions: Record<string, number>;
    base_scenario: { mean_critical_ratio: number; methods: Record<string, DecisionMethodRow> };
    scenarios: { salvage_probability: number; mean_critical_ratio: number; methods: Record<string, DecisionMethodRow> }[];
    limits: string[];
  };
  attributionExperiment?: Attribution;
};
type AttributionSummary = { mean_estimate: number; bias: number; rmse: number; coverage95: number; power: number };
type Attribution = {
  protocol: string; reps: number; alpha: number;
  methods: Record<string, string>;
  recovery: Record<string, { truth: number; its: AttributionSummary; bsts: AttributionSummary }>;
  placebo: { its_false_positive_rate: number; bsts_false_positive_rate: number; reps: number };
  real_ledger: {
    days: string[]; leftover_rate_pct: number[]; verdict: string; warning: string;
    min_detectable_effect_pp: number; required_days_for_5pp: number | null; residual_sd_pp: number;
    negative_control_fit: { effect: number; ci_low: number; ci_high: number; p_value: number };
  };
  limits: string[];
};
type DecisionRow = {
  id: number; dishId: number; targetDate: string; engine: string; modelVersion: string;
  q05: number; q95: number; intervalLow: number; intervalHigh: number;
  criticalRatio: number; quantity: number; firstBatch: number; replenish: number; createdAt: string;
};
type ReplayReport = {
  recordId: number; recordedQuantity: number; replayedQuantity: number; match: boolean; drift: boolean; notes: string[];
};
type Contract = {
  answerable: { intent: string; description: string }[];
  refusals: { code: string; reason: string; examples: string[]; count: number }[];
  citations: { type: string; meaning: string }[];
  eval: {
    cases: number; refused: number; answerable: number;
    by_category: { key: string; label: string; count: number }[];
    resource: string;
  };
  rules: string[];
};

const evidence = ref<Evidence | null>(null);
const contract = ref<Contract | null>(null);
const decisions = ref<DecisionRow[]>([]);
const replay = ref<Record<number, ReplayReport>>({});
const busyReplay = ref<number | null>(null);
const error = ref("");

const methodLabels: Record<string, string> = {
  quantile_raw: "原始分位（未校准）",
  cqr_global: "CQR 全局偏移",
  cqr_stratified: "CQR + 分层收缩（部署）",
  cqr_aci: "CQR + ACI（一次性）",
  cqr_rolling: "滚动重校准",
  cqr_rolling_aci: "滚动 + ACI",
  cqr_sliding: "滑动窗口校准",
};
const decisionLabels: Record<string, string> = {
  rule_10pct: "固定安全系数 +10%（现状）",
  newsvendor_raw: "报童 + 未校准 σ",
  newsvendor_calibrated: "报童 + 校准 σ（部署）",
  newsvendor_batch: "报童 + 校准 + 批量约束",
};

async function load() {
  error.value = "";
  try {
    evidence.value = await getApi<Evidence>("/model/evidence");
    decisions.value = await getApi<DecisionRow[]>("/decisions/recent?limit=8");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "详细数据暂时无法加载，请稍后重试";
  }
  try {
    // 契约单独取：参谋不可用时不该拖垮整页证据
    contract.value = await getApi<Contract>("/assistant/contract");
  } catch {
    contract.value = null;
  }
}
async function runReplay(row: DecisionRow) {
  busyReplay.value = row.id;
  try {
    replay.value = { ...replay.value, [row.id]: await getApi<ReplayReport>(`/decisions/${row.id}/replay`) };
  } catch (e) {
    error.value = e instanceof Error ? e.message : "重放失败";
  } finally { busyReplay.value = null; }
}
function percent(value: number | undefined | null) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}
function localTime(value?: string) {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
}
const limits = computed(() => {
  const source = evidence.value;
  if (!source) return [];
  return Array.from(new Set([
    ...(source.intervalExperiment.limits ?? []),
    ...(source.decisionExperiment.limits ?? []),
    ...(source.manifest.limits ?? []),
    ...(source.attributionExperiment?.limits ?? []),
  ]));
});
onMounted(load);
</script>

<template>
  <PageHeader
    eyebrow="服务说明"
    title="数据说明"
    description="了解页面数字从哪里来、备餐建议如何使用，以及哪些结果还需要现场核实。"
  />

  <section class="panel usage-summary"><h3>先了解这三件事</h3><dl><div><dt>页面数字从哪里来？</dt><dd>来自已录入或导入的经营记录。演示环境使用项目测算资料，请先核对营业日期和菜品。</dd></div><div><dt>备餐建议能直接照做吗？</dt><dd>建议用于辅助判断。制作前仍需确认当餐库存、产能、天气与现场情况，由负责人确定数量。</dd></div><div><dt>是否已经验证减损效果？</dt><dd>目前完成的是本地流程和公开数据实验，尚未验证校园现场减损、实际预测精度或经营收益。</dd></div></dl></section>
  <details class="professional-details"><summary>查看方法与验证详情 <span>供需要进一步核对数据的人员查阅</span></summary>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="evidence?.loadError" class="error" role="alert">模型产物加载异常：{{ evidence.loadError }}</p>

  <template v-if="evidence">
    <section class="evidence-strip" aria-label="模型与校准概要">
      <article class="evidence-card">
        <span class="kicker">模型版本</span>
        <strong>{{ evidence.manifest.model_version }}</strong>
        <small>{{ evidence.manifest.model_kind }} · schema v{{ evidence.manifest.schema_version }}</small>
      </article>
      <article class="evidence-card">
        <span class="kicker">校准方法</span>
        <strong>{{ evidence.manifest.calibration?.method ?? "未登记" }}</strong>
        <small>α = {{ evidence.manifest.calibration?.alpha ?? "—" }}，产物哈希 {{ (evidence.manifest.calibration?.artifact_sha256 ?? "").slice(0, 12) }}…</small>
      </article>
      <article class="evidence-card">
        <span class="kicker">测试集覆盖率 PICP90</span>
        <strong>{{ percent(evidence.manifest.metrics?.picp90) }}</strong>
        <small>目标 90% · 区间宽度 {{ formatNumber(evidence.manifest.metrics?.pinaw90, 3) }} 份 · Winkler {{ formatNumber(evidence.manifest.metrics?.winkler90, 2) }}</small>
      </article>
      <article class="evidence-card">
        <span class="kicker">在线引擎</span>
        <strong>{{ evidence.engines.join(" / ") }}</strong>
        <small>四个引擎：规则、未校准分位、校准分位共用一套分位模型，稳健基线（部署默认）另算</small>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="kicker">实验一 · 区间质量</span>
        <h3>七种区间方法在同一测试集上的表现</h3>
        <p class="source-note">
          {{ evidence.intervalExperiment.dataset }}，{{ evidence.intervalExperiment.rows }} 行；
          训练 {{ evidence.intervalExperiment.split.train_rows }} / 校准 {{ evidence.intervalExperiment.split.calib_rows }} / 测试 {{ evidence.intervalExperiment.split.test_rows }}；
          α = {{ evidence.intervalExperiment.alpha }}。{{ evidence.intervalExperiment.label_note }}
        </p>
      </div>
      <div class="table-scroll">
        <table>
          <caption class="sr-only">七种区间方法的覆盖率、区间宽度与 Winkler 分数</caption>
          <thead>
            <tr><th scope="col">方法</th><th scope="col">覆盖率 PICP90</th><th scope="col">宽度 PINAW90</th><th scope="col">Winkler90</th><th scope="col">样本</th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, key) in evidence.intervalExperiment.methods" :key="key" :class="{ deployed: key === 'cqr_stratified' }">
              <th scope="row">{{ methodLabels[key] ?? key }}<span v-if="key === 'cqr_stratified'" class="tag">部署</span></th>
              <td>
                <span class="bar" :style="{ width: `${Math.min(100, row.picp * 100)}%` }" aria-hidden="true"></span>
                <b>{{ percent(row.picp) }}</b>
              </td>
              <td>{{ formatNumber(row.pinaw, 3) }}</td>
              <td>{{ formatNumber(row.winkler, 2) }}</td>
              <td>{{ row.n }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="reading">
        读法：未校准区间只覆盖 57.7%，等于“十次里有四次把真实销量挡在门外”；CQR 校准后覆盖率回到 96.7%，
        代价是区间变宽（0.128 → 0.284 份/百份）。<b>更宽的区间不是退步，而是把不确定性说清楚。</b>
      </p>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="kicker">实验二 · 决策成本</span>
        <h3>不同备餐策略的成本对比（实验场景）</h3>
        <p class="source-note">
          基准场景临界比 {{ formatNumber(evidence.decisionExperiment.base_scenario.mean_critical_ratio, 3) }}；
          成本假设：折价比例 {{ evidence.decisionExperiment.assumptions.discount_ratio }}、剩余可售概率
          {{ evidence.decisionExperiment.assumptions.salvage_probability }}、缺货信任损失系数 {{ evidence.decisionExperiment.assumptions.shortage_lambda }}。
        </p>
      </div>
      <div class="table-scroll">
        <table>
          <caption class="sr-only">四种备餐策略的 regret 与每百份损失</caption>
          <thead>
            <tr><th scope="col">策略</th><th scope="col">regret</th><th scope="col">每百份损失（元）</th><th scope="col">缺货率</th><th scope="col">剩余率</th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, key) in evidence.decisionExperiment.base_scenario.methods" :key="key" :class="{ deployed: key === 'newsvendor_calibrated' }">
              <th scope="row">{{ decisionLabels[key] ?? key }}<span v-if="key === 'newsvendor_calibrated'" class="tag">部署</span></th>
              <td><b>{{ percent(row.regret) }}</b></td>
              <td>{{ formatNumber(row.loss_per_100, 2) }}</td>
              <td>{{ percent(row.stockout_rate) }}</td>
              <td>{{ percent(row.leftover_rate) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="table-scroll">
        <table class="compact">
          <caption>成本结构变化时，固定安全系数会失效（regret）</caption>
          <thead>
            <tr><th scope="col">临界比</th><th scope="col">固定 +10%</th><th scope="col">报童 + 校准</th><th scope="col">差值</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in evidence.decisionExperiment.scenarios" :key="row.salvage_probability">
              <th scope="row">{{ formatNumber(row.mean_critical_ratio, 3) }}</th>
              <td>{{ percent(row.methods.rule_10pct.regret) }}</td>
              <td>{{ percent(row.methods.newsvendor_calibrated.regret) }}</td>
              <td :class="{ gain: row.methods.rule_10pct.regret > row.methods.newsvendor_calibrated.regret }">
                {{ percent(row.methods.rule_10pct.regret - row.methods.newsvendor_calibrated.regret) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="kicker">实验三 · 运行时可重放</span>
        <h3>最近的决策记录，可以当场重算</h3>
        <p class="source-note">重放会用留存的 24 维输入与当前模型产物重新计算建议量，并比对是否一致。不一致意味着产物被替换或输入被改写。</p>
      </div>
      <p v-if="!decisions.length" class="empty">还没有决策记录。到“备餐计划”生成一次，这里就会出现可重放的记录。</p>
      <ul v-else class="decision-list">
        <li v-for="row in decisions" :key="row.id">
          <div class="decision-main">
            <strong>#{{ row.id }} · 菜品 {{ row.dishId }}</strong>
            <span>{{ localTime(row.createdAt) }} · {{ row.engine }} · {{ row.modelVersion }}</span>
          </div>
          <div class="decision-numbers">
            <span>区间 [{{ row.intervalLow }}, {{ row.intervalHigh }}]</span>
            <span>临界比 {{ formatNumber(row.criticalRatio, 3) }}</span>
            <span>建议 {{ row.quantity }} 份（首锅 {{ row.firstBatch }} / 补餐 {{ row.replenish }}）</span>
          </div>
          <button class="btn secondary" :disabled="busyReplay === row.id" @click="runReplay(row)">
            {{ busyReplay === row.id ? "重放中…" : "重放核对" }}
          </button>
          <p v-if="replay[row.id]" class="replay-result" aria-live="polite" :class="{ ok: replay[row.id].match, bad: !replay[row.id].match }">
            {{ replay[row.id].match
              ? `一致：记录 ${replay[row.id].recordedQuantity} 份，重算 ${replay[row.id].replayedQuantity} 份。`
              : `不一致：记录 ${replay[row.id].recordedQuantity} 份，重算 ${replay[row.id].replayedQuantity} 份，需排查产物漂移。` }}
          </p>
        </li>
      </ul>
    </section>

    <section v-if="evidence.attributionExperiment" class="panel">
      <div class="panel-head">
        <span class="kicker">实验四 · 归因与负对照</span>
        <h3>“减损有效果”这句话，需要多强的证据才敢说</h3>
        <p class="source-note">
          {{ evidence.attributionExperiment.reps }} 次合成周日序列恢复实验，已知效应 0 / −5 / −10 个百分点：
          ITS（分段回归 + Newey-West）与轻量 BSTS（局部水平 + 星期效应）。真值未知的方法先要证明“能估回来”。
        </p>
      </div>
      <div class="table-scroll">
        <table>
          <caption class="sr-only">恢复实验：两种归因方法的偏差、区间覆盖率与功效</caption>
          <thead>
            <tr><th scope="col">真实效应</th><th scope="col">方法</th><th scope="col">平均估计</th><th scope="col">偏差（pp）</th><th scope="col">RMSE（pp）</th><th scope="col">95% 覆盖率</th><th scope="col">功效</th></tr>
          </thead>
          <tbody>
            <template v-for="(row, key) in evidence.attributionExperiment.recovery" :key="key">
              <tr :class="{ deployed: key === 'effect_-5pct' }">
                <th scope="row" :rowspan="2">{{ row.truth }} pp</th>
                <td>ITS + HAC</td>
                <td>{{ formatNumber(row.its.mean_estimate, 2) }}</td>
                <td>{{ formatNumber(row.its.bias, 2) }}</td>
                <td>{{ formatNumber(row.its.rmse, 2) }}</td>
                <td>{{ percent(row.its.coverage95) }}</td>
                <td>{{ percent(row.its.power) }}</td>
              </tr>
              <tr :class="{ deployed: key === 'effect_-5pct' }">
                <td>轻量 BSTS</td>
                <td>{{ formatNumber(row.bsts.mean_estimate, 2) }}</td>
                <td>{{ formatNumber(row.bsts.bias, 2) }}</td>
                <td>{{ formatNumber(row.bsts.rmse, 2) }}</td>
                <td>{{ percent(row.bsts.coverage95) }}</td>
                <td>{{ percent(row.bsts.power) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <p class="reading">
        读法：ITS 在 −5pp 上的平均偏差 {{ formatNumber(evidence.attributionExperiment.recovery["effect_-5pct"]?.its.bias, 2) }} pp，
        区间覆盖率 {{ percent(evidence.attributionExperiment.recovery["effect_-5pct"]?.its.coverage95) }}；
        BSTS 区间偏窄，覆盖率只有 {{ percent(evidence.attributionExperiment.recovery["effect_-5pct"]?.bsts.coverage95) }}，
        所以<b>主方法用 ITS，BSTS 只作敏感性对照</b>。真值为 0 时的假阳性率：ITS
        {{ percent(evidence.attributionExperiment.placebo.its_false_positive_rate) }} / BSTS
        {{ percent(evidence.attributionExperiment.placebo.bsts_false_positive_rate) }}。
      </p>
      <div class="negative-control">
        <h4>负对照：把第 8 天当分界点，会“测出”一个不存在的效果</h4>
        <p>
          真实台账 {{ evidence.attributionExperiment.real_ledger.days.length }} 个营业日、期间<b>没有上线任何干预</b>。
          但按第 8 天分段做 ITS，会得到
          {{ formatNumber(evidence.attributionExperiment.real_ledger.negative_control_fit.effect, 2) }} pp
          （95% 区间 {{ formatNumber(evidence.attributionExperiment.real_ledger.negative_control_fit.ci_low, 2) }} ~
          {{ formatNumber(evidence.attributionExperiment.real_ledger.negative_control_fit.ci_high, 2) }}）的“显著”下降。
          真实原因是 7 月中旬起剩余率本身在下降，分段回归把趋势读成了干预。
        </p>
        <p class="verdict">
          <strong>结论：不可识别。</strong>
          现有数据噪声 {{ formatNumber(evidence.attributionExperiment.real_ledger.residual_sd_pp, 2) }} pp，
          能识别的效果下限约 {{ formatNumber(evidence.attributionExperiment.real_ledger.min_detectable_effect_pp, 1) }} pp；
          要识别 5pp 级效果，至少需要
          {{ evidence.attributionExperiment.real_ledger.required_days_for_5pp ?? "—" }} 个营业日。
          站内因此不做任何减损成效声明。
        </p>
      </div>
    </section>

    <section v-if="contract" class="panel assistant-contract" aria-labelledby="assistant-contract-title">
      <div class="panel-head">
        <span class="kicker">实验五 · 智能体与边界</span>
        <h3 id="assistant-contract-title">参谋能问什么、什么会被挡回去</h3>
        <p class="source-note">
          {{ contract.eval.cases }} 条评测集里 {{ contract.eval.answerable }} 条给答案、{{ contract.eval.refused }} 条必须拒绝；
          条数直接读自 <code>{{ contract.eval.resource }}</code>，与本页同源，不在这里手写。
        </p>
      </div>
      <ul class="contract-stats">
        <li v-for="row in contract.eval.by_category" :key="row.key">
          <strong>{{ row.count }}</strong><span>{{ row.label }}</span>
        </li>
      </ul>
      <div class="table-wrap">
        <table>
          <thead><tr><th>拒绝码</th><th>为什么拒</th><th>评测集里的真实问法</th><th>条数</th></tr></thead>
          <tbody>
            <tr v-for="row in contract.refusals" :key="row.code">
              <td><code>{{ row.code }}</code></td>
              <td>{{ row.reason }}</td>
              <td class="examples">
                <span v-for="example in row.examples" :key="example">「{{ example }}」</span>
              </td>
              <td>{{ row.count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="contract-grid">
        <div>
          <h4>回答里的数字从哪来</h4>
          <ul>
            <li v-for="item in contract.citations" :key="item.type">
              <code>{{ item.type }}</code>：{{ item.meaning }}
            </li>
          </ul>
        </div>
        <div>
          <h4>两条硬规则</h4>
          <ul>
            <li v-for="rule in contract.rules" :key="rule">{{ rule }}</li>
          </ul>
        </div>
      </div>
      <p class="source-note">
        评测不通过就是构建失败：意图、拒绝码、引用条数（≥2）、答案禁语、拒绝文案不含数字，逐条断言。
        这不是"能返回"的演示，而是"边界改塌了会被发现"的验收。
      </p>
    </section>

    <section class="panel limits">
      <div class="panel-head"><span class="kicker">必须说清楚</span><h3>这些结论的边界</h3></div>
      <ul>
        <li v-for="line in limits" :key="line">{{ line }}</li>
      </ul>
      <p class="source-note">成本参数为情景假设，未经食堂财务数据校准；需求为派生目标，regret 只反映策略相对排序。</p>
    </section>

    <section class="panel">
      <div class="panel-head"><span class="kicker">复现</span><h3>从零复现以上数字</h3></div>
      <pre class="commands"><code>cd 项目代码
modeling/.venv/Scripts/python.exe modeling/scripts/32_fit_intervals.py
modeling/.venv/Scripts/python.exe modeling/scripts/33_decision_backtest.py
modeling/.venv/Scripts/python.exe modeling/scripts/34_attribute.py --reps 120
modeling/.venv/Scripts/python.exe modeling/scripts/30_verify_manifest.py
modeling/.venv/Scripts/python.exe -m unittest discover -s modeling/tests
./gradlew.bat test</code></pre>
      <p class="source-note">32 会重写分位模型、校准产物与测试对照样本；34 会重跑归因恢复实验（约 2 分钟）；30 校验清单契约与哈希绑定；任何一步失败都会直接非零退出。</p>
    </section>
  </template>
  </details>
</template>

<style scoped>
.evidence-strip { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; margin-bottom:18px; }
.evidence-card { background:var(--fw-surface); border:1px solid var(--fw-border); border-radius:var(--fw-radius); padding:16px 18px; display:flex; flex-direction:column; gap:6px; min-width:0; }
.evidence-card strong { font-size:20px; color:var(--fw-ink); line-height:1.3; overflow-wrap:anywhere; }
.evidence-card small { color:var(--fw-muted); font-size:12px; line-height:1.5; }
.panel { margin-bottom:18px; }
.panel-head { display:block; }
.panel-head h3 { margin:2px 0 6px; }
.panel-head .source-note { display:block; margin:0; max-width:920px; line-height:1.7; }
.table-scroll { overflow-x:auto; }
table { width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }
caption { text-align:left; color:var(--fw-muted); font-size:12px; padding-bottom:6px; }
th, td { padding:9px 10px; border-bottom:1px solid #e5ecee; text-align:left; vertical-align:middle; }
thead th { background:#edf3f5; color:#526a76; font-weight:600; white-space:nowrap; }
tbody th { font-weight:600; color:var(--fw-ink); }
tr.deployed { background:#f2f8f9; }
.tag { display:inline-block; margin-left:8px; padding:1px 7px; border-radius:999px; background:var(--fw-primary); color:#fff; font-size:11px; font-weight:600; vertical-align:middle; }
.bar { display:block; height:5px; background:var(--fw-accent); border-radius:3px; margin-bottom:5px; opacity:.55; }
td b { color:var(--fw-ink); }
.compact { margin-top:16px; }
.gain { color:#1f6b57; font-weight:700; }
.reading { margin:12px 0 0; padding:12px 14px; background:var(--fw-tint); border-radius:6px; color:#37525f; font-size:13px; line-height:1.7; }
.decision-list { list-style:none; margin:14px 0 0; padding:0; display:grid; gap:10px; }
.decision-list li { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,1.6fr) auto; gap:12px; align-items:center; padding:12px 14px; border:1px solid var(--fw-border); border-radius:6px; }
.decision-main strong { display:block; font-size:14px; }
.decision-main span { color:var(--fw-muted); font-size:12px; }
.decision-numbers { display:flex; flex-wrap:wrap; gap:6px 16px; color:#3f5a67; font-size:13px; }
.replay-result { grid-column:1 / -1; margin:0; font-size:13px; }
.replay-result.ok { color:#1f6b57; }
.replay-result.bad { color:#a33b25; }
.limits ul { margin:10px 0 0; padding-left:20px; color:#435b67; font-size:13px; line-height:1.8; }
.commands { background:#1f333d; color:#e8f1f3; padding:16px 18px; border-radius:6px; overflow-x:auto; font-size:12.5px; line-height:1.85; margin:10px 0 8px; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0; }
.empty { color:var(--fw-muted); font-size:13px; margin:12px 0 0; }
@media(max-width:1080px){ .evidence-strip{grid-template-columns:repeat(2,minmax(0,1fr))} }
@media(max-width:720px){
  .evidence-strip{grid-template-columns:1fr}
  .decision-list li{grid-template-columns:1fr;gap:8px}
  .decision-list li .btn{justify-self:start}
  th,td{padding:8px 8px;font-size:12.5px}
}.negative-control{margin-top:14px;padding:14px 16px;border:1px solid #e5d6c6;border-left:3px solid #c08a4a;border-radius:6px;background:#fdf8f1}
.negative-control h4{margin:0 0 8px;font-size:14px;color:#7d5321}
.negative-control p{margin:0 0 8px;font-size:13px;line-height:1.75;color:#5c4a33}
.negative-control .verdict{margin:0;padding-top:8px;border-top:1px dashed #e2cdb4;color:#3f3220}
.negative-control .verdict strong{color:#a33b25}
.contract-stats{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;margin:12px 0 14px;padding:0;list-style:none}
.contract-stats li{background:#f7fbfc;border:1px solid #e3ecef;border-radius:6px;padding:8px 10px;text-align:center}
.contract-stats strong{display:block;font-size:18px;color:var(--fw-ink);line-height:1.2}
.contract-stats span{display:block;margin-top:3px;font-size:11px;color:var(--fw-muted);line-height:1.4}
.assistant-contract td.examples{font-size:12px;color:#4f6873;line-height:1.9;text-align:left}
.assistant-contract td.examples span{display:block}
.contract-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}
.contract-grid h4{margin:0 0 6px;font-size:13.5px;color:var(--fw-ink)}
.contract-grid ul{margin:0;padding-left:18px;font-size:12.5px;line-height:1.85;color:#435b67}
.contract-grid code{font-size:12px;background:#eef4f6;border-radius:3px;padding:1px 5px}
@media(max-width:900px){.contract-stats{grid-template-columns:repeat(3,minmax(0,1fr))}.contract-grid{grid-template-columns:1fr}}
</style>
<style scoped>
.usage-summary h3{margin:0 0 8px;font-size:19px}.usage-summary dl{margin:0}.usage-summary dl>div{padding:18px 0;border-top:1px solid var(--fw-border)}.usage-summary dl>div:first-child{border-top:0}.usage-summary dt{font-size:15px;font-weight:700;color:var(--fw-ink)}.usage-summary dd{margin:8px 0 0;color:var(--fw-muted);font-size:14px;line-height:1.85;max-width:860px}.professional-details>summary{padding:18px 20px;background:white;border:1px solid var(--fw-border);border-radius:12px;cursor:pointer;color:var(--fw-primary);font-size:14px;font-weight:700;margin-bottom:20px}.professional-details>summary span{display:inline-block;margin-left:14px;font-size:12px;font-weight:400;color:var(--fw-muted)}
</style>
