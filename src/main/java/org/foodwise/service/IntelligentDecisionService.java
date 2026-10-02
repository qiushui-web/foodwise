package org.foodwise.service;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;
import org.foodwise.model.IntelligentAdvice;
import org.foodwise.model.OfferRecommendation;
import org.foodwise.model.dto.DishDetail;
import org.foodwise.model.dto.LatestDishOperation;
import org.foodwise.intelligence.Narrative;
import org.foodwise.intelligence.NarrativeProvider;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class IntelligentDecisionService {

    private final FoodwiseRepository repository;
    private final NarrativeProvider narrativeProvider;
    private final ObjectMapper objectMapper;

    public IntelligentDecisionService(FoodwiseRepository repository, NarrativeProvider narrativeProvider,
                                      ObjectMapper objectMapper) {
        this.repository = repository;
        this.narrativeProvider = narrativeProvider;
        this.objectMapper = objectMapper;
    }

    public IntelligentAdvice dashboardAdvice() {
        Map<String, Object> summary = repository.dashboardSummary();
        List<Map<String, Object>> risks = repository.riskDishes();
        double prepared = number(summary.get("prepared"));
        double sold = number(summary.get("sold"));
        double leftover = number(summary.get("leftover"));
        double leftoverRate = prepared == 0 ? 0 : leftover * 100 / prepared;
        long mediumHigh = risks.stream().filter(row -> !"低".equals(String.valueOf(row.get("risk_level")))).count();

        Map<String, Object> facts = new LinkedHashMap<>();
        facts.put("prepared", prepared);
        facts.put("sold", sold);
        facts.put("leftover", leftover);
        facts.put("leftoverRate", round(leftoverRate));
        facts.put("rescued", number(summary.get("rescued")));
        facts.put("mediumHighRiskDishes", mediumHigh);
        facts.put("topRiskDish", risks.isEmpty() ? "暂无" : risks.get(0).get("name"));

        long highRisk = risks.stream().filter(row -> "高".equals(String.valueOf(row.get("risk_level")))).count();
        String riskLevel = leftoverRate >= 10 || highRisk >= 2 ? "HIGH" : leftoverRate >= 6 || mediumHigh >= 2 ? "MEDIUM" : "LOW";
        String localSummary = leftoverRate >= 8
                ? "最近营业日剩余压力偏高，应优先控制高风险菜品首批备餐，并延后非必要补餐。"
                : "最近营业日供需整体稳定，可继续保持分批备餐，并重点跟踪少数高风险菜品。";
        List<String> reasons = new ArrayList<>();
        reasons.add("备餐" + integer(prepared) + "份，售出" + integer(sold) + "份，剩余率" + round(leftoverRate) + "%");
        reasons.add("当前共有" + mediumHigh + "个中高风险菜品");
        if (!risks.isEmpty()) reasons.add("剩余风险最高的是" + risks.get(0).get("name"));
        List<String> actions = List.of("先处理高风险菜品", "按销量节点决定是否补餐", "闭餐后记录采纳结果");
        return createAdvice("今日经营简报", "dashboard", facts, localSummary, riskLevel, reasons, actions,
                List.of("建议仅用于经营辅助，食品安全与现场动作由档口负责人确认"));
    }

    public IntelligentAdvice predictionAdvice(String dishName, int low, int mid, int high, int firstBatch,
                                                int replenish, int stopHour, int stopMinute, BigDecimal confidence,
                                                String weather, boolean examWeek, boolean campusEvent,
                                                List<String> factorDetails) {
        Map<String, Object> facts = new LinkedHashMap<>();
        facts.put("dishName", dishName);
        facts.put("predictedRange", List.of(low, high));
        facts.put("predictedMid", mid);
        facts.put("firstBatch", firstBatch);
        facts.put("replenishQty", replenish);
        facts.put("stopTime", "%02d:%02d".formatted(stopHour, stopMinute));
        facts.put("confidence", confidence);
        facts.put("weather", weather);
        facts.put("examWeek", examWeek);
        facts.put("campusEvent", campusEvent);
        facts.put("factors", factorDetails);

        String risk = confidence.doubleValue() < 78 ? "MEDIUM" : "LOW";
        String localSummary = dishName + "预计需求为" + low + "—" + high + "份，建议先准备" + firstBatch
                + "份，再根据实际销售决定是否补充" + replenish + "份。";
        List<String> reasons = new ArrayList<>(factorDetails);
        List<String> actions = List.of(
                "首批备餐控制在" + firstBatch + "份",
                "销售达到计划节点后再补充" + replenish + "份",
                "%02d:%02d后原则上停止继续制作".formatted(stopHour, stopMinute)
        );
        return createAdvice("备餐决策说明", "prediction", facts, localSummary, risk, reasons, actions,
                List.of("需求区间不是销量承诺，异常天气或活动需人工确认"));
    }

    public IntelligentAdvice reportAdvice() {
        Map<String, Object> report = repository.reportSummary();
        Map<String, Object> facts = new LinkedHashMap<>(report);
        double improvement = number(report.get("baseline_leftover_rate")) - number(report.get("intervention_leftover_rate"));
        String localSummary = "经营测算中，剩余率较基准阶段改善" + round(improvement)
                + "个百分点。下一周期应继续记录采纳、交付工时和增量毛利。";
        List<String> reasons = List.of(
                "剩余率由" + report.get("baseline_leftover_rate") + "%变为" + report.get("intervention_leftover_rate") + "%",
                "策略阶段建议执行率为" + report.get("adoption_rate") + "%",
                "优惠销售共记录" + report.get("rescued_meals") + "份"
        );
        return createAdvice("周期经营复盘", "report", facts, localSummary, "LOW", reasons,
                List.of("保留有效备餐参数", "复查未采纳建议原因", "用真实付费和交付工时校准商业价值"),
                List.of("当前结果属于经营测算，不替代真实档口连续台账"));
    }

    public OfferRecommendation recommendOffer(long dishId) {
        DishDetail dish = repository.dishDto(dishId);
        LatestDishOperation operation = repository.latestDishOperationDto(dishId);
        if (!LocalDate.now().equals(operation.businessDate())) {
            throw new IllegalArgumentException("缺少今天的经营记录，请先核对当餐剩余量");
        }
        int leftover = operation.leftoverQty();
        if (leftover <= 0) throw new IllegalArgumentException("今天该菜品暂无可优惠的剩余量");
        int sold = operation.soldQty();
        int prepared = operation.preparedQty();
        BigDecimal price = dish.price();
        BigDecimal unitCost = dish.unitCost();
        int qty = Math.max(1, Math.min(leftover, Math.max(3, (int) Math.ceil(prepared * 0.08))));
        int discountRate = leftover >= 7 ? 20 : leftover >= 4 ? 15 : 10;
        BigDecimal offerPrice = price.multiply(BigDecimal.valueOf(100 - discountRate))
                .divide(BigDecimal.valueOf(100), 1, RoundingMode.HALF_UP)
                .max(unitCost.multiply(BigDecimal.valueOf(1.15)).setScale(1, RoundingMode.HALF_UP));
        int recovered = Math.max(1, (int) Math.round(qty * (discountRate >= 20 ? 0.8 : 0.65)));
        LocalTime start = LocalTime.of(12, 20);
        LocalTime end = LocalTime.of(12, 45);

        Map<String, Object> facts = Map.of(
                "dishName", dish.name(), "prepared", prepared, "sold", sold, "leftover", leftover,
                "originalPrice", price, "recommendedPrice", offerPrice, "recommendedQty", qty,
                "startTime", start.toString(), "endTime", end.toString()
        );
        IntelligentAdvice advice = createAdvice("限时优惠建议", "offer", facts,
                "当前预计剩余" + leftover + "份，建议最多发布" + qty + "份限时优惠，并由档口确认餐品状态和截止时间。",
                leftover >= 7 ? "HIGH" : leftover >= 4 ? "MEDIUM" : "LOW",
                List.of("备餐" + prepared + "份，已售" + sold + "份", "优惠数量不超过当前预计剩余", "建议价格高于单位成本"),
                List.of("确认餐品状态", "按建议数量限量发布", "到达截止时间自动下架"),
                List.of("系统不判断餐品是否安全，发布前必须人工确认"));
        return new OfferRecommendation(dishId, dish.name(), qty, offerPrice, discountRate,
                start.format(DateTimeFormatter.ofPattern("HH:mm")), end.format(DateTimeFormatter.ofPattern("HH:mm")),
                recovered, offerPrice.multiply(BigDecimal.valueOf(recovered)), advice.riskLevel(), advice);
    }

    public void saveFeedback(long adviceId, boolean adopted, String adjustedValue, String rejectReason) {
        repository.saveAdviceFeedback(adviceId, adopted, adjustedValue, rejectReason);
    }

    private IntelligentAdvice createAdvice(String title, String scenario, Map<String, Object> facts,
                                            String localSummary, String riskLevel, List<String> localReasons,
                                            List<String> localActions, List<String> localWarnings) {
        Narrative narrative = narrativeProvider.generateNarrative(scenario, facts).orElse(null);
        boolean aiGenerated = narrative != null && !narrative.summary().isBlank();
        String summary = aiGenerated ? narrative.summary() : localSummary;
        List<String> reasons = localReasons;
        List<String> actionTexts = localActions;
        List<String> warnings = localWarnings;
        List<IntelligentAdvice.Action> actions = new ArrayList<>();
        for (int index = 0; index < actionTexts.size(); index++) {
            actions.add(new IntelligentAdvice.Action("ACTION_" + (index + 1), "建议" + (index + 1),
                    actionTexts.get(index), index == 0 ? "HIGH" : "MEDIUM"));
        }
        String source = aiGenerated ? "经营台账 · 规则校验 · 经营概括" : "经营台账 · 规则判断";
        long id = repository.saveAdvice(scenario, title, summary, riskLevel, source, aiGenerated,
                json(facts), json(Map.of("reasons", reasons, "actions", actions, "warnings", warnings)));
        return new IntelligentAdvice(id, title, summary, riskLevel, reasons, actions, warnings, source,
                aiGenerated, LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
    }

    private String json(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JacksonException exception) {
            return "{}";
        }
    }

    private double number(Object value) {
        return value instanceof Number number ? number.doubleValue() : value == null ? 0 : Double.parseDouble(String.valueOf(value));
    }

    private int integer(double value) {
        return (int) Math.round(value);
    }

    private double round(double value) {
        return Math.round(value * 10.0) / 10.0;
    }

    private BigDecimal decimal(Object value) {
        return value instanceof BigDecimal decimal ? decimal : new BigDecimal(String.valueOf(value));
    }
}

