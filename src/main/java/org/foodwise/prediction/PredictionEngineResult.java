package org.foodwise.prediction;

import org.foodwise.model.PredictionResult;

import java.time.Instant;

public record PredictionEngineResult(
        String engineKey,
        String modelVersion,
        PredictionResult prediction,
        Instant generatedAt,
        java.time.LocalDate targetDate,
        java.time.LocalDate historyCutoff,
        String mealPeriod,
        String sourceNature,
        java.time.LocalDate historyLatestDate,
        int historySampleCount,
        Instant predictionCutoffAt,
        java.util.List<Long> revisionIds,
        Long publicationWatermark
) {
    public PredictionEngineResult(String engineKey, String modelVersion,
                                  PredictionResult prediction, Instant generatedAt) {
        this(engineKey, modelVersion, prediction, generatedAt, null, null, "全日", "经营台账；来源待逐笔核验", null, 0, null, java.util.List.of(), null);
    }
}

