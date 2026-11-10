package org.foodwise.assistant;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;

/**
 * 参谋请求：菜品 + 问题 + 可选上下文。
 * 成本参数与"实际备餐/售出"都是可选的——不给就按引擎默认值，复盘则必须给。
 */
public record AssistantRequest(
        @Min(1) long dishId,
        @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate targetDate,
        @NotBlank String question,
        String weather,
        Boolean examWeek,
        Boolean campusEvent,
        Double price,
        Double unitCost,
        Integer actualPrepared,
        Integer actualSold
) {
}