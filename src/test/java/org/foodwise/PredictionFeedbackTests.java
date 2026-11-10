package org.foodwise;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.service.FoodwiseService;
import org.foodwise.service.PredictionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDate;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Transactional
class PredictionFeedbackTests {
    @Autowired PredictionService predictions;
    @Autowired FoodwiseService foodwise;
    @Autowired org.foodwise.repository.FoodwiseRepository repository;

    @Test void rejectsOtherDishDateOrMealAndRequiresAdjustmentReason() {
        var day = LocalDate.now().plusDays(1);
        var result = predictions.predict(new PredictionContext(1, "晴", false, false,
                "test", null, "test", day, "全日", "simulation"));
        long id = result.prediction().predictionId();
        int quantity = result.prediction().predictedMid();
        assertDoesNotThrow(() -> foodwise.validatePredictionFeedback(id, 1, day, "全日", true, quantity, ""));
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(id, 2, day, "全日", true, quantity, ""));
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(id, 1, day.minusDays(1), "全日", true, quantity, ""));
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(id, 1, day, "午餐", true, quantity, ""));
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(id, 1, day, "全日", true, quantity + 1, ""));
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(id, 1, day, "全日", false, quantity, ""));
        assertDoesNotThrow(() -> foodwise.validatePredictionFeedback(id, 1, day, "全日", true, quantity + 1, "现场客流变化"));
    }

    @Test void reviewUsesMatchingMealAndMostRecentDecisionWithoutMultiplyingRows() {
        var day = LocalDate.now();
        var result = predictions.predict(new PredictionContext(1, "晴", false, false,
                "test", null, "test", day, "全日", "simulation"));
        long id = result.prediction().predictionId();
        repository.upsertOperation(day, "午餐", 1, 10, 10, 8, 0, 2, new java.math.BigDecimal("80"), "晴", "", true);
        foodwise.savePredictionFeedback(id, true, 20, "库存调整", "test");
        foodwise.savePredictionFeedback(id, true, 25, "修正计划", "test");
        var rows = foodwise.predictionReviews().stream().filter(row -> ((Number) row.get("prediction_id")).longValue() == id).toList();
        assertEquals(1, rows.size());
        assertEquals(25, ((Number) rows.get(0).get("adjusted_qty")).intValue());
        assertFalse(rows.get(0).containsKey("sold_qty"));
        repository.upsertOperation(day, "全日", 1, 20, 24, 22, 0, 2, new java.math.BigDecimal("220"), "晴", "", true);
        var review = foodwise.predictionReviews().stream().filter(row -> ((Number) row.get("prediction_id")).longValue() == id).findFirst().orElseThrow();
        assertEquals(-1, ((Number) review.get("execution_error")).intValue());
        assertEquals(22 - result.prediction().predictedMid(), ((Number) review.get("prediction_error")).intValue());
    }

    @Test void preventsMixingDailyTotalsWithMealSpecificRecords() {
        var day = LocalDate.now().minusDays(2);
        repository.upsertOperation(day, "午餐", 1, 10, 10, 8, 0, 2, new java.math.BigDecimal("80"), "晴", "", true);
        assertThrows(IllegalArgumentException.class, () -> repository.validateMealScope(day, "全日", 1));
        assertDoesNotThrow(() -> repository.validateMealScope(day, "晚餐", 1));
    }

    @Test void projectSnapshotMetadataDoesNotClaimVerifiedCampusTrial() {
        var sources = repository.dataSources();
        var snapshot = sources.stream().filter(row -> "OPS_MEASURE_001".equals(row.get("source_id"))).findFirst().orElseThrow();
        assertEquals("project_snapshot_unverified", snapshot.get("source_type"));
        assertTrue(String.valueOf(snapshot.get("truth_boundary")).contains("不能作为河北校园"));
    }
}
