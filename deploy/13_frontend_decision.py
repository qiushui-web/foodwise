# -*- coding: utf-8 -*-
"""前端补丁：训练模型决策依据(归因条形图+决策路径) + 大模型混测面板"""
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = str(ROOT / "src" / "main" / "resources" / "static" / "build" / "app.js")
CSS = str(ROOT / "src" / "main" / "resources" / "static" / "css" / "visual-enhanced.css")

js = io.open(JS, encoding="utf-8").read()

# 1) renderPrediction 中插入两个面板
anchor = "${renderAdvicePanel(advice)}</div>`;"
inject = "${renderDecisionPanel(data)}${renderCrossCheckBlock()}${renderAdvicePanel(advice)}</div>`;"
assert anchor in js, "render anchor not found"
js = js.replace(anchor, inject, 1)

# 2) 追加渲染函数
extra_js = r"""
/* ===== 训练模型决策依据（逐树路径归因，来自真实训练模型） ===== */
function renderDecisionPanel(data) {
    const contribs = data.decisionContributions || [];
    const rules = data.decisionRules || [];
    if (!contribs.length && !rules.length) return '';
    const maxAbs = Math.max(1, ...contribs.map(c => Math.abs(Number(c.soldDelta) || 0)));
    const bars = contribs.map(c => {
        const v = Number(c.soldDelta) || 0;
        const w = Math.max(6, Math.round(Math.abs(v) / maxAbs * 100));
        const up = v >= 0;
        return `<div class="dc-row"><span class="dc-name" title="${escapeHtml(c.featureZh || c.feature || '')}">${escapeHtml(c.featureZh || c.feature || '')}</span>` +
            `<div class="dc-bar-wrap"><div class="dc-bar ${up ? 'dc-up' : 'dc-down'}" style="width:${w}%"></div></div>` +
            `<span class="dc-val ${up ? 'dc-up-text' : 'dc-down-text'}">${up ? '+' : ''}${v}份 · ${c.splits}次分裂</span></div>`;
    }).join('');
    const ruleList = (rules || []).slice(0, 6).map(r => `<li>${escapeHtml(String(r))}</li>`).join('');
    return `<div class="decision-model-panel"><div class="dmp-head"><strong><i data-lucide="git-branch"></i> 训练模型决策依据（LGBM 逐树路径归因）</strong>` +
        `<span class="dmp-tag">${data.modelTrees || 500}棵回归树 · ${data.trainedRows || 2600}行真实数据训练</span></div>` +
        `<div class="dc-bars">${bars}</div>` +
        (ruleList ? `<ul class="dc-rules">${ruleList}</ul>` : '') + `</div>`;
}

/* ===== 大模型混测 ===== */
function renderCrossCheckBlock() {
    return `<div class="crosscheck-block"><button type="button" class="crosscheck-btn" onclick="runCrossCheck(this)">` +
        `<i data-lucide="shield-check"></i> 与大模型混测：独立复核训练模型的决策</button>` +
        `<div id="crossCheckPanel" class="crosscheck-panel"></div></div>`;
}

async function runCrossCheck(btn) {
    const panel = document.getElementById('crossCheckPanel');
    if (!panel) return;
    panel.innerHTML = '<div class="cc-loading">正在把训练模型的决策路径与事实提交给大模型独立复核…</div>';
    lucide.createIcons();
    try {
        const resp = await fetch('/api/model/cross-check', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dishId: Number(document.getElementById('dishId').value),
                weather: document.getElementById('weather').value,
                examWeek: document.getElementById('examWeek').checked,
                campusEvent: document.getElementById('campusEvent').checked
            })
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(d.message || '混测请求失败');
        panel.innerHTML = renderCrossCheck(d);
        lucide.createIcons();
    } catch (e) {
        panel.innerHTML = `<div class="cc-loading">混测未完成：${escapeHtml(e.message)}</div>`;
    }
}

function renderCrossCheck(d) {
    const det = d.deterministic || {};
    const checks = (det.checks || []).map(c =>
        `<li class="${c.pass ? 'cc-pass' : 'cc-fail'}"><span>${c.pass ? '✓' : '!'}</span><div><b>${escapeHtml(c.name)}</b><small>${escapeHtml(c.detail)}</small></div></li>`
    ).join('');
    const llm = d.llm || {};
    let llmCard;
    if (llm.enabled && llm.status === 'ok') {
        const vmap = { agree: '认可', caution: '保留意见', disagree: '不认可' };
        const cmap = { '一致': 'cc-cons-ok', '接近': 'cc-cons-mid', '分歧': 'cc-cons-bad', '无法判定': 'cc-cons-mid' };
        llmCard = `<div class="cc-llm"><div class="cc-llm-head"><strong><i data-lucide="bot"></i> 大模型独立判断（${escapeHtml(llm.model || 'GLM')}）</strong>` +
            `<span class="cc-cons ${cmap[llm.consistency] || ''}">与训练模型：${escapeHtml(llm.consistency || '—')}</span></div>` +
            `<div class="cc-range">大模型独立预估 <b>${llm.llmLow}–${llm.llmHigh} 份</b> ｜ 训练模型预测 <b>${d.lgbmPrediction ?? '—'} 份</b> ｜ 规则引擎 <b>${d.rulePrediction} 份</b> ｜ 大模型对训练模型结论：<b>${escapeHtml(vmap[llm.verdict] || llm.verdict || '—')}</b></div>` +
            `<p class="cc-comment">“${escapeHtml(llm.comment || '')}”</p></div>`;
    } else {
        llmCard = `<div class="cc-llm cc-llm-off"><strong><i data-lucide="bot"></i> 大模型独立判断</strong><p>${escapeHtml(llm.status || '大模型未启用，当前为确定性交叉校验')}</p></div>`;
    }
    return `<div class="cc-summary"><b>确定性交叉校验：${escapeHtml(det.verdict || '—')}</b>（${det.passCount || 0}/${det.totalCount || 0} 项通过）` +
        ` ｜ 训练模型回测 MAPE ${escapeHtml(d.modelMape)}% ｜ ${d.trainedRows}行真实数据训练 ｜ ${d.modelTrees}棵树</div>` +
        `<ul class="cc-checks">${checks}</ul>${llmCard}`;
}
"""
if "function renderDecisionPanel" not in js:
    js = js.rstrip() + "\n" + extra_js
