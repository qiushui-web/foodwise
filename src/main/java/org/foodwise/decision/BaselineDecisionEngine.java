package org.foodwise.decision;

import org.foodwise.model.PredictionResult;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngine;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.PredictionPolicy;
import org.foodwise.prediction.SalesObservation;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.IntelligentDecisionService;
import org.foodwise.service.PredictionService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * 分层稳健基线引擎（v3 部署链路）。
 *
 * 中心：同菜品同星期、最近四周售出量的中位数（不足则退回全窗口中位数）。
 * 尺度：历史残差的 90% 分位（保形思路），换算成正态尺度后参与报童解。
 * 全程只用台账里已经发生过的销量，不看天气/考试周等协变量——这是刻意的：
 * 14 天台账上 GBDT 输给中位数基线，与其保留一个说不清为什么更好的模型，不如留一个能手算的。
 */
@Service
public class BaselineDecisionEngine implements PredictionEngine {

    public static final String KEY = "robust-baseline";
    public static final String MODEL_VERSION = "baseline-v1";
    /** 没有校准产物可哈希，就哈希自己的参数配置：任何一处改动都会让重放提示漂移。 */
    public static final String CONFIG_SHA256 = configDigest();
    private static final double Z_90 = 1.6448536269514722;
    private static final int WINDOW_DAYS = 28;
    private static final int SAME_WEEKDAY_POINTS = 4;
    private static final int MIN_HISTORY = 5;

    private final FoodwiseRepository repository;
    private final IntelligentDecisionService adviceService;
    private final PredictionService ruleEngine;
    private final DecisionRecorder recorder;

    @Value("${foodwise.decision.capacity:250}")
    private int capacity = 250;
    @Value("${foodwise.decision.minimum-batch:5}")
    private int minimumBatch = 5;

    public BaselineDecisionEngine(FoodwiseRepository repository,
                                  IntelligentDecisionService adviceService,
                                  PredictionService ruleEngine,
                                  DecisionRecorder recorder) {
        this.repository = repository;
        this.adviceService = adviceService;
        this.ruleEngine = ruleEngine;
        this.recorder = recorder;
    }

    @Override
    public String key() {
        return KEY;
    }

    @Override
    public String modelVersion() {
        return MODEL_VERSION;
    }

    /** 一次基线决策的全部中间量。字段与校准引擎对齐，便于共用留痕与重放。 */
    public record Computation(double q05, double q95, double offset, int intervalLow, int intervalHigh,
                              double center, double sigma, DecisionCostModel cost, double criticalRatio,
                              int quantity, int firstBatch, int replenish, int dayOfWeek, int categoryId,
                              int historyDays, double empiricalCoverage, String unavailableReason) {
        public boolean available() {
            return unavailableReason == null;
        }
    }

    public Computation compute(long dishId, LocalDate targetDate) {
        return compute(dishId, targetDate, null);
    }

    public Computation compute(long dishId, LocalDate targetDate, DecisionCostModel override) {
        Map<String, Object> dish;
        try {
            dish = repository.dish(dishId);
        } catch (org.springframework.dao.EmptyResultDataAccessException notFound) {
            return unavailable(dishId, targetDate, "DISH_NOT_FOUND:" + dishId);
        }
        if (dish.isEmpty() || !(dish.get("price") instanceof Number priceNumber)) {
            return unavailable(dishId, targetDate, "DISH_NOT_FOUND:" + dishId);
        }
        List<SalesObservation> history = repository.recentSalesObservations(dishId, targetDate.minusDays(1), "全日",
                WINDOW_DAYS);
        if (history.size() < MIN_HISTORY) {
            return unavailable(dishId, targetDate, "INSUFFICIENT_HISTORY:" + history.size());
        }
        int dow = targetDate.getDayOfWeek().getValue();
        double center = sameWeekdayMedian(history, dow);
        double[] residuals = leaveOneOutResiduals(history);
        if (residuals.length == 0) {
            return unavailable(dishId, targetDate, "NO_RESIDUALS");
        }
        double halfWidth = quantile(Arrays.stream(residuals).map(Math::abs).toArray(), 0.90);
        double sigma = Math.max(halfWidth / Z_90, 0.5);
        long within = Arrays.stream(residuals).filter(r -> Math.abs(r) <= Z_90 * sigma).count();
        double coverage = (double) within / residuals.length;

        double price = priceNumber.doubleValue();
        double unitCost = dish.get("unit_cost") instanceof Number cost && cost.doubleValue() < price
                ? cost.doubleValue() : price * 0.4;
        DecisionCostModel cost = override != null ? override : DecisionCostModel.defaults(price, unitCost);
        double ratio = cost.criticalRatio();
        double raw = center + NormalQuantile.invCdf(ratio) * sigma;
        int quantity = batch(raw);
        int firstBatch = Math.max(1, (int) Math.round(quantity * 0.82));
        int replenish = Math.max(0, quantity - firstBatch);
        int intervalLow = (int) Math.round(Math.max(0, center - Z_90 * sigma));
        int intervalHigh = (int) Math.round(center + Z_90 * sigma);
        int categoryId = dish.get("category_id") instanceof Number category ? category.intValue() : 0;
        return new Computation(Math.max(0, center - Z_90 * sigma), center + Z_90 * sigma, 0.0,
                intervalLow, intervalHigh, center, sigma, cost, ratio, quantity, firstBatch, replenish,
                dow, categoryId, history.size(), coverage, null);
    }

