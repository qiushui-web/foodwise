package org.foodwise.api;

import java.time.Instant;

public record ApiResponse<T>(boolean success, T data, String code, String message, String traceId, Instant timestamp) {
    public static <T> ApiResponse<T> success(T data, String traceId) {
        return new ApiResponse<>(true, data, null, null, traceId, Instant.now());
    }

    public static <T> ApiResponse<T> failure(String code, String message, String traceId) {
        return new ApiResponse<>(false, null, code, message, traceId, Instant.now());
    }
}

