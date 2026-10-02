package org.foodwise.model.dto;

import java.time.LocalDate;

/**
 * 菜品单日经营记录
 */
public record DishOperation(
    LocalDate businessDate,
    int preparedQty,
    int soldQty,
    int leftoverQty,
    int discountSoldQty,
    String weather,
    String eventTag
) {}

