package org.foodwise.decision;

import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 模型清单（model_manifest.json）的只读视图。
 *
 * Java 侧只读取运行时真正需要的字段：模型版本、分位模型文件与哈希、校准产物哈希、
 * 覆盖率指标。清单的权威校验仍在 Python（30_verify_manifest.py），Java 只做“文件是否被替换”的校验。
 */
public final class ModelManifest {

    public record QuantileModel(String file, String sha256) {
    }

    private final String schemaVersion;
    private final String modelVersion;
    private final String modelKind;
    private final Map<String, QuantileModel> quantileModels;
    private final String calibrationArtifact;
    private final String calibrationSha256;
    private final String calibrationMethod;
    private final Double picp90;
    private final Double pinaw90;

    private ModelManifest(String schemaVersion, String modelVersion, String modelKind,
                          Map<String, QuantileModel> quantileModels, String calibrationArtifact,
                          String calibrationSha256, String calibrationMethod,
                          Double picp90, Double pinaw90) {
        this.schemaVersion = schemaVersion;
        this.modelVersion = modelVersion;
        this.modelKind = modelKind;
        this.quantileModels = Map.copyOf(quantileModels);
        this.calibrationArtifact = calibrationArtifact;
        this.calibrationSha256 = calibrationSha256;
        this.calibrationMethod = calibrationMethod;
        this.picp90 = picp90;
        this.pinaw90 = pinaw90;
    }

    @SuppressWarnings("unchecked")
    public static ModelManifest parse(byte[] json) throws IOException {
        Map<String, Object> root = new ObjectMapper()
                .readValue(new String(json, StandardCharsets.UTF_8), Map.class);
        Map<String, QuantileModel> quantiles = new LinkedHashMap<>();
        Map<String, Object> quantileNode = asMap(root.get("quantile_models"));
        for (Map.Entry<String, Object> entry : quantileNode.entrySet()) {
            Map<String, Object> item = asMap(entry.getValue());
            quantiles.put(entry.getKey(), new QuantileModel(asString(item.get("file")), asString(item.get("sha256"))));
        }
        Map<String, Object> calibration = asMap(root.get("calibration"));
        Map<String, Object> metrics = asMap(root.get("metrics"));
        return new ModelManifest(
                asString(root.get("schema_version"), "1"),
                asString(root.get("model_version"), "unknown"),
                asString(root.get("model_kind"), "point"),
                quantiles,
                asString(calibration.get("artifact")),
                asString(calibration.get("artifact_sha256")),
                asString(calibration.get("method")),
                asDouble(metrics.get("picp90")),
                asDouble(metrics.get("pinaw90")));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private static String asString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static String asString(Object value, String fallback) {
        return value == null ? fallback : String.valueOf(value);
    }

    private static Double asDouble(Object value) {
        return value instanceof Number number ? number.doubleValue() : null;
    }

    public String schemaVersion() {
        return schemaVersion;
    }

    public String modelVersion() {
        return modelVersion;
    }

    public String modelKind() {
        return modelKind;
    }

    public Map<String, QuantileModel> quantileModels() {
        return quantileModels;
    }

    public String calibrationArtifact() {
        return calibrationArtifact;
    }

    public String calibrationSha256() {
        return calibrationSha256;
    }

    public String calibrationMethod() {
        return calibrationMethod;
    }

    public Double picp90() {
        return picp90;
    }

    public Double pinaw90() {
        return pinaw90;
    }
}