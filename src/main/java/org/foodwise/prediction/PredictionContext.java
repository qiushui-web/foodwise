package org.foodwise.prediction;

public record PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                String traceId, String idempotencyKey, String operatorName) {
    public PredictionContext(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        this(dishId, weather, examWeek, campusEvent, "system", null, "system");
    }
}

