package org.foodwise.model.dto;

import java.time.LocalDate;

public record LatestDishOperation(
        LocalDate businessDate,
        int preparedQty,
        int soldQty,
        int leftoverQty,
        int discountSoldQty,
        String weather,
        String eventTag
) {
}

