<script setup lang="ts">
import DataPanel from "../components/DataPanel.vue";
import MetricCard from "../components/MetricCard.vue";
import AsyncState from "../components/AsyncState.vue";
import type { ExperimentReport, OperatingReport } from "../api/types";
import PageHeader from "../components/PageHeader.vue";
import { onMounted, ref } from "vue";
import { getApi } from "../utils/vue-api";
const report = ref<OperatingReport>({}); const backtest = ref<ExperimentReport>({ available: false }); const loading = ref(true); const error = ref("");
async function load() { loading.value = true; error.value = ""; try { [report.value, backtest.value] = await Promise.all([getApi<OperatingReport>("/reports"), getApi<ExperimentReport>("/analytics/backtest")]); } catch (e) { error.value = e instanceof Error ? e.message : "报告加载失败"; } finally { loading.value = false; } }
onMounted(load);
const pick = (key: string) => report.value?.summary?.[key] ?? "—";
</script>
<template><PageHeader title="把经营变化算清楚" description="依据统一经营台账，比较基线期与策略期的经营结果。" eyebrow="经营数据总览" /><AsyncState :loading="loading" :error="error" @retry="load"><DataPanel><div class="panel-head"><span class="kicker">公开数据实验</span><h3>冻结测试集验证</h3></div><p v-if="!backtest.available" class="state">公开实验报告不可用，暂不展示精度数字。</p><template v-else><p class="source-note">运行：{{ backtest.run_id }}<br>数据集：{{ backtest.dataset }}<br>单位：{{ backtest.unit }}<br>模型：{{ backtest.model_version }}</p><div class="metric-grid"><MetricCard label="测试样本" :value="backtest.splits?.test?.rows ?? '—'" detail="时间顺序切分" /><MetricCard label="LightGBM MAE" :value="backtest.test_metrics?.pred_lgbm?.mae?.toFixed(4) ?? '—'" detail="缩放销量单位" /><MetricCard label="同星期均值基线 MAE" :value="backtest.test_metrics?.pred_same_weekday_mean4?.mae?.toFixed(4) ?? '—'" detail="缩放销量单位" /></div><p class="source-note">当前 LightGBM MAE 高于同星期均值基线。这组实验不能解释为份数、人民币、产能或现场减损收益。</p><ul class="source-note"><li v-for="item in backtest.limitations" :key="item">{{ item }}</li></ul></template></DataPanel><DataPanel><div class="panel-head"><span class="kicker">复盘摘要</span><h3>经营台账指标变化</h3><p class="source-note">项目台账及测算场景对比；不代表现场试点或因果改善效果。</p></div><div class="report-grid"><div><span>策略期剩余率</span><strong>{{ pick("intervention_leftover_rate") }}%</strong></div><div><span>基线期剩余率</span><strong>{{ pick("baseline_leftover_rate") }}%</strong></div><div><span>建议执行率</span><strong>{{ pick("adoption_rate") }}%</strong></div><div><span>剩余成本测算差额</span><strong>¥{{ report.summary?.avoided_loss ?? 0 }}</strong></div></div></DataPanel><DataPanel><div class="panel-head"><span class="kicker">数据治理</span><h3>经营复盘闭环</h3></div><div class="steps"><div><b>01</b><span>统一导入经营资料</span></div><div><b>02</b><span>校验备餐、售出与剩余</span></div><div><b>03</b><span>更新需求基线与模型</span></div><div><b>04</b><span>沉淀下一周期动作</span></div></div></DataPanel></AsyncState></template>
<style scoped>
.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px}
.report-grid,.steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.report-grid div,.steps div{padding:15px;background:#f5f9fd;border-radius:8px;min-width:0}
.report-grid span,.report-grid strong,.steps b,.steps span{display:block}
.report-grid span,.steps span{font-size:13px;color:#496a85;line-height:1.6}
.report-grid strong{font-size:18px;margin-top:9px}
.steps b{font-size:18px;color:var(--fw-primary);margin-bottom:8px}
.source-note{font-size:13px;color:var(--fw-muted);line-height:1.7;overflow-wrap:anywhere}
@media(max-width:700px){.metric-grid,.report-grid,.steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
