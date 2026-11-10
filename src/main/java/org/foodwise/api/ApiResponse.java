package org.foodwise.api;

import java.time.OffsetDateTime;
import java.time.ZoneId;

/**
 * 统一响应外壳。时间戳固定带 +08:00 偏移：本产品只服务国内校园食堂，
 * 让前端拿到“看得懂的时间”比坚持输出 UTC 的 `Z` 更有用。
 */
public record ApiResponse<T>(boolean success, T data, String code, String message, String traceId,
                             OffsetDateTime timestamp) {

    public static final ZoneId SITE_ZONE = ZoneId.of("Asia/Shanghai");

    public static <T> ApiResponse<T> success(T data, String traceId) {
        return new ApiResponse<>(true, data, null, null, traceId, OffsetDateTime.now(SITE_ZONE));
    }

    public static <T> ApiResponse<T> failure(String code, String message, String traceId) {
        return new ApiResponse<>(false, null, code, message, traceId, OffsetDateTime.now(SITE_ZONE));
    }
}