package org.foodwise.model.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 数据元信息和校验结果
 */
public record DataMetadata(
    long records,
    long dishes,
    long stalls,
    long totalPrepared,
    long totalSold,
    long conservationViolations,
    long discountViolations,
    LocalDate minDate,
    LocalDate maxDate,
    String nature,
    String sourceLabel,
    String sources,
    String statement,
    double validationRate
) {}

