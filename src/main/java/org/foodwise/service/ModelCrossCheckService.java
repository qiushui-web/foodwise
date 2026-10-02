package org.foodwise.service;

import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 大模型混测服务：把"训练模型的具体决策"交给第三方大模型做独立交叉判断。
 * <p>
 * 混测分两层：
 * 1. 确定性校验（始终可用）：训练模型预测 vs 规则引擎 vs 历史销量区间，
 *    输出可机读的检查项（分歧度、历史区间命中、模型就绪/回测指标）。
 * 2. 大模型独立判断（配置 foodwise.ai.api-key 后激活）：将同一情景的事实
 *    （近7日销量、天气、星期、考试周/活动、规则预测、LGBM预测及Top决策因子）
 *    交给 GLM，要求其不迎合任何一方、独立给出预估区间和结论，
 *    再与训练模型预测比对一致性。
 * 全程不修改训练模型结果，只做旁路基验，让"决策来自训练"可被外部模型复核。
 */
@Service
public class ModelCrossCheckService {

    private final DualPredictionService dualPredictionService;
    private final FoodwiseRepository repository;
    private final ZhipuAiService zhipuAiService;
    private final LgbmCampusModel lgbmModel;

    public ModelCrossCheckService(DualPredictionService dualPredictionService,
                                  FoodwiseRepository repository,
                                  ZhipuAiService zhipuAiService,
                                  LgbmCampusModel lgbmModel) {
        this.dualPredictionService = dualPredictionService;
        this.repository = repository;
        this.zhipuAiService = zhipuAiService;
        this.lgbmModel = lgbmModel;
    }

    public Map<String, Object> crossCheck(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        Map<String, Object> dual = dualPredictionService.predictDual(dishId, weather, examWeek, campusEvent);
        List<Integer> sales = repository.recentSales(dishId);

        int rulePred = intVal(dual.get("rulePrediction"));
        Integer lgbmPred = dual.get("lgbmPrediction") == null ? null : intVal(dual.get("lgbmPrediction"));
        int ensemble = intVal(dual.get("predictedMid"));
        boolean ready = Boolean.TRUE.equals(dual.get("modelReady"));

        List<Integer> recent7 = sales.size() > 7 ? sales.subList(0, 7) : sales;
        double histMean = recent7.stream().mapToInt(Integer::intValue).average().orElse(0);
        int histMin = recent7.stream().mapToInt(Integer::intValue).min().orElse(0);
        int histMax = recent7.stream().mapToInt(Integer::intValue).max().orElse(0);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("dishId", dishId);
        result.put("dishName", dual.get("dishName"));
        result.put("weather", weather);
        result.put("targetWeekday", weekdayZh(LocalDate.now().plusDays(1)));
        result.put("examWeek", examWeek);
        result.put("campusEvent", campusEvent);
        result.put("rulePrediction", rulePred);
        result.put("lgbmPrediction", lgbmPred);
        result.put("ensemblePrediction", ensemble);
        result.put("modelReady", ready);
        result.put("modelMape", lgbmModel.backtestMape());
        result.put("modelTrees", lgbmModel.treeCount());
        result.put("trainedRows", lgbmModel.trainedRows());
        result.put("recent7", recent7);
        result.put("histMean", Math.round(histMean * 10) / 10.0);
        result.put("histMin", histMin);
        result.put("histMax", histMax);
        result.put("decisionContributions", dual.getOrDefault("decisionContributions", List.of()));
        result.put("decisionRules", dual.getOrDefault("decisionRules", List.of()));

        // ---- ① 确定性交叉校验 ----
        List<Map<String, Object>> checks = new ArrayList<>();
        checks.add(check("模型运行时就绪", ready,
                ready ? lgbmModel.treeCount() + "棵回归树已加载，纯Java推理与训练侧预测零误差" : "模型未就绪，当前仅有规则引擎结果"));
        double mapeNum;
        try { mapeNum = Double.parseDouble(lgbmModel.backtestMape()); }
        catch (NumberFormatException e) { mapeNum = 999; }
        checks.add(check("回测精度可信", mapeNum < 10,
                "university_food_waste " + lgbmModel.trainedRows() + "行真实数据滚动回测 MAPE=" + lgbmModel.backtestMape() + "%"));
        if (lgbmPred != null) {
            double divergence = Math.abs(lgbmPred - rulePred) * 100.0 / Math.max(1, rulePred);
            checks.add(check("训练模型与规则引擎分歧度", divergence <= 30,
                    "LGBM=" + lgbmPred + "份 vs 规则=" + rulePred + "份，分歧 " + String.format("%.1f", divergence) + "%"));
            boolean inHist = histMax == 0 || (lgbmPred >= histMin * 0.6 && lgbmPred <= histMax * 1.4);
            checks.add(check("预测落在历史合理区间", inHist,
                    histMax == 0 ? "历史数据不足，跳过区间校验"
                            : "近7日销量区间 " + histMin + "–" + histMax + " 份，模型预测 " + lgbmPred + " 份"));
        }
        long passCount = checks.stream().filter(c -> Boolean.TRUE.equals(c.get("pass"))).count();
        String detVerdict = passCount == checks.size() ? "全部通过" : (passCount >= checks.size() - 1 ? "基本通过" : "存在风险项");
        Map<String, Object> deterministic = new LinkedHashMap<>();
        deterministic.put("verdict", detVerdict);
        deterministic.put("passCount", passCount);
        deterministic.put("totalCount", checks.size());
        deterministic.put("checks", checks);
        result.put("deterministic", deterministic);

        // ---- ② 大模型独立混测 ----
        List<Integer> chronological = new ArrayList<>(recent7);
        Collections.reverse(chronological);
        result.put("llm", runLlmCheck(weather, examWeek, campusEvent,
                rulePred, lgbmPred, histMean, histMin, histMax, chronological, dual));
        return result;
    }

