<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import PageHeader from "../components/PageHeader.vue";
import { RouterLink } from "vue-router";
import { getApi, postApi } from "../utils/vue-api";

type Check = { name: string; passed: boolean; detail: string };
type Readiness = { ready: boolean; checks: Check[]; counts: Record<string, number> };
type Result = { schoolId: number; stallId: number; dishId: number; verificationStatus: string; message: string };

const form = ref({ schoolName: "", schoolCode: "", authorizationReference: "", dataPurpose: "校园餐饮备餐与减损分析", retentionPeriod: "保存至校赛复盘结束后90天", stallName: "", stallCategory: "基础餐饮", location: "", managerName: "", dishName: "", dishCategory: "套餐饭", price: 0, unitCost: 0, prepMinutes: 20, quantityUnit: "份", operatorName: "" });
const readiness = ref<Readiness | null>(null);
const result = ref<Result | null>(null);
const error = ref("");
const busy = ref(false);
const valid = computed(() => Boolean(form.value.schoolName.trim() && form.value.schoolCode.trim() && form.value.authorizationReference.trim() && form.value.dataPurpose.trim() && form.value.retentionPeriod.trim() && form.value.stallName.trim() && form.value.managerName.trim() && form.value.dishName.trim() && form.value.operatorName.trim() && form.value.price >= form.value.unitCost && form.value.quantityUnit === "份"));

async function loadReadiness() {
  try { readiness.value = await getApi<Readiness>("/onboarding/readiness"); } catch (e) { error.value = e instanceof Error ? e.message : "建档检查加载失败"; }
}
async function submit() {
  if (!valid.value || busy.value) return;
  busy.value = true; error.value = ""; result.value = null;
  try { result.value = await postApi<Result>("/onboarding", { ...form.value }); await loadReadiness(); }
  catch (e) { error.value = e instanceof Error ? e.message : "建档提交失败"; }
  finally { busy.value = false; }
}
function readinessText(check: Check) {
  if (check.name === "档口建档") return check.passed ? "已有档口资料，请核对名称、负责人和菜品是否与现场一致。" : "请先登记档口名称、位置和负责人。";
  if (check.name === "训练准入") return "待真实台账来源与授权核验完成后，再评估是否适合更新建议方法。";
  return check.detail;
}
onMounted(loadReadiness);
</script>

<template>
  <div class="onboarding-view">
    <PageHeader eyebrow="首次准备" title="确认学校、档口和菜品信息" description="完成首次设置后即可开始记录经营和制定备餐计划。提交信息不代表授权材料已审核通过。" />
    <div class="notice"><strong>当前可用单位：份</strong><span>备餐建议、经营记录和数量核对目前统一按“份”计算。其他单位暂不能用于备餐计划。</span></div>
    <form class="form" @submit.prevent="submit">
      <section><h3>学校与数据授权</h3><div class="grid"><label>学校名称<input v-model="form.schoolName" required placeholder="例如：河北某高校" /></label><label>学校内部编号<input v-model="form.schoolCode" required placeholder="例如：HEB-001" /></label><label class="wide">授权材料位置或编号<input v-model="form.authorizationReference" required placeholder="填写材料名称、编号或存放位置" /></label><label>数据用途<input v-model="form.dataPurpose" required /></label><label>数据保留期限<input v-model="form.retentionPeriod" required /></label></div></section>
      <section><h3>档口信息</h3><div class="grid"><label>档口名称<input v-model="form.stallName" required placeholder="例如：一食堂一层快餐档" /></label><label>档口类别<input v-model="form.stallCategory" /></label><label>地点<input v-model="form.location" placeholder="例如：一食堂一层东侧" /></label><label>负责人<input v-model="form.managerName" required /></label></div></section>
      <section><h3>首个菜品</h3><div class="grid"><label>菜品名称<input v-model="form.dishName" required placeholder="例如：香菇滑鸡饭" /></label><label>菜品类别<input v-model="form.dishCategory" /></label><label>售价（元）<input v-model.number="form.price" type="number" min="0" step="0.01" required /></label><label>每份成本（元）<input v-model.number="form.unitCost" type="number" min="0" step="0.01" required /></label><label>备餐时间（分钟）<input v-model.number="form.prepMinutes" type="number" min="0" required /></label><div class="unit-field"><span>销售与盘点单位</span><strong>份</strong></div></div></section>
      <section><h3>操作责任</h3><div class="grid"><label>操作人<input v-model="form.operatorName" required placeholder="填写真实经办人" /></label></div></section>
      <p v-if="form.price < form.unitCost" class="field-error">售价不能低于单位成本，请先核对金额口径。</p><p v-if="error" class="field-error" role="alert">{{ error }}</p>
      <button class="primary" type="submit" :disabled="!valid || busy">{{ busy ? "提交中…" : "保存建档" }}</button>
    </form>
    <section v-if="result" class="result success"><strong>建档完成，接下来录入历史台账</strong><span>学校 {{ result.schoolId }} · 档口 {{ result.stallId }} · 菜品 {{ result.dishId }}</span><span>授权材料仍待人工核对。</span><p>{{ result.message }}</p><RouterLink to="/app/operations/feedback">去录入或导入台账 →</RouterLink></section>
    <section v-if="readiness" class="readiness"><div class="readiness-head"><h3>启用准备</h3><span :class="readiness.ready ? 'ok' : 'pending'">{{ readiness.ready ? "已满足" : "仍需补充" }}</span></div><div v-for="check in readiness.checks" :key="check.name" class="check"><b>{{ check.passed ? "✓" : "○" }} {{ check.name === "训练准入" ? "历史记录可用性" : check.name }}</b><span>{{ readinessText(check) }}</span></div></section>
  </div>
