package org.foodwise.api;

import java.util.List;

public record PageResponse<T>(List<T> items, int page, int size, long total, int totalPages) {
    public static <T> PageResponse<T> of(List<T> source, int page, int size) {
        int safePage = Math.max(1, page);
        int safeSize = Math.max(1, Math.min(100, size));
        int from = Math.min((safePage - 1) * safeSize, source.size());
        int to = Math.min(from + safeSize, source.size());
        long total = source.size();
        int totalPages = total == 0 ? 0 : (int) Math.ceil((double) total / safeSize);
        return new PageResponse<>(source.subList(from, to), safePage, safeSize, total, totalPages);
    }
}

