package org.foodwise.model.dto;

import java.time.LocalDateTime;

/**
 * 经营预警记录
 */
public record AlertInfo(
    long id,
    long dishId,
    String dishName,
    String stallName,
    String alertType,
    String riskLevel,
    String status,
    String message,
    String suggestion,
    LocalDateTime createdAt,
    int currentLeftover,
    int threshold
) {}

