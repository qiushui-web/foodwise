package org.foodwise;

import org.foodwise.prediction.PredictionPolicy;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PredictionPolicyTests {
    @Test void quantitiesAreOrderedAndInvalidDemandFailsClosed() {
        for (double demand : new double[]{0, 1, 30, 100.5}) {
            var q = PredictionPolicy.quantities(demand);
            assertTrue(q.low() <= q.mid() && q.mid() < q.high());
            assertEquals(q.mid(), q.firstBatch() + q.replenish());
        }
        assertThrows(IllegalArgumentException.class, () -> PredictionPolicy.quantities(Double.NaN));
        assertThrows(IllegalArgumentException.class, () -> PredictionPolicy.quantities(-1));
    }
}
