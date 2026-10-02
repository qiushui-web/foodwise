package org.foodwise.model.dto;

import java.time.LocalDate;

/**
 * 经营趋势时间序列点
 */
public record TrendPoint(
    LocalDate businessDay,
    int prepared,
    int sold,
    int leftover,
    int rescued
) {}

