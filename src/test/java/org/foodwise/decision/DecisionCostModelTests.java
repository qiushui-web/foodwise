package org.foodwise.decision;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 制作损耗与后悔上界：两个数都要能被手算复核，否则用户没法信任。
 */
class DecisionCostModelTests {

    private static final double PRICE = 13.0;
    private static final double COST = 5.2;

    @Test
    void zeroLossKeepsTheV2Numbers() {
        DecisionCostModel cost = DecisionCostModel.defaults(PRICE, COST);
        assertEquals(5.2, cost.effectiveUnitCost(), 1e-9, "无损耗时有效成本就是成本");
        assertEquals(10.14, cost.underage(), 1e-6);
        assertEquals(1.3, cost.overage(), 1e-6);
        assertEquals(0.8864, cost.criticalRatio(), 1e-4);
        assertEquals(0.0, cost.lossRate(), 1e-9);
    }

    @Test
    void lossRaisesEffectiveCostAndLowersCriticalRatio() {
        DecisionCostModel noLoss = DecisionCostModel.defaults(PRICE, COST);
        DecisionCostModel withLoss = DecisionCostModel.withLoss(PRICE, COST, 0.05);

        assertEquals(5.2 / 0.95, withLoss.effectiveUnitCost(), 1e-9, "为卖 1 份要多投 1/(1−loss) 的料");
        assertTrue(withLoss.underage() < noLoss.underage(), "成本被摊高，缺货的边际收益变小");
        assertTrue(withLoss.overage() > noLoss.overage(), "剩下的每份更贵");
        assertTrue(withLoss.criticalRatio() < noLoss.criticalRatio(), "临界比因此下移");
    }

    @Test
    void lossShrinksTheSuggestedQuantity() {
        double center = 79.0;
        double sigma = 4.74;
        double without = center + NormalQuantile.invCdf(DecisionCostModel.defaults(PRICE, COST).criticalRatio()) * sigma;
        double with = center + NormalQuantile.invCdf(DecisionCostModel.withLoss(PRICE, COST, 0.10).criticalRatio()) * sigma;
        // 按最小批量 5 取整后两者可能都是 85，所以这里比的是取整前的建议量
        assertTrue(with < without, "同样中心与 σ，损耗越大建议量越小：" + with + " vs " + without);

        double wideCenter = 120.0;
        double wideSigma = 20.0;
        int withoutWide = (int) Math.ceil((wideCenter + NormalQuantile.invCdf(
                DecisionCostModel.defaults(PRICE, COST).criticalRatio()) * wideSigma) / 5) * 5;
        int withWide = (int) Math.ceil((wideCenter + NormalQuantile.invCdf(
                DecisionCostModel.withLoss(PRICE, COST, 0.10).criticalRatio()) * wideSigma) / 5) * 5;
        assertTrue(withWide < withoutWide, "σ 大时批量差异看得出来：" + withWide + " vs " + withoutWide);
    }

    @Test
    void regretUpperIsTheCostWeightedDistanceToTheInterval() {
        DecisionCostModel cost = DecisionCostModel.defaults(PRICE, COST);
        // 售价 13、成本 5.2：多备一份的机会损失 7.8，少备一份的剩余损失 1.3，取大的那个
        // 上界按"最优量可能落在区间任一侧"取最远距离，所以是 max(q−low, high−q)
        assertEquals(7.8 * 19, cost.regretUpper(90, 71, 87), 1e-6, "90 距下界 19 份");
        assertEquals(7.8 * 14, cost.regretUpper(85, 71, 87), 1e-6, "85 距下界 14 份");
        assertEquals(7.8 * 9, cost.regretUpper(80, 71, 87), 1e-6, "落在区间内也要按最远侧算上界");
    }

    @Test
    void regretUpperGrowsWithIntervalWidth() {
        DecisionCostModel cost = DecisionCostModel.defaults(PRICE, COST);
        double narrow = cost.regretUpper(80, 76, 84);
        double wide = cost.regretUpper(80, 64, 96);
        assertTrue(wide > narrow);
    }

    @Test
    void profitAccountsForTheLostUnits() {
        DecisionCostModel withLoss = DecisionCostModel.withLoss(PRICE, COST, 0.10);
        // 备 100 份、能上柜 90 份、需求 100：只卖出 90，且为 100 份付了料钱
        assertEquals(90 * PRICE - 100 * COST, withLoss.profit(100, 100), 1e-6);
    }

    @Test
    void invalidLossRateIsRejected() {
        assertThrows(IllegalArgumentException.class, () -> DecisionCostModel.withLoss(PRICE, COST, -0.1));
        assertThrows(IllegalArgumentException.class, () -> DecisionCostModel.withLoss(PRICE, COST, 0.95));
    }

    @Test
    void oldConstructorStillWorks() {
        DecisionCostModel legacy = new DecisionCostModel(PRICE, COST, 6.5, 0.6, 0.3);
        assertEquals(0.0, legacy.lossRate(), 1e-9);
        assertEquals(DecisionCostModel.defaults(PRICE, COST).criticalRatio(), legacy.criticalRatio(), 1e-9);
    }
}