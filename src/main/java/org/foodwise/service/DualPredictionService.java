package org.foodwise.service;

import org.foodwise.model.PredictionResult;
import org.foodwise.prediction.CampusFeatureBuilder;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 双引擎预测：规则引擎（Java 四因子）与真实 LightGBM 训练模型并行预测，
 * 最终经营建议保持规则结果；派生标签模型仅用于对照，不参与未经验证的融合。
 * 返回的 Map 同时携带两条预测链路的数值与训练模型的逐特征决策归因，
 * 供前端做"训练模型 vs 规则"对比、决策路径可视化与大模型交叉解读，
 * 让"决策来自训练模型"这一点在界面上可核对、可追溯。
 */
@Service
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = "foodwise.prediction.experimental-enabled", havingValue = "true")
public class DualPredictionService {

    private final PredictionService predictionService;
    private final FoodwiseRepository repository;
    private final LgbmCampusModel lgbmModel;

    public DualPredictionService(PredictionService predictionService,
                                 FoodwiseRepository repository,
                                 LgbmCampusModel lgbmModel) {
        this.predictionService = predictionService;
        this.repository = repository;
        this.lgbmModel = lgbmModel;
    }

    public Map<String, Object> predictDual(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        // 1. 规则引擎预测（现有 PredictionService，四因子加权）
        PredictionResult rule = predictionService.predict(dishId, weather, examWeek, campusEvent);

        // 2. 真实训练模型预测
        Map<String, Object> dish = repository.dish(dishId);
        List<Integer> sales = repository.recentSales(dishId);
        Double lgbmSold = null;
        LgbmCampusModel.Explanation explanation = null;
        double[] features = CampusFeatureBuilder.build(dish, sales, weather, examWeek, campusEvent,
                LocalDate.now().plusDays(1));
        if (lgbmModel.isReady()) {
            lgbmSold = lgbmModel.predict(features);
            explanation = lgbmModel.explain(features);
        }

        int ruleMid = rule.predictedMid();
        int lgbmMid = lgbmSold == null ? ruleMid : (int) Math.round(lgbmSold);

        // This derived-label scenario model is comparison-only until observed-unit validation exists.
        int mid = rule.predictedMid();
        int low = rule.predictedLow();
        int high = rule.predictedHigh();
        int firstBatch = rule.firstBatch();
        int replenish = rule.replenishQty();

        // 4. 因子列表（规则因子 + 训练模型因子）
        List<PredictionResult.Factor> factors = new ArrayList<>(rule.factors());
        if (lgbmSold != null) {
            double deltaPct = (lgbmMid - ruleMid) * 100.0 / Math.max(1, ruleMid);
            factors.add(new PredictionResult.Factor(
                    "训练模型 LGBM",
                    lgbmModel.treeCount() + "棵回归树场景推理，预测 " + lgbmMid + " 份（派生目标演示，观测销量精度未验证）",
                    BigDecimal.valueOf(deltaPct).setScale(1, RoundingMode.HALF_UP),
                    "lgbm_trained"));
        } else {
            factors.add(new PredictionResult.Factor(
                    "训练模型 LGBM",
                    "模型运行时未就绪，当前采用规则引擎预测（模型文件 " + lgbmModel.trainedRows() + " 行训练）",
                    BigDecimal.ZERO, "lgbm_unavailable"));
        }

        BigDecimal confidence = rule.confidence();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("predictionId", rule.predictionId());
        result.put("comparisonOnly", true);
        result.put("dishId", dishId);
        result.put("dishName", rule.dishName());
        result.put("predictedLow", low);
        result.put("predictedMid", mid);
        result.put("predictedHigh", high);
        result.put("firstBatch", firstBatch);
        result.put("replenishQty", replenish);
        result.put("stopHour", rule.stopHour());
        result.put("stopMinute", rule.stopMinute());
        result.put("confidence", confidence);
        result.put("confidenceKind", "heuristic_score_not_accuracy");
        result.put("intervalMethod", "heuristic");
        result.put("intervalCalibrated", false);
        result.put("soldOutRisk", rule.soldOutRisk());
        result.put("leftoverRisk", rule.leftoverRisk());
        result.put("factors", factors);
        result.put("advice", rule.advice());
        // 双引擎对比字段
        result.put("rulePrediction", ruleMid);
        result.put("lgbmPrediction", lgbmSold == null ? null : lgbmMid);
        result.put("modelReady", lgbmModel.isReady());
        result.put("modelName", "LightGBM 场景模型（来源与泛化待核验）");
        result.put("modelMape", lgbmModel.backtestMape());
        result.put("trainedRows", lgbmModel.trainedRows());
        result.put("modelTrees", lgbmModel.treeCount());
        // 训练模型逐特征决策归因（决策来自训练的直接证据）
        if (explanation != null) {
            List<Map<String, Object>> contribs = new ArrayList<>();
            int topN = 0;
            for (LgbmCampusModel.Contribution c : explanation.getContributions()) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("feature", c.getFeature());
                row.put("featureZh", c.getFeatureZh());
                row.put("soldDelta", BigDecimal.valueOf(c.getSoldDelta()).setScale(1, RoundingMode.HALF_UP));
                row.put("splits", c.getSplits());
                row.put("direction", c.getSoldDelta() >= 0 ? "up" : "down");
                contribs.add(row);
                if (++topN >= 8) break;
            }
            result.put("decisionContributions", contribs);
            result.put("decisionRules", explanation.getTopRules());
            result.put("rawScore", BigDecimal.valueOf(explanation.getRawScore()).setScale(4, RoundingMode.HALF_UP));
        } else {
            result.put("decisionContributions", List.of());
            result.put("decisionRules", List.of());
        }
        return result;
    }
}