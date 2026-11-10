package org.foodwise.decision;

import jakarta.annotation.PostConstruct;
import org.foodwise.model.IntelligentAdvice;
import org.foodwise.model.PredictionResult;
import org.foodwise.prediction.CampusFeatureBuilder;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngine;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.PredictionPolicy;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.IntelligentDecisionService;
import org.foodwise.service.PredictionService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 校准分位决策引擎：CQR 区间 + 分层偏移 + 报童临界分位 → 建议备餐量。
 *
 * 与 rule 引擎的区别不是“更准”，而是把不确定性显式化：
 *  q05/q95 → 校准区间 → 成本临界比 → 建议量，每一步都能在页面上展开解释。
 *
 * 降级策略：模型/校准/清单任一哈希对不上，就整条链路回落到规则引擎，
 * 并在 factors 中写明原因，绝不输出“看起来已校准”的数字。
 */
@Service
public class CalibratedDecisionEngine implements PredictionEngine {

    public static final String KEY = "calibrated-quantile";
    private static final double Z_90 = 1.6448536269514722;
    private static final String MANIFEST_RESOURCE = "modeling/model_manifest.json";
    private static final String CALIBRATION_RESOURCE = "modeling/campus_interval_calibration.json";

    private final FoodwiseRepository repository;
    private final IntelligentDecisionService adviceService;
    private final PredictionService ruleEngine;
    private final DecisionRecorder recorder;

    @Value("${foodwise.decision.capacity:250}")
    private int capacity = 250;
    @Value("${foodwise.decision.minimum-batch:5}")
    private int minimumBatch = 5;

    private LightGbmTextModel lowerModel;
    private LightGbmTextModel upperModel;
    private IntervalCalibration calibration;
    private ModelManifest manifest;
    private String calibrationSha256;
    private volatile boolean ready;
    private volatile String unavailableReason = "NOT_INITIALIZED";

    public CalibratedDecisionEngine(FoodwiseRepository repository,
                                    IntelligentDecisionService adviceService,
                                    PredictionService ruleEngine,
                                    DecisionRecorder recorder) {
        this.repository = repository;
        this.adviceService = adviceService;
        this.ruleEngine = ruleEngine;
        this.recorder = recorder;
    }

    @PostConstruct
    public void init() {
        try {
            byte[] manifestBytes = resourceBytes(MANIFEST_RESOURCE);
            manifest = ModelManifest.parse(manifestBytes);
            if (!"calibrated-quantile".equals(manifest.modelKind())) {
                throw new IllegalStateException("MANIFEST_KIND_NOT_CALIBRATED:" + manifest.modelKind());
            }
            byte[] calibrationBytes = resourceBytes(CALIBRATION_RESOURCE);
            calibrationSha256 = IntervalCalibration.sha256(calibrationBytes);
            if (!calibrationSha256.equalsIgnoreCase(manifest.calibrationSha256())) {
                throw new IllegalStateException("CALIBRATION_HASH_MISMATCH");
            }
            calibration = IntervalCalibration.parse(calibrationBytes);
            for (Map.Entry<String, ModelManifest.QuantileModel> entry : manifest.quantileModels().entrySet()) {
                byte[] bytes = resourceBytes(entry.getValue().file());
                String actual = IntervalCalibration.sha256(bytes);
                if (!actual.equalsIgnoreCase(entry.getValue().sha256())) {
                    throw new IllegalStateException("QUANTILE_HASH_MISMATCH:" + entry.getKey());
                }
                LightGbmTextModel model = LightGbmTextModel.load(new ByteArrayInputStream(bytes), entry.getKey());
                if (entry.getKey().startsWith("0.05")) lowerModel = model;
                else if (entry.getKey().startsWith("0.95")) upperModel = model;
            }
            if (lowerModel == null || upperModel == null) {
                throw new IllegalStateException("QUANTILE_MODELS_INCOMPLETE");
            }
            ready = true;
            unavailableReason = null;
            System.out.println("[CalibratedDecisionEngine] 校准分位引擎就绪 model=" + manifest.modelVersion()
                    + " calibration=" + calibrationSha256.substring(0, 12)
                    + " strata=" + calibration.stratumOffsets().size());
        } catch (Exception e) {
            ready = false;
            unavailableReason = e.getClass().getSimpleName() + ":" + e.getMessage();
            System.err.println("[CalibratedDecisionEngine] 校准引擎不可用，降级规则引擎: " + unavailableReason);
        }
    }

    @Override
    public String key() {
        return KEY;
    }

    @Override
    public String modelVersion() {
        return ready && manifest != null ? manifest.modelVersion() : "rule-v1";
    }

    public boolean isReady() {
        return ready;
    }

