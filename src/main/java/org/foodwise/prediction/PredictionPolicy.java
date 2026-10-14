package org.foodwise.prediction;

/** Uncalibrated operating rules kept separate from model evidence and persistence. */
public final class PredictionPolicy {
    private PredictionPolicy() {}
    public static final int STOP_HOUR = 12;
    public static final int STOP_MINUTE = 18;
    public record Quantities(int low, int mid, int high, int firstBatch, int replenish) {}
    public static Quantities quantities(double demand) {
        if (!Double.isFinite(demand) || demand < 0) throw new IllegalArgumentException("需求必须为有限非负数");
        int mid = Math.max(1, (int) Math.round(demand));
        int low = Math.max(1, (int) Math.floor(mid * 0.92));
        int high = Math.max(mid + 1, (int) Math.ceil(mid * 1.08));
        int first = Math.max(1, (int) Math.round(low * 0.82));
        return new Quantities(low, mid, high, first, Math.max(0, mid - first));
    }
}
