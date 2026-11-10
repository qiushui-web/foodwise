package org.foodwise.prediction;

public record PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                String traceId, String idempotencyKey, String operatorName,
                                java.time.LocalDate targetDate, String mealPeriod, String sourceNature,
                                java.time.Instant predictionCutoffAt,
                                java.util.List<Long> selectedRevisionIds,
                                Long publicationWatermark, boolean explicitCutoff) {
    public PredictionContext {
        java.util.Objects.requireNonNull(targetDate, "targetDate");
        java.util.Objects.requireNonNull(predictionCutoffAt, "predictionCutoffAt");
        if (selectedRevisionIds != null) selectedRevisionIds = java.util.List.copyOf(selectedRevisionIds);
        if (predictionCutoffAt.isAfter(java.time.Instant.now()) ||
                predictionCutoffAt.atZone(java.time.ZoneId.of("Asia/Shanghai")).toLocalDate().isAfter(targetDate))
            throw new IllegalArgumentException("预测截止时刻不能晚于当前时刻或目标日期");
        if (!java.util.List.of("早餐", "午餐", "晚餐", "全日").contains(mealPeriod)) throw new IllegalArgumentException("餐次无效");
    }
    public PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                             String traceId, String idempotencyKey, String operatorName,
                             java.time.LocalDate targetDate, String mealPeriod, String sourceNature,
                             java.time.Instant predictionCutoffAt) {
        this(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey, operatorName,
                targetDate, mealPeriod, sourceNature, predictionCutoffAt, null, null, true);
    }
    public PredictionContext withSelectedRevisions(java.util.List<Long> ids) {
        return new PredictionContext(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey,
                operatorName, targetDate, mealPeriod, sourceNature, predictionCutoffAt, ids, publicationWatermark, explicitCutoff);
    }
    public PredictionContext withPublicationBoundary(long watermark, java.time.Instant observedAt) {
        if (watermark < 0) throw new IllegalArgumentException("台账发布边界无效");
        return new PredictionContext(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey,
                operatorName, targetDate, mealPeriod, sourceNature, observedAt, selectedRevisionIds, watermark, true);
    }
    public java.time.LocalDate historyCutoff() {
        var cutoff = targetDate.minusDays(1);
        var availableDay = predictionCutoffAt.atZone(java.time.ZoneId.of("Asia/Shanghai")).toLocalDate();
        return cutoff.isAfter(availableDay) ? availableDay : cutoff;
    }
    public PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                             String traceId, String idempotencyKey, String operatorName,
                             java.time.LocalDate targetDate, String mealPeriod, String sourceNature) {
        this(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey, operatorName,
                targetDate, mealPeriod, sourceNature,
                targetDate.isBefore(java.time.LocalDate.now(java.time.ZoneId.of("Asia/Shanghai")))
                        ? targetDate.atStartOfDay(java.time.ZoneId.of("Asia/Shanghai")).toInstant()
                        : java.time.Instant.now(), null, null, false);
    }
    public PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                             String traceId, String idempotencyKey, String operatorName) {
        this(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey, operatorName,
                java.time.LocalDate.now().plusDays(1), "全日", "经营台账；来源待逐笔核验");
    }
    public PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        this(dishId, weather, examWeek, campusEvent, "system", null, "system");
    }
}

