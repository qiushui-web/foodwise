package org.foodwise.api;

import jakarta.servlet.http.HttpServletRequest;

public final class ApiIdempotency {
    private static final String HEADER = "Idempotency-Key";

    private ApiIdempotency() {}

    public static String require(HttpServletRequest request) {
        String key = request.getHeader(HEADER);
        if (key == null || key.isBlank() || key.length() > 120) {
            throw new ApiIdempotencyException("写请求必须提供有效的 Idempotency-Key");
        }
        return key;
    }
}

