package org.foodwise.prediction;

public interface PredictionEngine {
    String key();

    String modelVersion();

    PredictionEngineResult predict(PredictionContext context);
}

