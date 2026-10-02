package org.foodwise.api;

import jakarta.servlet.http.HttpServletRequest;

import java.util.UUID;

public final class ApiTrace {
    private static final String HEADER = "X-Trace-Id";

    private ApiTrace() {
    }

    public static String id(HttpServletRequest request) {
        String value = request.getHeader(HEADER);
        return value == null || value.isBlank() ? UUID.randomUUID().toString() : value;
    }
}

