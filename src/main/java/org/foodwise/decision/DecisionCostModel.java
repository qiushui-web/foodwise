package org.foodwise.decision;

/**
 * 单份成本结构与报童临界比。
 *
 * Cu（缺货损失）= (售价 − 有效成本) × (1 + 信任损失系数)
 * Co（剩余损失）= 有效成本 − 折价售价 × 可售概率
 * 临界比 ρ = Cu / (Cu + Co)，最优备餐量取需求分布的 ρ 分位。
 *
 * 制作损耗 lossRate：备 q 份，能上柜的只有 q·(1−λ_loss)；加工损耗的成本要摊到能卖的那部分上，
 * 所以有效单位成本 = 成本 / (1 − lossRate)。lossRate = 0 时退化为 v2 的口径，历史数字不变。
 */
public record DecisionCostModel(
        double price,
        double unitCost,
        double discountPrice,
        double salvageProbability,
        double shortageLambda,
        double lossRate
) {
    public static final double DEFAULT_DISCOUNT_RATIO = 0.5;
    public static final double DEFAULT_SALVAGE_PROBABILITY = 0.6;
    public static final double DEFAULT_SHORTAGE_LAMBDA = 0.3;
    public static final double DEFAULT_LOSS_RATE = 0.0;

    public DecisionCostModel {
        if (price <= 0) throw new IllegalArgumentException("PRICE_NOT_POSITIVE");
        if (unitCost <= 0 || unitCost >= price) throw new IllegalArgumentException("UNIT_COST_OUT_OF_RANGE");
        if (discountPrice < 0 || discountPrice > price) throw new IllegalArgumentException("DISCOUNT_PRICE_OUT_OF_RANGE");
        if (salvageProbability < 0 || salvageProbability > 1) {
            throw new IllegalArgumentException("SALVAGE_PROBABILITY_OUT_OF_RANGE");
        }
        if (shortageLambda < 0) throw new IllegalArgumentException("SHORTAGE_LAMBDA_NEGATIVE");
        if (lossRate < 0 || lossRate >= 0.9) throw new IllegalArgumentException("LOSS_RATE_OUT_OF_RANGE");
    }

    /** 无制作损耗的旧口径，保留给既有调用方与回归测试。 */
    public DecisionCostModel(double price, double unitCost, double discountPrice,
                             double salvageProbability, double shortageLambda) {
        this(price, unitCost, discountPrice, salvageProbability, shortageLambda, DEFAULT_LOSS_RATE);
    }

    public static DecisionCostModel defaults(double price, double unitCost) {
        return new DecisionCostModel(price, unitCost, price * DEFAULT_DISCOUNT_RATIO,
                DEFAULT_SALVAGE_PROBABILITY, DEFAULT_SHORTAGE_LAMBDA, DEFAULT_LOSS_RATE);
    }

    public static DecisionCostModel withLoss(double price, double unitCost, double lossRate) {
        return new DecisionCostModel(price, unitCost, price * DEFAULT_DISCOUNT_RATIO,
                DEFAULT_SALVAGE_PROBABILITY, DEFAULT_SHORTAGE_LAMBDA, lossRate);
    }

    /** 摊掉加工损耗之后的单位成本：为卖出 1 份，实际要投入 1/(1−loss) 份的料。 */
    public double effectiveUnitCost() {
        return unitCost / (1 - lossRate);
    }

    public double underage() {
        return (price - effectiveUnitCost()) * (1 + shortageLambda);
    }

    public double overage() {
        return effectiveUnitCost() - discountPrice * salvageProbability;
    }

    public double criticalRatio() {
        double over = overage();
        if (over <= 0) return 0.999; // 剩余越放越值钱：报童问题无界，压到上界
        double ratio = underage() / (underage() + over);
        return Math.min(Math.max(ratio, 0.01), 0.999);
    }

    /**
     * 后悔上界：在"真实最优量落在 [low, high] 内"的前提下，多备或少备每偏离 1 份，
     * 单期利润最多损失 max(上柜边际收益, 剩余边际损失)，于是
     * regret ≤ maxGainLoss × max(q − low, high − q)。
     *
     * 这是保守上界：区间越宽越松。它的用途是告诉用户"最坏能差多少"，不是预测实际差多少。
     */
    public double regretUpper(int quantity, double low, double high) {
        double sellable = 1 - lossRate;
        double gain = sellable * price - unitCost;
        double loss = unitCost - sellable * discountPrice * salvageProbability;
        double perUnit = Math.max(Math.max(gain, loss), 0);
        double distance = Math.max(quantity - low, high - quantity);
        return perUnit * Math.max(distance, 0);
    }

    /** 单期利润：备 prepared 份，能上柜 prepared×(1−loss)，收入 + 折价残值 − 备餐成本。 */
    public double profit(double prepared, double demand) {
        double available = prepared * (1 - lossRate);
        double sold = Math.min(available, demand);
        double leftover = Math.max(available - demand, 0);
        return sold * price + leftover * discountPrice * salvageProbability - prepared * unitCost;
    }
}