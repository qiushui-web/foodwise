package org.foodwise.model.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 经营台账单行数据（用于 CSV 导出和分析）
 */
public record OperationRow(
    long dishId,
    long operationId,
    String stallName,
    String dishName,
    String phase,
    String weather,
    String eventTag,
    int plannedQty,
    int preparedQty,
    int soldQty,
    int discountSoldQty,
    int leftoverQty,
    BigDecimal revenue,
    LocalDate businessDate,
    boolean recommendationAdopted
) {}