    private Computation unavailable(long dishId, LocalDate targetDate, String reason) {
        double price = 13.0;
        DecisionCostModel cost = DecisionCostModel.defaults(price, price * 0.4);
        return new Computation(0, 0, 0, 0, 0, 0, 0, cost, cost.criticalRatio(), 0, 0, 0,
                targetDate.getDayOfWeek().getValue(), 0, 0, 0, reason);
    }

    public DecisionPreview preview(long dishId, LocalDate targetDate) {
        return preview(dishId, targetDate, null);
    }

    /** costOverride 只用于试算；落库路径仍用菜品主数据的成本参数。 */
    public DecisionPreview preview(long dishId, LocalDate targetDate, DecisionCostModel costOverride) {
        Computation c = compute(dishId, targetDate, costOverride);
        if (!c.available()) {
            return new DecisionPreview(KEY, MODEL_VERSION, "insufficient_history", c.unavailableReason(), targetDate,
                    c.dayOfWeek(), c.categoryId(), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "baseline-robust",
                    List.of("历史不足，无法给出基线建议：" + c.unavailableReason()));
        }
        List<String> notes = new ArrayList<>();
        notes.add("中心取同菜品同星期最近四周售出中位数；尺度取历史残差的 90% 分位（保形思路）。");
        notes.add("样本内覆盖 " + Math.round(c.empiricalCoverage() * 100) + "%（" + c.historyDays()
                + " 个营业日，属拟合内检验，不是独立回测）。");
        notes.add("建议量由成本临界比决定，可能落在区间之外；这是成本驱动而非模型越界。");
        if (c.quantity() > c.intervalHigh()) notes.add("本次建议量高于区间上界：" + c.quantity() + " > " + c.intervalHigh() + "。");
        return new DecisionPreview(KEY, MODEL_VERSION, "ready", null, targetDate, c.dayOfWeek(), c.categoryId(),
                round(c.q05(), 2), round(c.q95(), 2), 0.0, c.intervalLow(), c.intervalHigh(),
                round(c.center(), 2), round(c.sigma(), 2), round(c.criticalRatio(), 4),
                round(c.cost().underage(), 2), round(c.cost().overage(), 2),
                c.quantity(), c.firstBatch(), c.replenish(),
                round(c.cost().price(), 2), round(c.cost().unitCost(), 2),
                round(c.cost().lossRate(), 4), round(c.cost().effectiveUnitCost(), 2),
                round(c.cost().regretUpper(c.quantity(), c.intervalLow(), c.intervalHigh()), 2),
                round(c.empiricalCoverage(), 4),
                "baseline-robust", notes);
    }

