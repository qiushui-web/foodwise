package org.foodwise.model.dto;

import java.math.BigDecimal;

/**
 * 菜品基础信息及历史平均表现
 */
public record DishInfo(
    long id,
    String name,
    String category,
    BigDecimal price,
    BigDecimal unitCost,
    int prepMinutes,
    boolean active,
    String color,
    String stallName,
    double avgSales,
    double leftoverRate
) {}

