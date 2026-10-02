package org.foodwise.model.dto;

import java.math.BigDecimal;

/**
 * 校园场景数据系列（用于前端回测可视化）
 */
public record CampusSeries(
    String phase,
    long dishId,
    String dishName,
    String metric,
    BigDecimal value
) {}