    public String unavailableReason() {
        return unavailableReason;
    }

    @Override
    public PredictionEngineResult predict(PredictionContext context) {
        if (!ready) return fallback(context);
        Map<String, Object> dish = repository.dish(context.dishId());
        List<Integer> sales = repository.recentSales(context.dishId());
        double[] features = CampusFeatureBuilder.build(dish, sales, context.weather(), context.examWeek(),
                context.campusEvent(), context.targetDate());
        Computation computation = compute(features, dish, context.targetDate());
        long recordId = recorder.save(context.dishId(), context.targetDate(), context.mealPeriod(), context.weather(),
                context.examWeek(), context.campusEvent(), key(), manifest.modelVersion(), calibrationSha256,
                features, computation);
        PredictionResult result = toResult(context, dish, computation, recordId);
        return new PredictionEngineResult(key(), manifest.modelVersion(), result, Instant.now(), context.targetDate(),
                context.historyCutoff(), context.mealPeriod(), context.sourceNature(), null, sales.size(),
                context.predictionCutoffAt(), List.of(), null);
    }

    /** 只读预览：不落库，供计划页在用户确认前展示。 */
    public DecisionPreview preview(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                   LocalDate targetDate) {
        return preview(dishId, weather, examWeek, campusEvent, targetDate, null);
    }

    /** costOverride 只用于试算；落库路径仍用菜品主数据的成本参数，保证重放一致。 */
    public DecisionPreview preview(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                   LocalDate targetDate, DecisionCostModel costOverride) {
        if (!ready) {
            return new DecisionPreview(key(), "rule-v1", "unavailable", unavailableReason, targetDate,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, null,
                    List.of("校准产物不可用，已降级为规则引擎：" + unavailableReason));
        }
        Map<String, Object> dish = repository.dish(dishId);
        List<Integer> sales = repository.recentSales(dishId);
        double[] features = CampusFeatureBuilder.build(dish, sales, weather, examWeek, campusEvent, targetDate);
        Computation computation = compute(features, dish, targetDate, costOverride);
        DecisionCostModel cost = computation.cost();
        List<String> notes = new ArrayList<>();
        if (applyCalibration()) {
            notes.add("区间来自 CQR 校准（alpha=" + calibration.alpha() + "），偏移按 星期×品类 分层收缩。");
        } else {
            notes.add("未校准对照：直接使用分位模型原始输出，不做 CQR 偏移与位置校正。");
        }
        notes.add("建议量由成本临界比决定，可能落在统计区间之外；这是成本驱动而非模型越界。");
        if (computation.quantity() > computation.intervalHigh()) {
            notes.add("本次建议量高于区间上界：" + computation.quantity() + " > " + computation.intervalHigh() + "。");
        }
        if (computation.quantity() < computation.intervalLow()) {
            notes.add("本次建议量低于区间下界：" + computation.quantity() + " < " + computation.intervalLow() + "。");
        }
        double coverage = manifest.picp90() == null ? 0.9 : manifest.picp90();
        return new DecisionPreview(key(), manifest.modelVersion(), "ready", null, targetDate,
                computation.dayOfWeek(), computation.categoryId(),
                round(computation.q05(), 2), round(computation.q95(), 2), round(computation.offset(), 2),
                computation.intervalLow(), computation.intervalHigh(),
                round(computation.center(), 2), round(computation.sigma(), 2),
                round(computation.criticalRatio(), 4), round(cost.underage(), 2), round(cost.overage(), 2),
                computation.quantity(), computation.firstBatch(), computation.replenish(),
                round(cost.price(), 2), round(cost.unitCost(), 2),
                round(cost.lossRate(), 4), round(cost.effectiveUnitCost(), 2),
                round(cost.regretUpper(computation.quantity(), computation.intervalLow(), computation.intervalHigh()), 2),
                coverage,
                applyCalibration() ? calibration.method() : "quantile-raw", notes);
    }

