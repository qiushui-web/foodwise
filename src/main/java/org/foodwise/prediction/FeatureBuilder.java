package org.foodwise.prediction;

import java.util.List;

/** Rule features for dated observed business records; not the experimental LightGBM contract. */
public final class FeatureBuilder {
    private FeatureBuilder() {}
    public record Features(double weightedDemand, double trend, double variability, int observations) {}
    public static Features build(List<SalesObservation> newestFirst) {
        if (newestFirst.isEmpty()) throw new IllegalArgumentException("该菜品暂无所选餐次的历史销量");
        double total = 0, weights = 0;
        for (int index = 0; index < newestFirst.size(); index++) {
            double weight = newestFirst.size() - index;
            total += newestFirst.get(index).sold() * weight; weights += weight;
        }
        double trend = 1;
        if (newestFirst.size() >= 4) {
            int recentCount = newestFirst.size() - newestFirst.size() / 2;
            double recent = newestFirst.subList(0, recentCount).stream().mapToInt(SalesObservation::sold).average().orElse(0);
            double early = newestFirst.subList(recentCount, newestFirst.size()).stream().mapToInt(SalesObservation::sold).average().orElse(0);
            trend = early == 0 ? (recent == 0 ? 1 : 1.08) : Math.max(0.92, Math.min(1.08, recent / early));
        }
        double mean = newestFirst.stream().mapToInt(SalesObservation::sold).average().orElse(0);
        double variance = newestFirst.stream().mapToDouble(p -> Math.pow(p.sold() - mean, 2)).average().orElse(0);
        double variability = mean == 0 ? 19 : Math.min(19, Math.sqrt(variance) / mean * 100);
        return new Features(total / weights, trend, variability, newestFirst.size());
    }
}
