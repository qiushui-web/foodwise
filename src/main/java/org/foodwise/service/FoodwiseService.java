package org.foodwise.service;

import org.foodwise.model.dto.*;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.*;

@Service
public class FoodwiseService {

    private final FoodwiseRepository repository;
    private final org.springframework.context.ApplicationEventPublisher events;

    public FoodwiseService(FoodwiseRepository repository, org.springframework.context.ApplicationEventPublisher events) {
        this.repository = repository;
        this.events = events;
    }

    /**
     * 经营驾驶舱数据（保留 Map 形式兼容 Thymeleaf 模板）
     */
    @Cacheable(value = "dashboard", key = "'summary'")
    public Map<String, Object> dashboard() {
        Map<String, Object> data = new LinkedHashMap<>();
        DashboardSummary summary = getDashboardSummary();
        Map<String, Object> summaryMap = new LinkedHashMap<>();
        summaryMap.put("prepared", summary.prepared());
        summaryMap.put("sold", summary.sold());
        summaryMap.put("leftover", summary.leftover());
        summaryMap.put("rescued", summary.rescued());
        summaryMap.put("revenue", summary.revenue());
        summaryMap.put("accuracy", summary.accuracy());
        summaryMap.put("cost_saved", summary.costSaved());
        summaryMap.put("carbon_saved", summary.carbonSaved());
        summaryMap.put("water_saved", summary.waterSaved());

        var trends = repository.trend();
        summaryMap.put("business_day", trends.isEmpty() ? "未提供" : trends.get(trends.size() - 1).get("business_day"));
        summaryMap.put("scenario_statement", "年化场景：260营业日/14日，0.3kg/份，1.1kg碳/kg，250L水/kg；非实测收益");
        data.put("summary", summaryMap);
        data.put("trend", repository.trend());
        data.put("risks", repository.riskDishes());
        data.put("offers", repository.offers());
        return data;
    }

    @Cacheable(value = "stalls")
    public List<Map<String, Object>> stalls() {
        return repository.stalls();
    }

    @Cacheable(value = "dishes")
    public List<Map<String, Object>> dishes() {
        return repository.dishes();
    }

    @Cacheable(value = "offers")
    public List<Map<String, Object>> offers() {
        return repository.offers();
    }

    public List<Map<String, Object>> orders() {
        return repository.orders();
    }

    public Map<String, Object> orderByPickupCode(String pickupCode) {
        if (pickupCode == null || !pickupCode.matches("[0-9]{6}")) {
            throw new IllegalArgumentException("请输入6位取餐码");
        }
        List<Map<String, Object>> matches = repository.orderByPickupCode(pickupCode);
        if (matches.isEmpty()) throw new IllegalArgumentException("未找到该取餐码，请核对后重试");
        return matches.get(0);
    }

    @Transactional
    @CacheEvict(value = {"offers", "dashboard"}, allEntries = true)
    public long createOffer(long dishId, int quantity, BigDecimal offerPrice, LocalTime startTime,
                            LocalTime endTime, boolean safetyConfirmed) {
        if (!safetyConfirmed) throw new IllegalArgumentException("发布前必须确认餐品仍处于当餐安全售卖时段");
        if (quantity <= 0) throw new IllegalArgumentException("优惠数量必须大于0");
        if (startTime == null || endTime == null || !endTime.isAfter(startTime)) {
            throw new IllegalArgumentException("优惠截止时间必须晚于开始时间");
        }
        if (!endTime.isAfter(LocalTime.now())) {
            throw new IllegalArgumentException("优惠截止时间已过，请重新选择当餐时段");
        }
        DishDetail dish = repository.dishDto(dishId);
        LatestDishOperation operation = repository.latestDishOperationDto(dishId);
        if (!LocalDate.now().equals(operation.businessDate())) {
            throw new IllegalArgumentException("缺少今天的经营记录，不能用历史剩余量发布优惠");
        }
        int leftover = operation.leftoverQty();
        if (leftover <= 0) throw new IllegalArgumentException("今天该菜品暂无可优惠的剩余量");
        if (quantity > leftover) throw new IllegalArgumentException("优惠数量不能超过当前剩余" + leftover + "份");
        BigDecimal originalPrice = dish.price();
        BigDecimal unitCost = dish.unitCost();
        if (offerPrice == null || offerPrice.compareTo(unitCost) < 0 || offerPrice.compareTo(originalPrice) >= 0) {
            throw new IllegalArgumentException("优惠价格应高于单位成本且低于原价");
        }
        LocalDate date = LocalDate.now();
        String title = dish.name() + " · 当餐限时优惠";
        String pickupLocation = dish.stallName();
        return repository.createOffer(dishId, title, originalPrice, offerPrice, quantity,
                LocalDateTime.of(date, startTime), LocalDateTime.of(date, endTime), pickupLocation);
    }

