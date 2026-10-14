package org.foodwise;

import org.foodwise.service.AnalyticsService;
import org.foodwise.service.OperationFeedbackService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.cache.CacheManager;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.math.BigDecimal;
import java.time.LocalDate;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:cache-verification;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class OperationCacheTests {
    @Autowired AnalyticsService analytics;
    @Autowired OperationFeedbackService feedback;
    @Autowired CacheManager caches;
    @Autowired PlatformTransactionManager transactions;
    @Autowired org.foodwise.service.OperationImportService importer;
    @Autowired org.springframework.jdbc.core.JdbcTemplate jdbc;

    @Test
    void mixedCsvCommitsAcceptedRowAndReportsRejectedRow() {
        String csv = "business_date,meal_period,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather\n"
                + LocalDate.now().minusDays(2) + ",早餐,1,10,10,8,0,2,80,晴\n"
                + LocalDate.now().minusDays(2) + ",晚餐,1,10,10,8,0,9,80,晴\n";
        var file = new org.springframework.mock.web.MockMultipartFile("file", "mixed.csv", "text/csv", csv.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        var result = importer.importCsv(file, "test", true);
        assertEquals(1, result.get("imported"));
        assertEquals(1, result.get("rejected"));
        assertEquals(8, jdbc.queryForObject("SELECT sold_qty FROM daily_operation WHERE business_date=? AND meal_period='早餐' AND dish_id=1", Integer.class, LocalDate.now().minusDays(2)));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM daily_operation WHERE business_date=? AND meal_period='晚餐' AND dish_id=1", Integer.class, LocalDate.now().minusDays(2)));
        assertEquals("COMPLETED_WITH_ERRORS", jdbc.queryForObject("SELECT status FROM operation_import_batch WHERE id=?", String.class, result.get("batchId")));
    }

    @Test
    void committedWriteRefreshesSummaryButRollbackKeepsCachedValue() {
        caches.getCache("metadata").clear();
        var before = analytics.metadata();
        int count = ((Number) before.get("records")).intValue();
        caches.getCache("weather").put("retained", "weather-result");
        var tx = new TransactionTemplate(transactions);
        tx.executeWithoutResult(status -> {
            submit(LocalDate.now().minusDays(1));
            status.setRollbackOnly();
        });
        assertSame(before, analytics.metadata());
        submit(LocalDate.now());
        assertEquals(count + 1, ((Number) analytics.metadata().get("records")).intValue());
        assertEquals("weather-result", caches.getCache("weather").get("retained", String.class));
    }

    private void submit(LocalDate date) {
        feedback.submit(date, "午餐", 1L, 12, 12, 10, 0, 2, new BigDecimal("100.00"),
                "晴", "测试", false, true, "test", "cache verification");
    }
}