    /** 重放：用留痕输入与当前产物重算，比对建议量是否仍一致。 */
    public ReplayReport replay(long recordId) {
        DecisionRecord record = recorder.find(recordId)
                .orElseThrow(() -> new IllegalArgumentException("DECISION_RECORD_NOT_FOUND:" + recordId));
        if (!ready) {
            return new ReplayReport(recordId, record.quantity(), -1, false, record.modelVersion(), "rule-v1",
                    record.calibrationSha256(), null, true,
                    List.of("校准引擎当前不可用：" + unavailableReason));
        }
        double q05 = lowerModel.predict(record.features());
        double q95 = upperModel.predict(record.features());
        if (q95 < q05) {
            double swap = q05;
            q05 = q95;
            q95 = swap;
        }
        double offset = applyCalibration() ? calibration.offsetFor(record.dayOfWeek(), record.categoryId()) : 0.0;
        double intervalLow = Math.max(0, q05 - offset);
        double intervalHigh = q95 + offset;
        double center = (q05 + q95) / 2.0 + (applyCalibration() ? calibration.bias() : 0.0);
        double sigma = Math.max((intervalHigh - intervalLow) / (2 * Z_90), 0.5);
        double raw = center + NormalQuantile.invCdf(record.costModel().criticalRatio()) * sigma;
        int quantity = batch(raw);
        boolean calibrationDrift = !calibrationSha256.equalsIgnoreCase(record.calibrationSha256());
        boolean modelDrift = !manifest.modelVersion().equals(record.modelVersion());
        List<String> notes = new ArrayList<>();
        if (modelDrift) notes.add("模型版本已从 " + record.modelVersion() + " 变为 " + manifest.modelVersion());
        if (calibrationDrift) notes.add("校准产物哈希已变化，重放结果只用于漂移检测");
        notes.add("区间 [" + Math.round(intervalLow) + ", " + Math.round(intervalHigh) + "]，临界比 "
                + round(record.costModel().criticalRatio(), 4));
        return new ReplayReport(recordId, record.quantity(), quantity, quantity == record.quantity(),
                record.modelVersion(), manifest.modelVersion(), record.calibrationSha256(), calibrationSha256,
                calibrationDrift || modelDrift, notes);
    }

    private PredictionEngineResult fallback(PredictionContext context) {
        PredictionResult base = ruleEngine.predict(context.dishId(), context.weather(),
                context.examWeek(), context.campusEvent());
        List<PredictionResult.Factor> factors = new ArrayList<>(base.factors());
        factors.add(new PredictionResult.Factor("校准引擎不可用",
                "已降级为规则引擎：" + unavailableReason, BigDecimal.ZERO, "calibration_unavailable"));
        PredictionResult degraded = new PredictionResult(base.predictionId(), base.dishId(), base.dishName(),
                base.predictedLow(), base.predictedMid(), base.predictedHigh(), base.firstBatch(),
                base.replenishQty(), base.stopHour(), base.stopMinute(), base.confidence(),
                base.soldOutRisk(), base.leftoverRisk(), factors, base.advice(),
                "rule-fallback", false, "heuristic_score_not_accuracy");
        return new PredictionEngineResult(key(), "rule-v1", degraded, Instant.now(), context.targetDate(),
                context.historyCutoff(), context.mealPeriod(), context.sourceNature(), null, 0,
                context.predictionCutoffAt(), List.of(), null);
    }

    private PredictionResult toResult(PredictionContext context, Map<String, Object> dish,
                                      Computation computation, long recordId) {
        DecisionCostModel cost = computation.cost();
        double coverage = manifest.picp90() == null ? 0.9 : manifest.picp90();
        BigDecimal confidence = BigDecimal.valueOf(coverage * 100).setScale(1, RoundingMode.HALF_UP);

        List<PredictionResult.Factor> factors = new ArrayList<>();
        factors.add(new PredictionResult.Factor("分位区间",
                "P5 " + Math.round(computation.q05()) + " 份、P95 " + Math.round(computation.q95())
                        + " 份，" + (applyCalibration() ? "分档校准偏移 " : "未校准偏移 0")
                        + round(computation.offset(), 2)
                        + " 份 → 区间 [" + computation.intervalLow() + ", " + computation.intervalHigh() + "]",
                BigDecimal.valueOf(computation.offset()).setScale(2, RoundingMode.HALF_UP), "interval"));
        factors.add(new PredictionResult.Factor("成本结构",
                "售价 " + round(cost.price(), 2) + " 元、成本 " + round(cost.unitCost(), 2)
                        + " 元；缺货损失 " + round(cost.underage(), 2) + " 元/份，剩余损失 "
                        + round(cost.overage(), 2) + " 元/份，临界比 " + round(computation.criticalRatio(), 3),
                BigDecimal.valueOf(computation.criticalRatio()).setScale(3, RoundingMode.HALF_UP), "cost"));
        factors.add(new PredictionResult.Factor("建议备餐",
                "成本感知建议 " + computation.quantity() + " 份（首锅 " + computation.firstBatch()
                        + "，补餐 " + computation.replenish() + "）",
                BigDecimal.valueOf(computation.quantity()), "decision"));
        factors.add(new PredictionResult.Factor(applyCalibration() ? "校准来源" : "对照说明",
                (applyCalibration()
                        ? "CQR + 分层 ACI（" + calibration.method() + "），PICP90 "
                        : "未校准分位直出，无 CQR/ACI（用于对照），标称 PICP90 ")
                        + round(coverage * 100, 1) + "%，模型版本 " + manifest.modelVersion(),
                BigDecimal.valueOf(coverage * 100).setScale(1, RoundingMode.HALF_UP), "calibration"));

        String dishName = String.valueOf(dish.getOrDefault("name", "菜品#" + context.dishId()));
        IntelligentAdvice advice = adviceService.predictionAdvice(dishName,
                computation.intervalLow(), computation.quantity(), computation.intervalHigh(),
                computation.firstBatch(), computation.replenish(),
                PredictionPolicy.STOP_HOUR, PredictionPolicy.STOP_MINUTE, confidence,
                context.weather(), context.examWeek(), context.campusEvent(),
                factors.stream().map(PredictionResult.Factor::detail).toList());

        return new PredictionResult(recordId, context.dishId(), dishName,
                computation.intervalLow(), computation.quantity(), computation.intervalHigh(),
                computation.firstBatch(), computation.replenish(),
                PredictionPolicy.STOP_HOUR, PredictionPolicy.STOP_MINUTE, confidence,
                computation.quantity() < computation.center() ? "中" : "低",
                computation.criticalRatio() < 0.8 ? "中" : "低",
                factors, advice, intervalMethod(), calibrated(), confidenceKind());
    }

