package org.foodwise.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;
import java.util.LinkedHashMap;
import java.util.Map;

/** Frozen public-data evidence, independent of operational simulation records. */
@Service
public class PublicExperimentReportService {
    private final Resource resource;

    @Autowired
    public PublicExperimentReportService(@Value("${foodwise.experiment.report:classpath:modeling/public_sales_report.json}") Resource resource) {
        this.resource = resource;
    }

    public Map<String, Object> report() {
        try (var input = resource.getInputStream()) {
            var node = new ObjectMapper().readTree(input);
            if (!"public-sales-v2".equals(node.path("protocol").asText())
                    || !"scaled store sales (continuous; may be negative)".equals(node.path("unit").asText())
                    || !node.path("source_sha256").asText().matches("[a-f0-9]{64}")
                    || node.path("run_id").asText().isBlank()
                    || node.path("splits").path("test").path("rows").asInt() <= 0
                    || !node.path("test_metrics").isObject()
                    || !node.path("limitations").isArray()) {
                return unavailable();
            }
            for (String model : new String[]{"pred_same_weekday_mean4", "pred_lgbm"}) {
                var mae = node.path("test_metrics").path(model).path("mae");
                if (!mae.isNumber() || !Double.isFinite(mae.asDouble()) || mae.asDouble() < 0) return unavailable();
            }
            if (node.path("dataset").asText().isBlank() || node.path("model_version").asText().isBlank()
                    || !node.path("series").isArray() || node.path("series").isEmpty()) return unavailable();
            for (var point : node.path("series")) {
                java.time.LocalDate.parse(point.path("date").asText());
                for (String field : new String[]{"actual", "baseline", "prediction"}) {
                    if (!point.path(field).isNumber() || !Double.isFinite(point.path(field).asDouble())) return unavailable();
                }
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> values = new ObjectMapper().convertValue(node, Map.class);
            var result = new LinkedHashMap<>(values);
            result.put("available", true);
            return result;
        } catch (Exception exception) {
            return unavailable();
        }
    }

    private Map<String, Object> unavailable() {
        return Map.of("available", false, "status", "unavailable",
                "limitation", "公开实验报告缺失、损坏或单位不匹配；暂不展示模型精度。");
    }
}
