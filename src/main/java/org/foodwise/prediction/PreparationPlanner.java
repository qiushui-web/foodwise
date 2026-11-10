package org.foodwise.prediction;

import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;

/** Constraints apply to explicitly allocated servings for one dish and one meal. */
public final class PreparationPlanner {
    private PreparationPlanner() {}

    public record Inputs(Integer stockServings, Integer capacityServings, Integer minimumBatch,
                         Integer leadMinutes, LocalTime preparationStart,
                         LocalTime serviceStart, LocalTime serviceEnd) {
        public Inputs {
            if (stockServings == null || capacityServings == null || minimumBatch == null || leadMinutes == null
                    || preparationStart == null || serviceStart == null || serviceEnd == null)
                throw new IllegalArgumentException("请完整填写库存、产能、最小批量、提前期和营业时段");
            if (stockServings < 0 || capacityServings < 0 || stockServings > 1_000_000 || capacityServings > 1_000_000
                    || minimumBatch < 1 || minimumBatch > 10_000 || leadMinutes < 1 || leadMinutes > 240)
                throw new IllegalArgumentException("库存/产能须为0—1000000份，批量1—10000份，提前期1—240分钟");
            if (!serviceStart.isBefore(serviceEnd) || preparationStart.isAfter(serviceStart))
                throw new IllegalArgumentException("首批准备须不晚于开餐，结束须晚于开餐；跨日营业请拆分记录");
        }
    }

    public record Plan(int referenceDemand, int firstBatch, int replenishQty, int plannedTotal,
                       int uncoveredDemand, LocalTime latestReplenishStart,
                       boolean canReplenish, boolean automaticExecution, List<String> warnings) {}

    public static Plan plan(int demand, int referenceFirstBatch, Inputs input) {
        if (demand < 0 || referenceFirstBatch < 0) throw new IllegalArgumentException("预测数量不能为负");
        List<String> warnings = new ArrayList<>();
        int cap = Math.min(demand, Math.min(input.stockServings(), input.capacityServings()));
        int total = cap / input.minimumBatch() * input.minimumBatch();
        int first = total == 0 ? 0 : Math.min(total,
                Math.max(input.minimumBatch(), referenceFirstBatch / input.minimumBatch() * input.minimumBatch()));
        long firstReady = input.preparationStart().toSecondOfDay() + input.leadMinutes() * 60L;
        long latestStart = input.serviceEnd().toSecondOfDay() - input.leadMinutes() * 60L;
        boolean window = latestStart >= input.serviceStart().toSecondOfDay();
        if (firstReady > input.serviceStart().toSecondOfDay()) {
            total = first = 0;
            warnings.add("按填写的提前期，首批无法在开餐前完成；请调整准备时间或人工重新安排。");
        } else if (!window) {
            total = first;
            warnings.add("营业时段不足以完成第二批，不安排补餐。");
        }
        int refill = total - first;
        if (total < demand) warnings.add("库存、产能、整批或时段约束留下" + (demand - total) + "份参考需求缺口；该缺口不是实测缺货。");
        warnings.add("库存和产能为手工分配快照；补餐前必须复核售速、剩余、原料与食品安全，不自动执行。");
        return new Plan(demand, first, refill, total, demand - total,
                window ? LocalTime.ofSecondOfDay(latestStart) : null,
                window && refill > 0, false, List.copyOf(warnings));
    }
}
