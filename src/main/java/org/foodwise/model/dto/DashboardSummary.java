package org.foodwise.model.dto;

import java.math.BigDecimal;

/**
 * 经营驾驶舱核心摘要数据
 */
public record DashboardSummary(
    int prepared,
    int sold,
    int leftover,
    int rescued,
    BigDecimal revenue,
    BigDecimal accuracy,
    long costSaved,
    long carbonSaved,
    long waterSaved
) {}