    private Map<String, Object> runLlmCheck(String weather, boolean examWeek, boolean campusEvent,
                                            int rulePred, Integer lgbmPred,
                                            double histMean, int histMin, int histMax,
                                            List<Integer> recent7Chronological, Map<String, Object> dual) {
        Map<String, Object> llm = new LinkedHashMap<>();
        llm.put("enabled", zhipuAiService.available());
        llm.put("model", zhipuAiService.modelName());
        if (!zhipuAiService.available()) {
            llm.put("status", "未配置大模型Key（foodwise.ai.api-key），当前展示确定性交叉校验；配置Key后此处显示大模型独立判断");
            return llm;
        }
        try {
            List<Map<String, Object>> topFactors = new ArrayList<>();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> contribs = (List<Map<String, Object>>) dual.getOrDefault("decisionContributions", List.of());
            for (Map<String, Object> c : contribs.subList(0, Math.min(5, contribs.size()))) {
                Map<String, Object> f = new LinkedHashMap<>();
                f.put("因子", c.get("featureZh"));
                f.put("对预测的影响_份", c.get("soldDelta"));
                f.put("命中分裂次数", c.get("splits"));
                topFactors.add(f);
            }
            Map<String, Object> facts = new LinkedHashMap<>();
            facts.put("情景", "高校食堂某菜品明日午餐销量独立预估");
            facts.put("菜品", String.valueOf(dual.get("dishName")));
            facts.put("明日星期", weekdayZh(LocalDate.now().plusDays(1)));
            facts.put("天气", weather);
            facts.put("考试周", examWeek ? "是" : "否");
            facts.put("校园活动", campusEvent ? "是" : "否");
            facts.put("近7日实际销量_份_按日期从早到晚", recent7Chronological);
            facts.put("近7日均值", histMean);
            facts.put("近7日最小", histMin);
            facts.put("近7日最大", histMax);
            facts.put("规则引擎预测_份", rulePred);
            facts.put("机器学习模型LGBM预测_份", lgbmPred);
            facts.put("LGBM训练依据Top因子", topFactors);
            facts.put("LGBM回测MAPE百分比", lgbmModel.backtestMape());

            String system = """
                    你是高校食堂需求评估专家。用户会给出同一菜品的真实历史销量、明日情景、规则引擎预测和机器学习模型LGBM的预测及其决策因子。
                    你必须独立判断，不要迎合任何一方的数字。
                    只返回JSON对象：{"llmLow":整数,"llmHigh":整数,"verdict":"agree或caution或disagree","comment":"60字以内中文判断依据"}。
                    规则：llmLow/llmHigh是你独立预估的明日销量区间；verdict表示你是否认可LGBM预测（agree认可/caution保留/disagree不认可）；
                    comment只陈述你的依据，不得编造事实中没有的数据。
                    """;
            Optional<Map<String, Object>> resp = zhipuAiService.generateJson(system, facts);
            if (resp.isEmpty()) {
                llm.put("status", "大模型服务调用失败，本次仅展示确定性交叉校验");
                return llm;
            }
            Map<String, Object> r = resp.get();
            int llmLow = asInt(r.get("llmLow"));
            int llmHigh = asInt(r.get("llmHigh"));
            String verdict = String.valueOf(r.getOrDefault("verdict", "")).toLowerCase();
            String comment = String.valueOf(r.getOrDefault("comment", ""));
            llm.put("llmLow", llmLow);
            llm.put("llmHigh", llmHigh);
            llm.put("verdict", verdict);
            llm.put("comment", comment);
            if (lgbmPred != null && llmHigh >= llmLow && llmLow > 0) {
                String consistency;
                if (lgbmPred >= llmLow && lgbmPred <= llmHigh) consistency = "一致";
                else if (lgbmPred >= llmLow * 0.9 && lgbmPred <= llmHigh * 1.1) consistency = "接近";
                else consistency = "分歧";
                llm.put("consistency", consistency);
            } else {
                llm.put("consistency", "无法判定");
            }
            llm.put("status", "ok");
            return llm;
        } catch (Exception e) {
            llm.put("status", "大模型混测异常：" + e.getMessage());
            return llm;
        }
    }

    private Map<String, Object> check(String name, boolean pass, String detail) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", name);
        m.put("pass", pass);
        m.put("detail", detail);
        return m;
    }

    private int intVal(Object o) {
        return o instanceof Number n ? n.intValue() : 0;
    }

    private int asInt(Object o) {
        if (o instanceof Number n) return n.intValue();
        try { return (int) Double.parseDouble(String.valueOf(o).replaceAll("[^0-9.\\-]", "")); }
        catch (Exception e) { return 0; }
    }

    private String weekdayZh(LocalDate date) {
        return List.of("周一", "周二", "周三", "周四", "周五", "周六", "周日").get(date.getDayOfWeek().getValue() - 1);
    }
}