    /** 是否套用 CQR 偏移与位置校正；对照引擎返回 false。 */
    protected boolean applyCalibration() {
        return true;
    }

    protected String intervalMethod() {
        return "cqr-stratified-aci";
    }

    protected boolean calibrated() {
        return true;
    }

    protected String confidenceKind() {
        return "interval_coverage_picp";
    }

    public Computation compute(double[] features, Map<String, Object> dish, LocalDate targetDate) {
        return compute(features, dish, targetDate, null);
    }

    public Computation compute(double[] features, Map<String, Object> dish, LocalDate targetDate,
                               DecisionCostModel costOverride) {
        double q05 = lowerModel.predict(features);
        double q95 = upperModel.predict(features);
        if (q95 < q05) {
            double swap = q05;
            q05 = q95;
            q95 = swap;
        }
        int dayOfWeek = CampusFeatureBuilder.dayOfWeek(targetDate);
        int categoryId = CampusFeatureBuilder.categoryId(dish);
        boolean calibrated = applyCalibration();
        double offset = calibrated ? calibration.offsetFor(dayOfWeek, categoryId) : 0.0;
        double intervalLow = Math.max(0, q05 - offset);
        double intervalHigh = q95 + offset;
        double center = (q05 + q95) / 2.0 + (calibrated ? calibration.bias() : 0.0);
        double sigma = Math.max((intervalHigh - intervalLow) / (2 * Z_90), 0.5);
        double price = ((Number) dish.get("price")).doubleValue();
        double unitCost = dish.get("unit_cost") instanceof Number n ? n.doubleValue() : price * 0.4;
        DecisionCostModel cost = costOverride != null ? costOverride
                : DecisionCostModel.defaults(price, unitCost);
        double ratio = cost.criticalRatio();
        double raw = center + NormalQuantile.invCdf(ratio) * sigma;
        int quantity = batch(raw);
        int firstBatch = Math.max(1, (int) Math.round(quantity * 0.82));
        int replenish = Math.max(0, quantity - firstBatch);
        return new Computation(q05, q95, offset, (int) Math.round(intervalLow), (int) Math.round(intervalHigh),
                center, sigma, cost, ratio, quantity, firstBatch, replenish, dayOfWeek, categoryId);
    }

    private int batch(double raw) {
        if (!Double.isFinite(raw)) return minimumBatch;
        int step = Math.max(1, minimumBatch);
        int rounded = (int) (Math.ceil(Math.max(raw, 0) / step) * step);
        return Math.min(Math.max(rounded, 0), Math.max(capacity, step));
    }

    private static double round(double value, int scale) {
        return BigDecimal.valueOf(value).setScale(scale, RoundingMode.HALF_UP).doubleValue();
    }

    private static byte[] resourceBytes(String path) throws IOException {
        try (InputStream input = new ClassPathResource(path).getInputStream()) {
            return input.readAllBytes();
        }
    }

    public record Computation(double q05, double q95, double offset, int intervalLow, int intervalHigh,
                              double center, double sigma, DecisionCostModel cost, double criticalRatio,
                              int quantity, int firstBatch, int replenish, int dayOfWeek, int categoryId) {
    }

    public record ReplayReport(long recordId, int recordedQuantity, int replayedQuantity, boolean match,
                               String recordedModelVersion, String currentModelVersion,
                               String recordedCalibrationSha256, String currentCalibrationSha256,
                               boolean drift, List<String> notes) {
    }
}
