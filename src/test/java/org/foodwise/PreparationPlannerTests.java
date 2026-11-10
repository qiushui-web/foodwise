package org.foodwise;

import org.foodwise.prediction.PreparationPlanner;
import org.junit.jupiter.api.Test;
import java.time.LocalTime;
import static org.junit.jupiter.api.Assertions.*;

class PreparationPlannerTests {
    private PreparationPlanner.Inputs input(int stock, int capacity, int batch, int lead,
                                            String ready, String start, String end) {
        return new PreparationPlanner.Inputs(stock, capacity, batch, lead,
                LocalTime.parse(ready), LocalTime.parse(start), LocalTime.parse(end));
    }
    @Test void stockAndCapacityLimitWholeBatchesWithoutChangingDemand() {
        var result = PreparationPlanner.plan(100, 75, input(83, 62, 10, 20, "10:30", "11:00", "13:00"));
        assertEquals(100, result.referenceDemand());
        assertEquals(60, result.plannedTotal());
        assertEquals(60, result.firstBatch());
        assertEquals(0, result.replenishQty());
        assertEquals(40, result.uncoveredDemand());
        assertFalse(result.automaticExecution());
    }
    @Test void zeroStockNeverManufacturesAMinimumServing() {
        var result = PreparationPlanner.plan(100, 75, input(0, 200, 10, 20, "10:30", "11:00", "13:00"));
        assertEquals(0, result.plannedTotal());
        assertEquals(0, result.firstBatch());
        assertEquals(100, result.uncoveredDemand());
    }
    @Test void leadTimeAndMealEndPreventLateProduction() {
        var tooLate = PreparationPlanner.plan(100, 75, input(200, 200, 10, 30, "10:45", "11:00", "13:00"));
        assertEquals(0, tooLate.plannedTotal());
        assertFalse(tooLate.warnings().isEmpty());
        var noRefill = PreparationPlanner.plan(100, 75, input(200, 200, 10, 30, "10:00", "11:00", "11:15"));
        assertEquals(70, noRefill.firstBatch());
        assertEquals(0, noRefill.replenishQty());
        assertEquals(30, noRefill.uncoveredDemand());
        assertFalse(noRefill.canReplenish());
    }
    @Test void refillRemainsConditionalAndBatchAligned() {
        var result = PreparationPlanner.plan(103, 75, input(200, 200, 10, 20, "10:30", "11:00", "13:00"));
        assertEquals(70, result.firstBatch());
        assertEquals(30, result.replenishQty());
        assertEquals(100, result.plannedTotal());
        assertEquals("12:40", result.latestReplenishStart().toString());
        assertTrue(result.canReplenish());
    }
    @Test void missingNegativeAndOvernightParametersAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> input(-1, 100, 10, 20, "10:30", "11:00", "13:00"));
        assertThrows(IllegalArgumentException.class, () -> input(100, 100, 0, 20, "10:30", "11:00", "13:00"));
        assertThrows(IllegalArgumentException.class, () -> input(100, 100, 10, 20, "20:00", "21:00", "01:00"));
        assertThrows(IllegalArgumentException.class, () -> new PreparationPlanner.Inputs(null, 100, 10, 20,
                LocalTime.NOON, LocalTime.NOON, LocalTime.of(13, 0)));
    }
}
