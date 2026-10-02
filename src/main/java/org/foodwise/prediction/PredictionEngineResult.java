package org.foodwise.prediction;

import org.foodwise.model.PredictionResult;

import java.time.Instant;

public record PredictionEngineResult(
        String engineKey,
        String modelVersion,
        PredictionResult prediction,
        Instant generatedAt
) {
}

