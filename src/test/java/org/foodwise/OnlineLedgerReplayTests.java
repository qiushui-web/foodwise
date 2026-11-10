package org.foodwise;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.PredictionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.time.LocalDate;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Transactional
class OnlineLedgerReplayTests {
    @Autowired FoodwiseRepository repository;
    @Autowired PredictionService predictions;
    @Autowired org.springframework.transaction.PlatformTransactionManager transactions;
    @Autowired org.springframework.jdbc.core.JdbcTemplate jdbc;

    @Test void aLaterCorrectionCannotRewriteAPreviouslyCapturedPredictionContext() {
        var day = LocalDate.now().minusDays(1);
        repository.upsertOperation(day, "午餐", 1, 20, 20, 18, 0, 2,
                new BigDecimal("180"), "晴", "constructed replay test", false);
        var context = repository.captureLedgerBoundary(new PredictionContext(1, "晴", false, false, "test", null, "test",
                LocalDate.now(), "午餐", "test fixture"));
        var first = predictions.predict(context);
        var before = first.prediction();
        var originalVersions = repository.ledgerHistory(context).revisionIds();
        assertFalse(originalVersions.isEmpty());
        assertEquals(context.predictionCutoffAt(), first.predictionCutoffAt());
        assertEquals(originalVersions, first.revisionIds());
        String snapshot = jdbc.queryForObject("SELECT input_json FROM prediction_input_snapshot WHERE prediction_id=?",
                String.class, before.predictionId());
        var saved = new tools.jackson.databind.ObjectMapper().readTree(snapshot);
        assertEquals(context.predictionCutoffAt().toString(), saved.path("predictionCutoffAt").asText());
        assertEquals(originalVersions.get(0).longValue(), saved.path("revisionIds").get(0).asLong());
        repository.upsertOperation(day, "午餐", 1, 200, 200, 180, 0, 20,
                new BigDecimal("1800"), "晴", "later correction", false);
        var replayed = predictions.predict(context).prediction();
        assertEquals(before.predictedMid(), replayed.predictedMid(),
                "The captured prediction context must retain the old 18-portion observation");
        assertEquals(originalVersions, repository.ledgerHistory(context).revisionIds());
        var current = predictions.predict(new PredictionContext(1, "晴", false, false,
                "test", null, "test", LocalDate.now(), "午餐", "test fixture")).prediction();
        assertTrue(current.predictedMid() > before.predictedMid());
    }

    @Test void aRecordedBoundaryDoesNotIncludeALaterBackfill() {
        var context = repository.captureLedgerBoundary(new PredictionContext(1, "晴", false, false, "test", null, "test",
                LocalDate.now(), "午餐", "test fixture"));
        repository.upsertOperation(LocalDate.now().minusDays(1), "午餐", 1, 20, 20, 18, 0, 2,
                new BigDecimal("180"), "晴", "late backfill", false);
        assertTrue(repository.ledgerHistory(context).observations().isEmpty());
        assertTrue(repository.ledgerHistory(context).revisionIds().isEmpty());
        assertThrows(IllegalArgumentException.class, () -> predictions.predict(context));
    }

    @Test void historicalDateDoesNotPretendCurrentSeedsWereAvailableThen() {
        var context = new PredictionContext(1, "晴", false, false, "test", null, "test",
                LocalDate.now().minusDays(2), "全日", "test fixture");
        assertThrows(IllegalArgumentException.class, () -> repository.ledgerHistory(context));
        assertThrows(IllegalArgumentException.class, () -> predictions.predict(context));
    }

    @Test
    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.NOT_SUPPORTED)
    void failedFeedbackTransactionDoesNotPublishALedgerRevision() {
        var initial = repository.captureLedgerBoundary(new PredictionContext(1, "晴", false, false));
        var before = repository.ledgerHistory(initial).revisionIds();
        var tx = new org.springframework.transaction.support.TransactionTemplate(transactions);
        assertThrows(IllegalStateException.class, () -> tx.execute(status -> {
            repository.upsertOperation(LocalDate.now().minusDays(1), "午餐", 1, 20, 20, 18, 0, 2,
                    new BigDecimal("180"), "晴", "rollback fixture", false);
            throw new IllegalStateException("simulated feedback failure");
        }));
        var after = repository.captureLedgerBoundary(new PredictionContext(1, "晴", false, false));
        assertEquals(initial.publicationWatermark(), after.publicationWatermark());
        assertEquals(before, repository.ledgerHistory(after).revisionIds());
    }

    @Test void ambiguousLegacyBusinessKeysAreRejectedInsteadOfDoubleCounted() {
        var day = LocalDate.now().minusDays(1);
        repository.upsertOperation(day, "午餐", 1, 20, 20, 18, 0, 2,
                new BigDecimal("180"), "晴", "legacy duplicate fixture", false);
        jdbc.update("""
                INSERT INTO daily_operation(business_date, phase, meal_period, dish_id, planned_qty,
                    prepared_qty, sold_qty, discount_sold_qty, leftover_qty, revenue, weather, recommendation_adopted)
                VALUES (?, '运营回传', '午餐', 1, 20, 20, 18, 0, 2, 180, '晴', FALSE)
                """, day);
        repository.captureUnversionedOperations();
        assertThrows(IllegalArgumentException.class,
                () -> predictions.predict(new PredictionContext(1, "晴", false, false)));
    }
}
