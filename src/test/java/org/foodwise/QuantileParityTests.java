package org.foodwise;

import org.foodwise.decision.LightGbmTextModel;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * Java 分位模型与 Python LightGBM 的逐值对齐。
 * 冻结点来自 modeling/scripts/32_fit_intervals.py 的实际训练结果，
 * 任何一侧改了特征顺序、模型文件或叶值解释，这里都会先失败。
 */
class QuantileParityTests {

    @SuppressWarnings("unchecked")
    @Test
    void javaQuantileModelsMatchPythonOnFrozenVectors() throws Exception {
        byte[] fixture = resource("/modeling/quantile_parity_fixture.json").readAllBytes();
        Map<String, Object> root = new ObjectMapper()
                .readValue(new String(fixture, StandardCharsets.UTF_8), Map.class);
        List<Map<String, Object>> rows = (List<Map<String, Object>>) root.get("rows");
        assertNotNull(rows);
        assertEquals(24, ((List<Object>) root.get("feature_order")).size());

        try (InputStream lower = resource("/modeling/lgbm_campus_q05.txt");
             InputStream upper = resource("/modeling/lgbm_campus_q95.txt")) {
            LightGbmTextModel q05 = LightGbmTextModel.load(lower, "q05");
            LightGbmTextModel q95 = LightGbmTextModel.load(upper, "q95");
            for (Map<String, Object> row : rows) {
                List<Number> values = (List<Number>) row.get("features");
                double[] features = new double[values.size()];
                for (int i = 0; i < features.length; i++) features[i] = values.get(i).doubleValue();
                assertEquals(((Number) row.get("q05")).doubleValue(), q05.predict(features), 1e-6);
                assertEquals(((Number) row.get("q95")).doubleValue(), q95.predict(features), 1e-6);
            }
        }
    }

    private InputStream resource(String path) {
        InputStream stream = getClass().getResourceAsStream(path);
        assertNotNull(stream, "Missing generated fixture: " + path);
        return stream;
    }
}