    public List<Map<String, Object>> alerts() {
        return repository.alerts();
    }

    public int pendingAlertCount() {
        return repository.pendingAlertCount();
    }

    @Transactional
    public void resolveAlert(long alertId) {
        if (repository.resolveAlert(alertId) != 1) {
            throw new IllegalStateException("预警不存在或已经处理");
        }
    }

    public void validatePredictionFeedback(long predictionId, long dishId, LocalDate date, String mealPeriod,
                                           boolean adopted, Integer adjustedQty, String reason) {
        var row = repository.predictionFeedbackContext(predictionId);
        var snapshot = new tools.jackson.databind.ObjectMapper().readTree(String.valueOf(row.get("input_json")));
        if (((Number) row.get("dish_id")).longValue() != dishId
                || !date.toString().equals(String.valueOf(row.get("target_date")))
                || !mealPeriod.equals(snapshot.path("mealPeriod").asText())) {
            throw new IllegalArgumentException("关联预测必须与当前菜品、日期和餐次一致");
        }
        if (adjustedQty == null || adjustedQty < 0) throw new IllegalArgumentException("请填写实际执行的建议量");
        if (row.get("constrained_total") instanceof Number limit && adjustedQty > limit.intValue())
            throw new IllegalArgumentException("执行量超过最近留档的现场约束计划；请核对库存产能后重新生成计划");
        if ((!adopted || adjustedQty != ((Number) row.get("predicted_mid")).intValue())
                && (reason == null || reason.isBlank())) {
            throw new IllegalArgumentException("调整或未采用建议时请填写原因");
        }
        if (reason != null && reason.length() > 300) throw new IllegalArgumentException("调整原因最多300字");
    }

    public void savePredictionFeedback(long predictionId, boolean adopted, Integer adjustedQty,
                                       String reason, String operatorName) {
        if (!adopted && (reason == null || reason.isBlank())) {
            throw new IllegalArgumentException("拒绝预测建议时请填写原因");
        }
        repository.savePredictionFeedback(predictionId, adopted, adjustedQty, reason, operatorName);
    }

    public byte[] exportOperationsCsv() {
        StringBuilder csv = new StringBuilder("\uFEFF营业日期,餐次,档口,菜品,数据阶段,建议备餐,实际备餐,售出,优惠售出,闭餐剩余,收入,天气,现场情况,是否采用建议\r\n");
        for (Map<String, Object> row : repository.operationExportRows()) {
            csv.append(csvCell(row.get("business_date"))).append(',')
                    .append(csvCell(row.get("meal_period"))).append(',')
                    .append(csvCell(row.get("stall_name"))).append(',')
                    .append(csvCell(row.get("dish_name"))).append(',')
                    .append(csvCell(row.get("phase"))).append(',')
                    .append(csvCell(row.get("planned_qty"))).append(',')
                    .append(csvCell(row.get("prepared_qty"))).append(',')
                    .append(csvCell(row.get("sold_qty"))).append(',')
                    .append(csvCell(row.get("discount_sold_qty"))).append(',')
                    .append(csvCell(row.get("leftover_qty"))).append(',')
                    .append(csvCell(row.get("revenue"))).append(',')
                    .append(csvCell(row.get("weather"))).append(',')
                    .append(csvCell(row.get("event_tag"))).append(',')
                    .append(Boolean.TRUE.equals(row.get("recommendation_adopted")) ? "是" : "否")
                    .append("\r\n");
        }
        return csv.toString().getBytes(StandardCharsets.UTF_8);
    }

    private String csvCell(Object value) {
        String text = value == null ? "" : String.valueOf(value);
        return '"' + text.replace("\"", "\"\"") + '"';
    }

