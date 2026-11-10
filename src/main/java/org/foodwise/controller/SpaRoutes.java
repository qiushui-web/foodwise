package org.foodwise.controller;

import java.util.Set;

/**
 * 前端单页应用的已知路由。用于把不存在的前端路径返回 404，
 * 而不是让所有 /app/** 都以 200 返回同一个空壳（软 404）。
 *
 * 新增前端路由时必须同步这里，`SpaRoutesTests` 会比对路由表防止漏改。
 */
public final class SpaRoutes {

    private SpaRoutes() {
    }

    public static final Set<String> KNOWN = Set.of(
            "",
            "dashboard",
            "prediction",
            "orders",
            "stalls",
            "onboarding",
            "reports",
            "offers",
            "operation-feedback",
            "operations/feedback",
            "alerts",
            "insights/realtime",
            "insights/demand",
            "insights/waste",
            "about",
            "evidence"
    );

    public static boolean isKnown(String path) {
        if (path == null) return true;
        String normalized = path.trim();
        while (normalized.startsWith("/")) normalized = normalized.substring(1);
        while (normalized.endsWith("/")) normalized = normalized.substring(0, normalized.length() - 1);
        return KNOWN.contains(normalized);
    }
}