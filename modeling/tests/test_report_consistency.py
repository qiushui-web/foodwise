"""研究报告与研究产物的数字必须对得上。

报告是给人看的，产物是给机器算的；两者漂移是最常见的"论文造假"事故来源（哪怕只是忘更新）。
这里把报告里出现的关键数字逐条与 JSON 产物核对，任何一条对不上就失败。
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "研究报告_食刻有数_v3_20261027.md"
RES = ROOT / "src" / "main" / "resources" / "modeling"


class ReportConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REPORT.exists():
            raise unittest.SkipTest("研究报告尚未生成")
        cls.text = REPORT.read_text(encoding="utf-8")
        cls.interval = json.loads((RES / "interval_backtest_metrics.json").read_text(encoding="utf-8"))
        cls.decision = json.loads((RES / "decision_backtest_metrics.json").read_text(encoding="utf-8"))
        cls.attribution = json.loads((RES / "attribution_backtest.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((RES / "model_manifest.json").read_text(encoding="utf-8"))

    def assertNumberAppears(self, value, digits, label):
        text = f"{value:.{digits}f}"
        self.assertIn(text, self.text, f"报告里没有出现 {label} 的正确数值 {text}")

    def test_interval_table_matches_artifact(self):
        methods = self.interval["methods"]
        self.assertNumberAppears(methods["quantile_raw"]["picp"] * 100, 2, "未校准覆盖率")
        self.assertNumberAppears(methods["cqr_stratified"]["picp"] * 100, 2, "部署覆盖率")
        self.assertNumberAppears(methods["cqr_stratified"]["pinaw"], 4, "部署区间宽度")
        self.assertNumberAppears(methods["cqr_stratified"]["winkler"], 2, "部署 Winkler")
        self.assertNumberAppears(methods["quantile_raw"]["winkler"], 2, "未校准 Winkler")

    def test_decision_table_matches_artifact(self):
        base = self.decision["base_scenario"]["methods"]
        for key in ("rule_10pct", "newsvendor_calibrated"):
            self.assertNumberAppears(base[key]["regret"] * 100, 2, f"{key} regret")
        self.assertNumberAppears(self.decision["base_scenario"]["mean_critical_ratio"], 3, "基准临界比")
        for scenario in self.decision["scenarios"]:
            self.assertNumberAppears(scenario["mean_critical_ratio"], 3, "扫描临界比")
            self.assertNumberAppears(scenario["methods"]["rule_10pct"]["regret"] * 100, 2, "扫描固定系数 regret")

    def test_attribution_numbers_match_artifact(self):
        recovery = self.attribution["recovery"]["effect_-5pct"]
        self.assertNumberAppears(abs(recovery["its"]["bias"]), 2, "ITS 偏差")
        self.assertNumberAppears(recovery["its"]["coverage95"] * 100, 1, "ITS 覆盖率")
        self.assertNumberAppears(recovery["bsts"]["coverage95"] * 100, 1, "BSTS 覆盖率")
        ledger = self.attribution["real_ledger"]
        self.assertNumberAppears(abs(ledger["negative_control_fit"]["effect"]), 2, "负对照效应")
        self.assertNumberAppears(ledger["min_detectable_effect_pp"], 2, "可识别下限")
        self.assertIn(f"{ledger['required_days_for_5pp']} 个营业日", self.text, "报告未写明所需营业日")

    def test_report_declares_not_identifiable(self):
        self.assertIn("不可识别", self.text)
        self.assertIn("not_identifiable", self.text)
        self.assertIn("负对照", self.text)

    def test_hashes_in_appendix_match_manifest(self):
        sha = self.manifest["calibration"]["artifact_sha256"]
        self.assertIn(sha, self.text, "附录中的校准产物哈希与清单不一致")
        for level, meta in self.manifest["quantile_models"].items():
            self.assertIn(meta["sha256"], self.text, f"附录缺少分位模型 {level} 的哈希")

    def test_reproduce_commands_cover_all_scripts(self):
        for script in ("32_fit_intervals.py", "33_decision_backtest.py", "34_attribute.py", "30_verify_manifest.py",
                       "44_baseline_vs_gbdt.py", "45_simulate.py", "46_power_analysis.py"):
            self.assertIn(script, self.text, f"复现命令缺少 {script}")

    def test_report_carries_the_v3_findings(self):
        # v3 的三条硬结论必须写在报告里，否则等于没做。
        self.assertIn("baseline", self.text.lower().replace("gbdt", "gbdt"))
        self.assertIn("4.32", self.text, "基线对照的 GBDT MAE 必须出现在报告里")
        self.assertIn("3.39", self.text, "基线对照的中位数 MAE 必须出现在报告里")
        self.assertIn("6.8 天", self.text, "功效实验的样本量结论必须出现")
        self.assertIn("不可声称清单", self.text, "报告必须包含不可声称清单")

    def test_external_validity_numbers_match_artifact(self):
        data = json.loads((ROOT / "modeling" / "data" / "03_output" / "external_zurich.json")
                          .read_text(encoding="utf-8"))
        self.assertIn("苏黎世", self.text, "报告必须写外部效度")
        for key in ("gbdt", "same_weekday_median", "mean_roll7"):
            metrics = data["methods"][key]
            self.assertIn(f"{metrics['mae']:.2f}", self.text, f"{key} 的 MAE 未出现在报告里")
            self.assertIn(f"{metrics['regret_per_100']:.2f}", self.text, f"{key} 的 regret 未出现在报告里")

    def test_no_unverified_causal_claim(self):
        # 允许出现"减损 30%"这类数字，但所在句子必须是在否定/限定它，不能当成结论陈述。
        banned = re.findall(r"减损\s*\d+(?:\.\d+)?\s*%", self.text)
        negations = ("不可信", "不成立", "不能", "拒绝", "并非", "无法验证", "不宣称")
        for match in banned:
            sentence = self._sentence_around(match)
            self.assertTrue(
                any(word in sentence for word in negations),
                f"报告把“{match}”当成了结论陈述：{sentence.strip()}",
            )

    def test_fourteen_day_table_matches_artifact(self):
        # 表 4-6 的每一行都必须与产物逐列对得上；缺货率曾经写成 0.0%，是最容易漏更新的一列。
        data = json.loads((ROOT / "modeling" / "data" / "03_output" / "baseline_vs_gbdt_14d.json")
                          .read_text(encoding="utf-8"))
        for method, metrics in data["metrics"].items():
            row = re.search(rf"\|\s*`?{method}`?[^|\n]*\|([^\n]*)", self.text)
            if row is None:
                continue
            cells = [cell.strip() for cell in row.group(1).split("|")]
            mae = cells[0].strip("*")
            regret = cells[2].strip("*")
            stockout = cells[3].strip("*").rstrip("%")
            self.assertEqual(f"{metrics['mae']:.2f}", mae, f"{method} 的 MAE 与产物不一致")
            self.assertEqual(f"{metrics['regret_per_100']:.2f}", regret, f"{method} 的 regret 与产物不一致")
            self.assertAlmostEqual(float(stockout), metrics["stockout_rate"] * 100, delta=0.05,
                                   msg=f"{method} 的缺货率与产物不一致")

    def test_plan_docx_carries_the_same_headline_numbers(self):
        # 计划书是给评委的另一份门面，口径必须与研究产物一致；缺库时跳过，不算失败。
        plan = ROOT.parent / "计划书" / "食刻有数_AIC算法创新赛计划书_竞赛适配完善版.docx"
        if not plan.exists():
            self.skipTest("计划书不在当前工作区")
        import zipfile
        with zipfile.ZipFile(plan) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", "", xml)
        data = json.loads((ROOT / "modeling" / "data" / "03_output" / "baseline_vs_gbdt_14d.json")
                          .read_text(encoding="utf-8"))
        pairs = {
            "稳健基线 MAE": f"{data['metrics']['median_roll7']['mae']:.2f}",
            "稳健基线 regret": f"{data['metrics']['median_roll7']['regret_per_100']:.2f}",
            "GBDT MAE": f"{data['metrics']['gbdt']['mae']:.2f}",
        }
        for label, value in pairs.items():
            self.assertIn(value, text, f"计划书缺少 {label} 的产物值 {value}")
        self.assertIn("不可声称", text, "计划书必须写明不可声称边界")

    def _sentence_around(self, needle: str) -> str:
        index = self.text.find(needle)
        start = max(self.text.rfind(ch, 0, index) for ch in "。！？\n") + 1
        ends = [self.text.find(ch, index) for ch in "。！？\n"]
        end = min((pos for pos in ends if pos != -1), default=len(self.text))
        return self.text[start:end]


if __name__ == "__main__":
    unittest.main()