    @Cacheable(value = "dashboard", key = "'report'")
    public Map<String, Object> report() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("summary", repository.reportSummary());
        data.put("trend", repository.trend());
        data.put("dishes", repository.dishes());
        return data;
    }

    public List<Map<String, Object>> predictionReviews() { return repository.predictionReviews(); }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> sourceEvidenceRecords() { return repository.sourceEvidenceRecords(); }

    /**
     * 首次入驻前的可审计检查。演示种子数据只说明页面可运行，不会被解释为学校已完成入驻。
     */
    @Transactional(readOnly = true)
    public Map<String, Object> onboardingReadiness() {
        List<StallInfo> stalls = getStalls();
        List<DishInfo> dishes = getDishes();
        List<Map<String, Object>> evidence = repository.sourceEvidenceRecords();
        long unverified = evidence.stream()
                .filter(row -> "DECLARED_UNVERIFIED".equals(String.valueOf(row.get("verification_status"))))
                .count();
        List<Map<String, Object>> checks = new ArrayList<>();
        checks.add(check("学校身份与数据授权", false,
                "学校资料可通过首次建档登记；学校身份、授权材料及数据用途仍需人工核验，保存建档不会自动通过本项。"));
        checks.add(check("档口建档", !stalls.isEmpty(), stalls.isEmpty()
                ? "至少建立一个档口，并核对地点、负责人和营业状态。"
                : "已发现 " + stalls.size() + " 个档口；请确认它们不是演示种子。"));
        boolean dishesReady = !dishes.isEmpty() && dishes.stream().allMatch(d -> d.name() != null && !d.name().isBlank()
                && "份".equals(d.quantityUnit()));
        checks.add(check("菜品与单位口径", dishesReady,
                dishesReady ? "已有菜品且预测计量单位统一为份。" : "至少建立一个菜品，并确认首版预测计量单位统一为份。"));
        checks.add(check("来源与授权核验", !evidence.isEmpty() && unverified == 0,
                evidence.isEmpty() ? "尚未登记原始台账来源。" : "已有 " + evidence.size() + " 条来源登记，其中 " + unverified + " 条仍待人工核验。"));
        checks.add(check("训练准入", false,
                "来源核验、有效样本、时间切分、独立校准和 Python-Java 对照全部通过后才能训练校园模型。"));
        boolean ready = checks.stream().allMatch(row -> Boolean.TRUE.equals(row.get("passed")));
        return Map.of("ready", ready, "checks", checks, "counts", Map.of(
                "stalls", stalls.size(), "dishes", dishes.size(), "sourceEvidence", evidence.size(), "unverifiedSources", unverified));
    }

    private Map<String, Object> check(String name, boolean passed, String detail) {
        return Map.of("name", name, "passed", passed, "detail", detail);
    }

    @Transactional
    public Map<String, Object> onboard(OnboardingRequest request) {
        if (!"份".equals(request.quantityUnit())) {
            throw new IllegalArgumentException("首版只接受“份”作为预测计量单位；其他单位请先建立换算规则");
        }
        if (request.price().compareTo(request.unitCost()) < 0) {
            throw new IllegalArgumentException("售价不能低于单位成本，请核对口径");
        }
        long schoolId = repository.upsertSchoolProfile(request.schoolName(), request.schoolCode(),
                request.authorizationReference(), request.dataPurpose(), request.retentionPeriod(), request.operatorName());
        long stallId = repository.createStall(request.stallName(), request.stallCategory(), request.location(), request.managerName());
        long dishId = repository.createDish(stallId, request.dishName(), request.dishCategory(), request.price(),
                request.unitCost(), request.prepMinutes(), request.quantityUnit());
        events.publishEvent(new OperationDataChanged(dishId));
        return Map.of("schoolId", schoolId, "stallId", stallId, "dishId", dishId,
                "verificationStatus", "DECLARED_UNVERIFIED",
                "message", "建档完成；学校授权、地域和原始台账仍需人工核验后才能进入训练");
    }

    public record OnboardingRequest(String schoolName, String schoolCode, String authorizationReference,
                                    String dataPurpose, String retentionPeriod, String stallName,
                                    String stallCategory, String location, String managerName,
                                    String dishName, String dishCategory, BigDecimal price,
                                    BigDecimal unitCost, int prepMinutes, String quantityUnit,
                                    String operatorName) {}

    @Transactional(readOnly = true)
    public Map<String, Object> replayPredictionInputs(long predictionId) { return repository.replayPredictionInputs(predictionId); }

    @Transactional
    public void verify(long orderId) {
        if (repository.verifyOrder(orderId, "档口操作员") != 1) {
            throw new IllegalStateException("订单不存在、已核销或当前状态不允许核销");
        }
    }

    // === DTO 快速查询方法（供 Controller 直接使用） ===

    public DashboardSummary getDashboardSummary() {
        return SummaryCalculator.calculate(repository.dashboardSummaryDto(), repository.operationRowsDto(),
                repository.reportSummaryDto().avoidedLoss());
    }

    @Cacheable(value = "stalls", key = "'dto'")
    public List<StallInfo> getStalls() {
        return repository.stallsDto();
    }

    @Cacheable(value = "dishes", key = "'dto'")
    public List<DishInfo> getDishes() {
        return repository.dishesDto();
    }

    public List<TrendPoint> getTrend() {
        return repository.trendDto();
    }

    public ReportSummary getReportSummary() {
        return repository.reportSummaryDto();
    }

    public List<OperationRow> getOperationRows() {
        return repository.operationRowsDto();
    }
}



