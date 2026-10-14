package org.foodwise.prediction;

public record PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                String traceId, String idempotencyKey, String operatorName,
                                java.time.LocalDate targetDate, String mealPeriod, String sourceNature) {
    public PredictionContext {
        java.util.Objects.requireNonNull(targetDate, "targetDate");
        if (!java.util.List.of("早餐", "午餐", "晚餐", "全日").contains(mealPeriod)) throw new IllegalArgumentException("餐次无效");
    }
    public java.time.LocalDate historyCutoff() {
        var cutoff = targetDate.minusDays(1);
        return cutoff.isAfter(java.time.LocalDate.now()) ? java.time.LocalDate.now() : cutoff;
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