</template>

<style scoped>
.onboarding-view{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;max-width:1240px;margin:0 auto;align-items:start}
.onboarding-view>.fw-page-header{margin-bottom:0}
.notice{display:flex;flex-wrap:wrap;gap:6px 16px;padding:14px 18px;border:1px solid var(--fw-border);background:var(--fw-tint);border-radius:10px;color:var(--fw-muted);font-size:13px;line-height:1.75}.notice strong{color:var(--fw-primary-strong)}
.readiness{grid-row:3;padding:20px 24px;border:1px solid var(--fw-border);border-radius:12px;background:#fff;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 24px;min-width:0}
.readiness-head{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding-bottom:12px}
.readiness h3{margin:0;font-size:17px;color:var(--fw-ink)}
.check{min-width:0;display:block;border-top:1px solid var(--fw-border);padding:14px 0 0;font-size:13px}.check b{display:block;color:var(--fw-ink);line-height:1.6}.check span{display:block;margin-top:7px;color:var(--fw-muted);line-height:1.8;overflow-wrap:anywhere}
.ok,.pending{font-size:12px;font-weight:700;padding:5px 10px;border-radius:6px}.ok{color:#287346;background:#e7f6eb}.pending{color:#8a6416;background:#fff4d8}
.form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin:0;counter-reset:steps;min-width:0}
.form section{min-width:0;margin:0;padding:24px;background:#fff;border:1px solid var(--fw-border);border-radius:12px;counter-increment:steps}
.form section:first-child{grid-column:1/-1}.form section:last-of-type{grid-column:1/-1}
.form h3{display:flex;gap:10px;align-items:center;margin:0 0 22px;font-size:18px;color:var(--fw-ink)}
.form h3:before{content:counter(steps,decimal-leading-zero);display:grid;place-items:center;flex:none;width:30px;height:30px;border-radius:6px;background:var(--fw-tint);color:var(--fw-primary);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 20px}.wide{grid-column:1/-1}
label,.unit-field{display:flex;flex-direction:column;gap:8px;min-width:0;font-size:13px;color:var(--fw-muted);font-weight:700;line-height:1.6}
input,.unit-field strong{width:100%;min-width:0;box-sizing:border-box;font:inherit;font-weight:400;color:var(--fw-ink);border:1px solid var(--fw-border);border-radius:8px;padding:11px 12px;background:#fbfdff;min-height:44px}
.unit-field strong{background:var(--fw-tint)}
.form section:last-of-type .grid{max-width:540px;grid-template-columns:1fr}
.primary{justify-self:start;border:0;border-radius:8px;background:var(--fw-primary);color:#fff;font-weight:700;padding:12px 28px;cursor:pointer;min-height:44px}.primary:disabled{opacity:.45;cursor:not-allowed}
.field-error{grid-column:1/-1;margin:0;color:#b44c36;font-size:13px;line-height:1.7}
.result{padding:22px 24px;border:1px solid #b9dfc7;border-radius:12px;background:#f4fbf6;color:#2f6b46}.result strong,.result span{display:block}.result span,.result p{font-size:13px;margin-top:8px;line-height:1.7}
@media(max-width:1100px){.form{grid-template-columns:1fr}.form section{grid-column:1/-1}.readiness{gap:0 18px}}
@media(max-width:700px){.onboarding-view{gap:16px}.readiness{grid-template-columns:1fr;padding:18px}.check{padding:12px 0}.check:last-child{padding-bottom:0}.form{gap:16px}.form section{padding:18px}.grid{grid-template-columns:1fr;gap:16px}.wide{grid-column:auto}.form h3{margin-bottom:18px}.primary{width:100%}}
</style>
