package org.foodwise.prediction;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

@Service
public class PredictionOrchestrator {
    private final List<PredictionEngine> engines;

    public PredictionOrchestrator(List<PredictionEngine> engines) {
        this.engines = List.copyOf(engines);
    }

    public PredictionEngineResult predict(PredictionContext context) {
        return predict(context, "rule");
    }

    public PredictionEngineResult predict(PredictionContext context, String engineKey) {
        return engines.stream()
                .filter(engine -> engine.key().equalsIgnoreCase(engineKey))
                .findFirst()
                .map(engine -> engine.predict(context))
                .orElseThrow(() -> new IllegalArgumentException("未找到预测引擎: " + engineKey));
    }

    public List<String> availableEngines() {
        return engines.stream().map(PredictionEngine::key).sorted().toList();
    }

    public PredictionEngineResult result(String engineKey, String version,
                                         org.foodwise.model.PredictionResult prediction) {
        return new PredictionEngineResult(engineKey, version, prediction, Instant.now());
    }
}

