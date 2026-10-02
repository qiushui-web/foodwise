package org.foodwise.model.dto;

import java.math.BigDecimal;

/**
 * 档口信息及其经营概况
 */
public record StallInfo(
    long id,
    String name,
    String category,
    String location,
    String managerName,
    String status,
    int rating,
    int dishCount,
    BigDecimal todayRevenue,
    BigDecimal todayLeftover
) {}

