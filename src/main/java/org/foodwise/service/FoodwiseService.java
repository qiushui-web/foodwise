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

    public FoodwiseService(FoodwiseRepository repository) {
        this.repository = repository;
    }

    /**
     * 经营驾驶舱数据（保留 Map 形式兼容 Thymeleaf 模板）
     */
    @Cacheable(value = "dashboard", key = "'summary'")
    public Map<String, Object> dashboard() {
        Map<String, Object> data = new LinkedHashMap<>();
        DashboardSummary summary = repository.dashboardSummaryDto();
        List<OperationRow> rows = repository.operationRowsDto();

        long baselineLeftover = rows.stream()
                .filter(r -> "基线期".equals(r.phase()))
                .mapToInt(OperationRow::leftoverQty).sum();
        long interventionLeftover = rows.stream()
                .filter(r -> "干预期".equals(r.phase()))
                .mapToInt(OperationRow::leftoverQty).sum();
        long reducedPieces = Math.max(0L, baselineLeftover - interventionLeftover);
        double wasteWeightKg = reducedPieces * 0.3d;
        double annualFactor = 260d / 14d;
        long costSaved = Math.round(repository.reportSummaryDto().avoidedLoss().doubleValue() * annualFactor);
        long carbonSaved = Math.round(wasteWeightKg * 1.1d * annualFactor);
        long waterSaved = Math.round(wasteWeightKg * 250d * annualFactor);

        Map<String, Object> summaryMap = new LinkedHashMap<>();
        summaryMap.put("prepared", summary.prepared());
        summaryMap.put("sold", summary.sold());
        summaryMap.put("leftover", summary.leftover());
        summaryMap.put("rescued", summary.rescued());
        summaryMap.put("revenue", summary.revenue());
        summaryMap.put("accuracy", summary.accuracy());
        summaryMap.put("cost_saved", costSaved);
        summaryMap.put("carbon_saved", carbonSaved);
        summaryMap.put("water_saved", waterSaved);

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

    @Transactional
    public void verify(long orderId) {
        if (repository.verifyOrder(orderId, "档口操作员") != 1) {
            throw new IllegalStateException("订单不存在、已核销或当前状态不允许核销");
        }
    }

    // === DTO 快速查询方法（供 Controller 直接使用） ===

    public DashboardSummary getDashboardSummary() {
        DashboardSummary s = repository.dashboardSummaryDto();
        List<OperationRow> rows = repository.operationRowsDto();
        long bl = rows.stream().filter(r -> "基线期".equals(r.phase())).mapToInt(OperationRow::leftoverQty).sum();
        long il = rows.stream().filter(r -> "干预期".equals(r.phase())).mapToInt(OperationRow::leftoverQty).sum();
        long rp = Math.max(0L, bl - il);
        double ww = rp * 0.3d;
        double af = 260d / 14d;
        long cs = Math.round(repository.reportSummaryDto().avoidedLoss().doubleValue() * af);
        long cb = Math.round(ww * 1.1d * af);
        long ws = Math.round(ww * 250d * af);
        return new DashboardSummary(s.prepared(), s.sold(), s.leftover(), s.rescued(), s.revenue(), s.accuracy(), cs, cb, ws);
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



