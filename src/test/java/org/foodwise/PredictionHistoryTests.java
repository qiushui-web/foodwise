package org.foodwise;

import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.prediction.PredictionContext;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDate;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PredictionHistoryTests {
    @Autowired FoodwiseRepository repository;
    @Autowired JdbcTemplate jdbc;
    @Test @Transactional
    void historyCutoffExcludesFutureRecordsAndPreservesMealScope() {
        var date = LocalDate.of(2026, 7, 12);
        var before = repository.recentSales(1L, date, "全日");
        jdbc.update("UPDATE daily_operation SET sold_qty = 9999 WHERE dish_id=1 AND business_date > ?", date);
        assertEquals(before, repository.recentSales(1L, date, "全日"));
        assertTrue(repository.recentSales(1L, date, "不存在").isEmpty());
        var context = new PredictionContext(1L, "晴", false, false, "test", null, "test", date.plusDays(1), "午餐", "simulation");
        assertEquals(date, context.historyCutoff());
        var later = new PredictionContext(1, "晴", false, false, "test", null, "test", LocalDate.now().plusDays(10), "全日", "simulation");
        assertEquals(LocalDate.now(), later.historyCutoff());
    }

    @Test void missingBusinessDatesDoNotBecomeZeroSales() {
        var features = org.foodwise.prediction.FeatureBuilder.build(java.util.List.of(
                new org.foodwise.prediction.SalesObservation(LocalDate.of(2026,10,12), 20, 22),
                new org.foodwise.prediction.SalesObservation(LocalDate.of(2026,10,1), 10, 12)));
        assertEquals(2, features.observations());
        assertEquals(50.0 / 3, features.weightedDemand(), 0.00001);
        assertThrows(IllegalArgumentException.class, () -> org.foodwise.prediction.FeatureBuilder.build(java.util.List.of()));
    }
}
