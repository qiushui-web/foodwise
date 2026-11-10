<script setup lang="ts">
import DataPanel from "../components/DataPanel.vue";
import MetricCard from "../components/MetricCard.vue";
import AsyncState from "../components/AsyncState.vue";
import PageHeader from "../components/PageHeader.vue";
import type { ExperimentReport, OperatingReport, PredictionReview } from "../api/types";
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getApi } from "../utils/vue-api";

const report = ref<OperatingReport>({});
const backtest = ref<ExperimentReport>({ available: false });
const reviews = ref<PredictionReview[]>([]);
type Attribution = {
  real_ledger: {
    verdict: string; min_detectable_effect_pp: number; required_days_for_5pp: number | null;
    residual_sd_pp: number; warning: string;
    negative_control_fit: { effect: number; ci_low: number; ci_high: number };
  };
  recovery: Record<string, { its: { coverage95: number; bias: number }; bsts: { coverage95: number } }>;
  placebo: { its_false_positive_rate: number };
};
const attribution = ref<Attribution | null>(null);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [report.value, backtest.value, reviews.value] = await Promise.all([
      getApi<OperatingReport>("/reports"),
      getApi<ExperimentReport>("/analytics/backtest"),
      getApi<PredictionReview[]>("/predictions/reviews"),
    ]);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "报告加载失败";
  } finally {
    loading.value = false;
  }
  try {
    const evidence = await getApi<{ attributionExperiment?: Attribution }>("/model/evidence");
    attribution.value = evidence.attributionExperiment ?? null;
  } catch { attribution.value = null; }
}
onMounted(load);
const pick = (key: string) => report.value?.summary?.[key] ?? "—";
const rate = (key: string) => {
  const raw = report.value?.summary?.[key];
  if (raw === null || raw === undefined || raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
};
const rateScale = computed(() => Math.min(100, Math.ceil(Math.max(10, rate("baseline_leftover_rate") ?? 0, rate("intervention_leftover_rate") ?? 0) / 5) * 5));
const rateWidth = (key: string) => `${((rate(key) ?? 0) / rateScale.value) * 100}%`;
const rateGap = computed(() => {
  const baseline = rate("baseline_leftover_rate");
  const intervention = rate("intervention_leftover_rate");
  return baseline === null || intervention === null ? null : Math.abs(baseline - intervention).toFixed(1);
});
// 预测 → 确认计划 → 实际制作 → 实际售出：把差额拆成三段，说明“差在哪一步”
const decomposition = computed(() => {
  const rows = reviews.value.filter((row) => typeof row.predicted_mid === "number" && typeof row.sold_qty === "number");
  if (!rows.length) return null;
  const mean = (values: number[]) => values.reduce((sum, v) => sum + v, 0) / values.length;
  const forecast = mean(rows.map((row) => row.predicted_mid - (row.adjusted_qty ?? row.predicted_mid)));
  const execution = mean(rows.map((row) => (row.adjusted_qty ?? row.predicted_mid) - (row.prepared_qty ?? row.adjusted_qty ?? row.predicted_mid)));
  const onSite = mean(rows.map((row) => (row.prepared_qty ?? row.sold_qty ?? 0) - (row.sold_qty ?? 0)));
  const total = mean(rows.map((row) => row.predicted_mid - (row.sold_qty ?? 0)));
  return { n: rows.length, forecast, execution, onSite, total };
});
const reviewChart = computed(() => reviews.value.filter((row) => typeof row.sold_qty === "number").slice(0, 5));
const reviewMax = computed(() => Math.max(1, ...reviewChart.value.flatMap((row) => [row.predicted_mid, row.sold_qty ?? 0])));
const reviewWidth = (value: number) => `${Math.max(0, Math.min(100, value / reviewMax.value * 100))}%`;
const percent = (value: number | undefined | null) => (value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`);
const formatSigned = (value: number | undefined | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
};
</script>

<template>
  <PageHeader title="把经营变化算清楚" description="核对台账与每次备餐决策。营业中的盘点也会进入当前汇总，闭餐后须更新最终结果。" eyebrow="经营复盘" />
  <AsyncState :loading="loading" :error="error" @retry="load">
    <DataPanel>
      <div class="panel-head"><span class="kicker">台账汇总</span><h3>经营记录对照</h3></div>
      <p class="source-note">这些是项目台账及测算场景的描述性比较，可能包含尚未闭餐的盘点；不能视为已实现的现场减损或因果收益。</p>
      <div v-if="rateGap" class="rate-insight"><strong>两阶段剩余率相差 {{ rateGap }} 个百分点</strong><span>描述性测算对照，不能证明由系统造成。</span></div>
      <div class="rate-compare" aria-label="基线期与策略期剩余率对比">
        <div><span>基线期剩余率</span><strong>{{ rate("baseline_leftover_rate") === null ? "暂无数据" : `${pick("baseline_leftover_rate")}%` }}</strong><div class="rate-track"><span :style="{ width: rateWidth('baseline_leftover_rate') }"></span></div></div>
        <div><span>策略期剩余率</span><strong>{{ rate("intervention_leftover_rate") === null ? "暂无数据" : `${pick("intervention_leftover_rate")}%` }}</strong><div class="rate-track"><span :style="{ width: rateWidth('intervention_leftover_rate') }"></span></div></div>
      </div>
      <p class="rate-axis">两图同一刻度：0–{{ rateScale }}%</p>
      <div class="report-grid">
        <div><span>建议执行率</span><strong>{{ pick("adoption_rate") }}%</strong></div>
        <div><span>剩余成本测算差额</span><strong>¥{{ report.summary?.avoided_loss ?? 0 }}</strong></div>
      </div>
    </DataPanel>

    <DataPanel>
      <details class="experiment-details"><summary>这些变化是否来自系统？查看验证说明</summary><p class="source-note">现有对照仅供演示和方法核对，尚不能证明现场减损效果。</p>
      <div v-if="attribution" class="attribution-grid">
        <div><span>观测差异</span><strong>{{ rateGap ?? "—" }} pp</strong><small>基线期与策略期各 7 个完整营业日</small></div>
        <div><span>可识别下限</span><strong>{{ attribution.real_ledger.min_detectable_effect_pp }} pp</strong><small>14 天、噪声 {{ attribution.real_ledger.residual_sd_pp }} pp，80% 功效</small></div>
        <div><span>要证明 5 pp</span><strong>{{ attribution.real_ledger.required_days_for_5pp ?? "—" }} 个营业日</strong><small>按现有数据波动测算，现场需重新评估</small></div>
      </div>
      <ul v-if="attribution" class="attribution-notes">
        <li>两阶段都是完整 7 天、星期构成相同，所以这 {{ rateGap }} pp 不是“周末效应”。</li>
        <li>
          把第 8 天当断点做 ITS，会得到
          {{ formatSigned(attribution.real_ledger.negative_control_fit.effect) }} pp
          （95% 区间 {{ formatSigned(attribution.real_ledger.negative_control_fit.ci_low) }} ~
          {{ formatSigned(attribution.real_ledger.negative_control_fit.ci_high) }}）——
          可这段数据里<b>没有任何干预上线</b>。同一方法在负对照上“测得出”，说明单靠前后对比分不清干预与同期变化。
        </li>
        <li>
          恢复实验（120 次）里 ITS 的 95% 区间覆盖率
          {{ percent(attribution.recovery["effect_-5pct"]?.its.coverage95) }}、假阳性率
          {{ percent(attribution.placebo.its_false_positive_rate) }}；BSTS 区间偏窄（覆盖率
          {{ percent(attribution.recovery["effect_-5pct"]?.bsts.coverage95) }}），只作敏感性对照。
        </li>
      </ul>
      <p class="source-note">
        结论：{{ rateGap ?? "—" }} pp 只能作为<b>描述性对照</b>，不能写成减损成效；要认领效果，需要预注册干预、并行对照档口，并连续观测约
        {{ attribution?.real_ledger.required_days_for_5pp ?? 35 }} 个营业日。
        <RouterLink to="/app/evidence">查看实验四的完整方法与限制 →</RouterLink>
      </p>
      </details><div v-if="decomposition" class="decomposition">
        <h4>预测差在哪一步（最近 {{ decomposition.n }} 条有售出记录的预测）</h4>
        <div class="decomposition-row"><span>预测 → 确认计划</span><b>{{ formatSigned(decomposition.forecast) }}</b></div>
        <div class="decomposition-row"><span>确认计划 → 实际制作</span><b>{{ formatSigned(decomposition.execution) }}</b></div>
        <div class="decomposition-row"><span>实际制作 → 实际售出</span><b>{{ formatSigned(decomposition.onSite) }}</b></div>
        <div class="decomposition-row total"><span>合计差额（预测中位 − 实际售出）</span><b>{{ formatSigned(decomposition.total) }}</b></div>
        <p class="source-note">正数表示“计划多了”。三段之和等于合计差额，可据此核对建议、制作调整与未售出各环节。</p>
      </div>
      <p v-else class="source-note">尚无完整的计划执行记录。确认备餐计划并回填售出结果后，可分别核对建议量、制作量与售出量。</p>
    </DataPanel>

    <DataPanel>
      <div class="panel-head"><span class="kicker">逐次复盘</span><h3>建议、计划和实际差在哪里？</h3></div>
      <p class="source-note">最近100次预测按菜品、日期和餐次匹配。营业中的记录仍会变化，闭餐回填后再核对偏差。</p>
      <div v-if="!reviews.length" class="review-empty"><strong>还没有可复盘的备餐计划</strong><p>现有台账已计入上方汇总；执行记录需要从备餐计划开始，闭餐后关联实际结果。</p><RouterLink class="btn primary" to="/app/prediction">制定第一份备餐计划 →</RouterLink></div>
      <div v-if="reviewChart.length" class="review-visual" aria-label="最近有实际售出记录的建议与售出对比">
        <div class="review-key"><span><i></i>建议量</span><span><i></i>实际售出</span><small>单位：份 · 最近 {{ reviewChart.length }} 条有售出记录的预测</small></div>
        <div v-for="row in reviewChart" :key="row.prediction_id" class="review-bar-row"><div><strong>{{ row.dish_name }}</strong><small>{{ row.target_date }} · {{ row.meal_period }}</small></div><div class="review-bars"><span :style="{ width: reviewWidth(row.predicted_mid) }"></span><span :style="{ width: reviewWidth(row.sold_qty ?? 0) }"></span></div><div class="review-values">{{ row.predicted_mid }} / {{ row.sold_qty }}</div></div>
      </div>
      <div v-if="reviews.length" class="review-table"><table><thead><tr><th>日期 / 餐次 / 菜品</th><th>预测 / 确认计划</th><th>售出 / 制作</th><th>预测 / 执行偏差</th><th>调整原因 / 记录来源</th></tr></thead><tbody>
        <tr v-for="row in reviews" :key="row.prediction_id"><td>{{ row.target_date }} · {{ row.meal_period }}<br>{{ row.dish_name }}</td><td>{{ row.predicted_mid }} / {{ row.adjusted_qty ?? '待确认' }}</td><td>{{ row.sold_qty ?? '待回填' }} / {{ row.prepared_qty ?? '待回填' }}</td><td>{{ row.prediction_error ?? '—' }} / {{ row.execution_error ?? '—' }}</td><td>{{ row.reason || '未记录调整原因' }}<br>{{ row.source_nature }}<br>历史截止 {{ row.history_cutoff }}</td></tr>
      </tbody></table></div>
    </DataPanel>

    <DataPanel>
      <details class="experiment-details"><summary>公开数据实验与验证范围</summary>
        <p v-if="!backtest.available" class="source-note">公开实验报告不可用，暂不展示精度数字。</p>
        <template v-else>
          <p class="source-note">数据集：{{ backtest.dataset }} · 单位：{{ backtest.unit }} · 模型：{{ backtest.model_version }} · 运行：{{ backtest.run_id }}</p>
          <div class="metric-grid"><MetricCard label="测试样本" :value="backtest.splits?.test?.rows ?? '—'" detail="时间顺序切分" /><MetricCard label="LightGBM MAE" :value="backtest.test_metrics?.pred_lgbm?.mae?.toFixed(4) ?? '—'" detail="缩放销量单位" /><MetricCard label="同星期均值基线 MAE" :value="backtest.test_metrics?.pred_same_weekday_mean4?.mae?.toFixed(4) ?? '—'" detail="缩放销量单位" /></div>
          <p class="source-note">当前 LightGBM MAE 高于同星期均值基线。这组实验不能解释为份数、人民币、产能或现场减损收益。</p>
          <ul class="source-note"><li v-for="item in backtest.limitations" :key="item">{{ item }}</li></ul>
        </template>
      </details>
    </DataPanel>
  </AsyncState>
</template>

<style scoped>
.report-grid,.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr));margin:16px 0}
.report-grid div{padding:15px;background:#f7fafc;border-radius:8px;min-width:0}.report-grid span,.report-grid strong{display:block}.report-grid span{font-size:13px;color:var(--fw-muted);line-height:1.6}.report-grid strong{font-size:18px;margin-top:9px}
.source-note{font-size:13px;color:var(--fw-muted);line-height:1.7;overflow-wrap:anywhere}.review-table{overflow-x:auto}.review-table table{width:100%;min-width:740px;border-collapse:collapse;font-size:13px}.review-table th,.review-table td{text-align:left;padding:12px;border-bottom:1px solid #dce8f2;line-height:1.7}.review-table th{background:#f3f8fc}
.experiment-details summary{cursor:pointer;color:var(--fw-primary-strong);font-size:15px;font-weight:700}.experiment-details[open] summary{margin-bottom:16px}
@media(max-width:700px){.report-grid,.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.rate-compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:20px 0;padding:19px 0;border-top:1px solid #e6edf1;border-bottom:1px solid #e6edf1}.rate-compare>div{min-width:0}.rate-compare span,.rate-compare strong{display:block}.rate-compare>div>span{color:#61786b;font-size:12px}.rate-compare strong{font-size:24px;color:#214b69;margin:5px 0 10px}.rate-track{height:12px;background:#eef2ed;border-radius:2px;overflow:hidden}.rate-track span{height:100%;background:#dba866}.rate-compare>div:nth-child(2) .rate-track span{background:#3b84ad}.review-visual{padding:14px 0 18px;border-top:1px solid #e6edf1;border-bottom:1px solid #e6edf1;margin:17px 0}.review-key{display:flex;gap:15px;align-items:center;margin-bottom:12px;color:#5a7465;font-size:11px}.review-key i{display:inline-block;width:8px;height:8px;margin-right:5px;background:#9ab7a3}.review-key span:nth-child(2) i{background:#3b84ad}.review-key small{margin-left:auto}.review-bar-row{display:grid;grid-template-columns:minmax(100px,160px) minmax(0,1fr) 75px;gap:10px;align-items:center;padding:7px 0}.review-bar-row>div:first-child{min-width:0}.review-bar-row strong,.review-bar-row small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.review-bar-row strong{font-size:12px}.review-bar-row small{font-size:10px;color:#789080}.review-bars{display:grid;gap:3px}.review-bars span{height:7px;min-width:2px;border-radius:2px;background:#9ab7a3}.review-bars span:nth-child(2){background:#3b84ad}.review-values{text-align:right;color:#496455;font-size:11px;font-variant-numeric:tabular-nums}@media(max-width:700px){.rate-compare{grid-template-columns:1fr;gap:14px}.review-key{flex-wrap:wrap}.review-key small{width:100%;margin-left:0}.review-bar-row{grid-template-columns:90px minmax(0,1fr) 57px;gap:5px}}
.rate-insight{display:flex;align-items:baseline;gap:12px;padding:13px 0 0;color:#254c69}.rate-insight strong{font-size:19px}.rate-insight span,.rate-axis{font-size:11px;color:#708594}.rate-axis{text-align:right;margin:-12px 0 10px}.report-grid div{background:transparent;border-top:1px solid #e6edf1;border-radius:0;padding:12px 0}.rate-compare{margin-bottom:17px}@media(max-width:700px){.rate-insight{display:block}.rate-insight span{display:block;margin-top:5px}.rate-axis{text-align:left;margin:0 0 10px}}
.attribution-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0 4px}
.attribution-grid>div{border:1px solid var(--fw-border);border-radius:8px;padding:13px 15px;background:var(--fw-surface)}
.attribution-grid span{font-size:12px;color:var(--fw-muted)}
.attribution-grid strong{display:block;margin:5px 0 3px;font-size:21px;color:var(--fw-ink);font-variant-numeric:tabular-nums}
.attribution-grid small{font-size:11.5px;color:var(--fw-muted);line-height:1.5}
.attribution-notes{margin:12px 0 10px;padding-left:20px;color:#41586a;font-size:13px;line-height:1.85}
.attribution-notes b{color:#a33b25}
.decomposition{margin-top:14px;padding:14px 16px;border:1px solid var(--fw-border);border-radius:8px;background:#f7fafb}
.decomposition h4{margin:0 0 10px;font-size:14px;color:var(--fw-ink)}
.decomposition-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px dashed #dde7ea;font-size:13px;color:#4a626f}
.decomposition-row b{font-variant-numeric:tabular-nums;color:var(--fw-ink)}
.decomposition-row.total{border-bottom:0;font-weight:700;color:var(--fw-ink)}
@media(max-width:720px){.attribution-grid{grid-template-columns:1fr}}
</style>