    @Override
    public PredictionEngineResult predict(PredictionContext context) {
        Computation c = compute(context.dishId(), context.targetDate());
        if (!c.available()) return fallback(context, c.unavailableReason());
        long recordId = recorder.save(context.dishId(), context.targetDate(), context.mealPeriod(), context.weather(), context.examWeek(),
                context.campusEvent(), KEY, MODEL_VERSION, CONFIG_SHA256, new double[0],
                new CalibratedDecisionEngine.Computation(c.q05(), c.q95(), 0.0, c.intervalLow(), c.intervalHigh(),
                        c.center(), c.sigma(), c.cost(), c.criticalRatio(), c.quantity(), c.firstBatch(),
                        c.replenish(), c.dayOfWeek(), c.categoryId()));
        Map<String, Object> dish = repository.dish(context.dishId());
        String dishName = String.valueOf(dish.getOrDefault("name", "菜品#" + context.dishId()));
        List<PredictionResult.Factor> factors = new ArrayList<>();
        factors.add(new PredictionResult.Factor("基线中心",
                "同菜品同星期最近四周中位数 " + round(c.center(), 2) + " 份（" + c.historyDays() + " 个营业日）",
                BigDecimal.valueOf(c.center()).setScale(2, RoundingMode.HALF_UP), "baseline_center"));
        factors.add(new PredictionResult.Factor("残差尺度",
                "历史残差 90% 分位换算 σ = " + round(c.sigma(), 2) + " 份，样本内覆盖 "
                        + Math.round(c.empiricalCoverage() * 100) + "%",
                BigDecimal.valueOf(c.sigma()).setScale(2, RoundingMode.HALF_UP), "baseline_sigma"));
        factors.add(new PredictionResult.Factor("成本结构",
                "缺货 " + round(c.cost().underage(), 2) + " 元/份，剩余 " + round(c.cost().overage(), 2)
                        + " 元/份，临界比 " + round(c.criticalRatio(), 3),
                BigDecimal.valueOf(c.criticalRatio()).setScale(3, RoundingMode.HALF_UP), "cost"));
        factors.add(new PredictionResult.Factor("建议备餐",
                "成本感知建议 " + c.quantity() + " 份（首锅 " + c.firstBatch() + "，补餐 " + c.replenish() + "）",
                BigDecimal.valueOf(c.quantity()), "decision"));
        var advice = adviceService.predictionAdvice(dishName, c.intervalLow(), c.quantity(), c.intervalHigh(),
                c.firstBatch(), c.replenish(), PredictionPolicy.STOP_HOUR, PredictionPolicy.STOP_MINUTE,
                BigDecimal.valueOf(c.empiricalCoverage() * 100).setScale(1, RoundingMode.HALF_UP),
                context.weather(), context.examWeek(), context.campusEvent(),
                factors.stream().map(PredictionResult.Factor::detail).toList());
        PredictionResult result = new PredictionResult(recordId, context.dishId(), dishName,
                c.intervalLow(), c.quantity(), c.intervalHigh(), c.firstBatch(), c.replenish(),
                PredictionPolicy.STOP_HOUR, PredictionPolicy.STOP_MINUTE,
                BigDecimal.valueOf(c.empiricalCoverage() * 100).setScale(1, RoundingMode.HALF_UP),
                c.quantity() < c.center() ? "高" : "低", c.criticalRatio() < 0.8 ? "中" : "低",
                factors, advice, "baseline-robust-quantile", false, "in_sample_residual_coverage");
        return new PredictionEngineResult(KEY, MODEL_VERSION, result, Instant.now(), context.targetDate(),
                context.historyCutoff(), context.mealPeriod(), context.sourceNature(), null, c.historyDays(),
                context.predictionCutoffAt(), List.of(), null);
    }

    public CalibratedDecisionEngine.ReplayReport replay(long recordId) {
        DecisionRecord record = recorder.find(recordId)
                .orElseThrow(() -> new IllegalArgumentException("DECISION_RECORD_NOT_FOUND:" + recordId));
        Computation c = compute(record.dishId(), record.targetDate(), record.costModel());
        if (!c.available()) {
            return new CalibratedDecisionEngine.ReplayReport(recordId, record.quantity(), -1, false,
                    record.modelVersion(), MODEL_VERSION, record.calibrationSha256(), null, true,
                    List.of("当前台账不足以重放：" + c.unavailableReason()));
        }
        boolean modelDrift = !MODEL_VERSION.equals(record.modelVersion());
        List<String> notes = new ArrayList<>();
        if (modelDrift) notes.add("模型版本已从 " + record.modelVersion() + " 变为 " + MODEL_VERSION);
        notes.add("基线重放基于当前台账（" + c.historyDays() + " 个营业日），台账新增会让结果自然变化。");
        return new CalibratedDecisionEngine.ReplayReport(recordId, record.quantity(), c.quantity(),
                c.quantity() == record.quantity(), record.modelVersion(), MODEL_VERSION,
                record.calibrationSha256(), null, modelDrift, notes);
    }