io.open(JS, "w", encoding="utf-8").write(js)
print("app.js patched")

css = io.open(CSS, encoding="utf-8").read()
extra_css = r"""
/* ===== 训练模型决策依据面板 ===== */
.decision-model-panel{margin:14px 0;background:linear-gradient(160deg,#f4f9fb,#f7faf6);border:1px solid #d9e8ea;border-radius:14px;padding:14px 16px}
.dmp-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.dmp-head strong{display:flex;align-items:center;gap:6px;font-size:13px;color:#123f36}
.dmp-tag{font-size:10px;color:#1f6f96;background:#e6f2f8;border:1px solid #cfe4ef;border-radius:20px;padding:3px 10px;white-space:nowrap}
.dc-row{display:grid;grid-template-columns:92px 1fr 128px;align-items:center;gap:8px;margin:6px 0}
.dc-name{font-size:11px;color:#3f564d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dc-bar-wrap{height:8px;background:#e8efec;border-radius:6px;overflow:hidden}
.dc-bar{height:100%;border-radius:6px;min-width:4px}
.dc-up{background:linear-gradient(90deg,#4cb47a,#2f8f5b)}
.dc-down{background:linear-gradient(90deg,#9db8d2,#6d8fb0)}
.dc-val{font-size:10px;color:#7a8c85;text-align:right;white-space:nowrap}
.dc-up-text{color:#2f8f5b;font-weight:700}.dc-down-text{color:#5a7d9e;font-weight:700}
.dc-rules{margin:10px 0 0;padding-left:18px;font-size:10.5px;color:#6b7f76;line-height:1.8}
/* ===== 大模型混测面板 ===== */
.crosscheck-block{margin:14px 0}
.crosscheck-btn{width:100%;padding:12px;border-radius:12px;border:1.5px dashed #6fb7d6;background:#f2f9fd;color:#1f6f96;font-weight:700;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;transition:.15s}
.crosscheck-btn:hover{background:#e6f3fb;border-style:solid}
.crosscheck-panel{margin-top:10px}
.cc-loading{font-size:12px;color:#7a8c85;text-align:center;padding:16px;background:#f7faf9;border:1px solid #e3ede8;border-radius:10px}
.cc-summary{font-size:12px;color:#3f564d;background:#eef7f1;border:1px solid #d6ead9;border-radius:10px;padding:10px 12px;margin-bottom:8px;line-height:1.6}
.cc-checks{list-style:none;padding:0;margin:0 0 8px}
.cc-checks li{display:flex;gap:8px;align-items:flex-start;padding:7px 10px;border-radius:9px;margin:5px 0;background:#f7faf9;border:1px solid #e8efec}
.cc-checks li span{flex:none;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff;margin-top:1px}
.cc-pass span{background:#3fa46a}.cc-fail span{background:#d9835f}
.cc-checks b{color:#2c463c;display:block;font-size:11.5px}
.cc-checks small{color:#80918a;font-size:10.5px;line-height:1.6}
.cc-llm{border:1.5px solid #b9d4e6;background:linear-gradient(160deg,#f0f7fd,#f6faf6);border-radius:12px;padding:12px 14px}
.cc-llm-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}
.cc-llm-head strong{font-size:12.5px;color:#1f5f86;display:flex;gap:6px;align-items:center}
.cc-cons{font-size:10.5px;border-radius:20px;padding:3px 10px;font-weight:700;white-space:nowrap}
.cc-cons-ok{background:#e2f4e8;color:#2f8f5b}.cc-cons-mid{background:#fdf3e0;color:#b07d2f}.cc-cons-bad{background:#fce8e4;color:#c05a45}
.cc-range{font-size:11.5px;color:#3f564d;line-height:1.8}
.cc-comment{margin:6px 0 0;font-size:11.5px;color:#5f7168;font-style:italic;line-height:1.6}
.cc-llm-off p{margin:6px 0 0;font-size:11px;color:#80918a;line-height:1.6}
.cc-llm-off strong{font-size:12.5px;color:#5f7168;display:flex;gap:6px;align-items:center}
"""
if "decision-model-panel" not in css:
    css = css.rstrip() + "\n" + extra_css
io.open(CSS, "w", encoding="utf-8").write(css)
print("css patched")
