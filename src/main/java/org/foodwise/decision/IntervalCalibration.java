package org.foodwise.decision;

import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 区间校准产物（campus_interval_calibration.json）的只读视图。
 *
 * 包含 CQR 偏移、分层收缩后的分档偏移与位置偏差。
 * 加载时强校验 sha256：产物被改写但清单未更新时拒绝启动校准引擎（降级为规则）。
 */
public final class IntervalCalibration {

    private final String method;
    private final double alpha;
    private final double kappa;
    private final double globalOffset;
    private final double bias;
    private final Map<String, Double> stratumOffsets;
    private final Map<String, Integer> stratumSizes;

    private IntervalCalibration(String method, double alpha, double kappa, double globalOffset, double bias,
                                Map<String, Double> stratumOffsets, Map<String, Integer> stratumSizes) {
        this.method = method;
        this.alpha = alpha;
        this.kappa = kappa;
        this.globalOffset = globalOffset;
        this.bias = bias;
        this.stratumOffsets = Map.copyOf(stratumOffsets);
        this.stratumSizes = Map.copyOf(stratumSizes);
    }

    @SuppressWarnings("unchecked")
    public static IntervalCalibration parse(byte[] json) throws IOException {
        Map<String, Object> root = new ObjectMapper()
                .readValue(new String(json, StandardCharsets.UTF_8), Map.class);
        Map<String, Double> offsets = new LinkedHashMap<>();
        Map<String, Integer> sizes = new LinkedHashMap<>();
        Object strata = root.get("strata");
        if (strata instanceof Map<?, ?> map) {
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                Map<String, Object> item = (Map<String, Object>) entry.getValue();
                String key = String.valueOf(entry.getKey());
                offsets.put(key, number(item.get("offset")));
                sizes.put(key, (int) number(item.get("n")));
            }
        }
        return new IntervalCalibration(
                string(root.get("method"), "cqr+stratified-aci"),
                number(root.get("alpha")),
                number(root.get("kappa")),
                number(root.get("global_offset")),
                number(root.get("bias")),
                offsets, sizes);
    }

    private static double number(Object value) {
        return value instanceof Number n ? n.doubleValue() : 0.0;
    }

    private static String string(Object value, String fallback) {
        return value == null ? fallback : String.valueOf(value);
    }

    /** 分档偏移；该档样本不足时回落到全局偏移。 */
    public double offsetFor(int dayOfWeek, int categoryId) {
        String key = stratumKey(dayOfWeek, categoryId);
        Double offset = stratumOffsets.get(key);
        if (offset == null || stratumSizes.getOrDefault(key, 0) < 5) return globalOffset;
        return offset;
    }

    public static String stratumKey(int dayOfWeek, int categoryId) {
        return dayOfWeek + "|" + categoryId;
    }

    public String method() {
        return method;
    }

    public double alpha() {
        return alpha;
    }

    public double kappa() {
        return kappa;
    }

    public double globalOffset() {
        return globalOffset;
    }

    public double bias() {
        return bias;
    }

    public Map<String, Double> stratumOffsets() {
        return stratumOffsets;
    }

    public int stratumSize(int dayOfWeek, int categoryId) {
        return stratumSizes.getOrDefault(stratumKey(dayOfWeek, categoryId), 0);
    }

    public static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA_256_UNAVAILABLE", e);
        }
    }
}