    private PredictionEngineResult fallback(PredictionContext context, String reason) {
        PredictionResult base = ruleEngine.predict(context.dishId(), context.weather(),
                context.examWeek(), context.campusEvent());
        List<PredictionResult.Factor> factors = new ArrayList<>(base.factors());
        factors.add(new PredictionResult.Factor("基线引擎不可用", reason, BigDecimal.ZERO, "baseline_unavailable"));
        PredictionResult degraded = new PredictionResult(base.predictionId(), base.dishId(), base.dishName(),
                base.predictedLow(), base.predictedMid(), base.predictedHigh(), base.firstBatch(),
                base.replenishQty(), base.stopHour(), base.stopMinute(), base.confidence(),
                base.soldOutRisk(), base.leftoverRisk(), factors, base.advice(),
                "rule-fallback", false, "heuristic_score_not_accuracy");
        return new PredictionEngineResult(KEY, "rule-v1", degraded, Instant.now(), context.targetDate(),
                context.historyCutoff(), context.mealPeriod(), context.sourceNature(), null, 0,
                context.predictionCutoffAt(), List.of(), null);
    }

    static double sameWeekdayMedian(List<SalesObservation> history, int dayOfWeek) {
        int[] same = history.stream()
                .filter(o -> o.date().getDayOfWeek().getValue() == dayOfWeek)
                .limit(SAME_WEEKDAY_POINTS)
                .mapToInt(SalesObservation::sold)
                .toArray();
        if (same.length == 0) return median(history.stream().mapToInt(SalesObservation::sold).toArray());
        return median(same);
    }

    static double[] leaveOneOutResiduals(List<SalesObservation> history) {
        SalesObservation[] ordered = history.toArray(new SalesObservation[0]);
        Arrays.sort(ordered, (a, b) -> a.date().compareTo(b.date()));
        double[] residuals = new double[ordered.length];
        int count = 0;
        for (int i = 1; i < ordered.length; i++) {
            int dow = ordered[i].date().getDayOfWeek().getValue();
            List<SalesObservation> prior = new ArrayList<>();
            for (int j = i - 1; j >= 0 && prior.size() < SAME_WEEKDAY_POINTS; j--) {
                if (ordered[j].date().getDayOfWeek().getValue() == dow) prior.add(ordered[j]);
            }
            double center;
            if (!prior.isEmpty()) {
                center = median(prior.stream().mapToInt(SalesObservation::sold).toArray());
            } else {
                int[] before = new int[i];
                for (int k = 0; k < i; k++) before[k] = ordered[k].sold();
                center = median(before);
            }
            residuals[count++] = ordered[i].sold() - center;
        }
        return Arrays.copyOf(residuals, count);
    }

    static double median(int[] values) {
        if (values.length == 0) return 0;
        int[] sorted = values.clone();
        Arrays.sort(sorted);
        int mid = sorted.length / 2;
        return sorted.length % 2 == 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2.0;
    }

    static double quantile(double[] values, double q) {
        if (values.length == 0) return 0;
        double[] sorted = values.clone();
        Arrays.sort(sorted);
        double position = q * (sorted.length - 1);
        int lower = (int) Math.floor(position);
        int upper = (int) Math.ceil(position);
        if (lower == upper) return sorted[lower];
        return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
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

    private static String configDigest() {
        try {
            var digest = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(("robust-baseline|" + MODEL_VERSION + "|window=" + WINDOW_DAYS
                    + "|same_weekday=" + SAME_WEEKDAY_POINTS + "|q=0.90|z=" + Z_90).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(hash.length * 2);
            for (byte b : hash) builder.append(String.format("%02x", b));
            return builder.toString();
        } catch (java.security.NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA_256_UNAVAILABLE", impossible);
        }
    }
}
