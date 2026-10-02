package org.foodwise.model.dto;

import java.math.BigDecimal;

public record DishDetail(
        long id,
        long stallId,
        String name,
        String category,
        BigDecimal price,
        BigDecimal unitCost,
        int prepMinutes,
        boolean active,
        String color,
        String stallName
) {
}

