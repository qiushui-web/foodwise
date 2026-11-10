package org.foodwise.decision;

import jakarta.annotation.PostConstruct;
import org.foodwise.prediction.PredictionOrchestrator;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 证据页的数据源：把模型清单、区间实验、决策实验、归因实验四份产物合成一个只读视图。
 * 页面上的每个数字都来自磁盘上的文件，而不是前端写死。
 */
@Service
public class ModelEvidenceService {

    private final PredictionOrchestrator orchestrator;
    private Map<String, Object> manifest = Map.of();
    private Map<String, Object> intervalExperiment = Map.of();
    private Map<String, Object> decisionExperiment = Map.of();
    private Map<String, Object> attributionExperiment = Map.of();
    private String loadError;

    public ModelEvidenceService(PredictionOrchestrator orchestrator) {
        this.orchestrator = orchestrator;
    }

    @PostConstruct
    public void init() {
        try {
            manifest = read("modeling/model_manifest.json");
            intervalExperiment = read("modeling/interval_backtest_metrics.json");
            decisionExperiment = read("modeling/decision_backtest_metrics.json");
            attributionExperiment = read("modeling/attribution_backtest.json");
        } catch (Exception e) {
            loadError = e.getClass().getSimpleName() + ":" + e.getMessage();
        }
    }

    private Map<String, Object> read(String path) throws Exception {
        try (InputStream input = new ClassPathResource(path).getInputStream()) {
            @SuppressWarnings("unchecked")
            Map<String, Object> value = new ObjectMapper()
                    .readValue(new String(input.readAllBytes(), StandardCharsets.UTF_8), Map.class);
            return value;
        }
    }

    public Map<String, Object> evidence() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("engines", orchestrator.availableEngines());
        payload.put("manifest", manifest);
        payload.put("intervalExperiment", intervalExperiment);
        payload.put("decisionExperiment", decisionExperiment);
        payload.put("attributionExperiment", attributionExperiment);
        payload.put("loadError", loadError);
        return payload;
    }

    public Map<String, Object> manifest() {
        return manifest;
    }

    public Map<String, Object> intervalExperiment() {
        return intervalExperiment;
    }

    public Map<String, Object> decisionExperiment() {
        return decisionExperiment;
    }

    public Map<String, Object> attributionExperiment() {
        return attributionExperiment;
    }
}