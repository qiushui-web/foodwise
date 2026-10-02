package org.foodwise.model.dto;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 限时优惠活动
 */
public record OfferInfo(
    long id,
    long dishId,
    String title,
    String dishName,
    String status,
    String pickupLocation,
    BigDecimal originalPrice,
    BigDecimal offerPrice,
    int quantity,
    int soldCount,
    LocalDateTime startTime,
    LocalDateTime endTime,
    LocalDateTime createdAt
) {}

