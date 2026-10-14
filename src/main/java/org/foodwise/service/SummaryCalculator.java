package org.foodwise.service;

import org.foodwise.model.dto.DashboardSummary;
import org.foodwise.model.dto.OperationRow;
import java.math.BigDecimal;
import java.util.List;

/** Scenario estimates under explicit assumptions, not measured environmental savings. */
public final class SummaryCalculator {
    private SummaryCalculator() {}
    public static final double ANNUAL_DAYS = 260;
    public static final double SAMPLE_DAYS = 14;
    public static DashboardSummary calculate(DashboardSummary input, List<OperationRow> rows, BigDecimal avoidedLoss) {
        long baseline = rows.stream().filter(r -> "基线期".equals(r.phase())).mapToLong(OperationRow::leftoverQty).sum();
        long intervention = rows.stream().filter(r -> "干预期".equals(r.phase())).mapToLong(OperationRow::leftoverQty).sum();
        double estimatedWeight = Math.max(0, baseline - intervention) * 0.3;
        double annual = ANNUAL_DAYS / SAMPLE_DAYS;
        return new DashboardSummary(input.prepared(), input.sold(), input.leftover(), input.rescued(),
                input.revenue(), input.accuracy(), Math.round(avoidedLoss.doubleValue() * annual),
                Math.round(estimatedWeight * 1.1 * annual), Math.round(estimatedWeight * 250 * annual));
    }
}
