package org.foodwise;

import org.foodwise.service.PublicExperimentReportService;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.ClassPathResource;
import static org.junit.jupiter.api.Assertions.*;

class PublicExperimentReportTests {
    @Test
    void missingOrInvalidReportsNeverFabricateAccuracy() {
        for (String json : new String[]{"{}", "broken", "{\"unit\":\"份\"}"}) {
            var result = new PublicExperimentReportService(new ByteArrayResource(json.getBytes())).report();
            assertEquals(false, result.get("available"));
            assertFalse(result.containsKey("test_metrics"));
        }
        assertEquals(false, new PublicExperimentReportService(new ClassPathResource("missing.json")).report().get("available"));
    }

    @Test
    void frozenReportKeepsObservedScaledUnitsAndBaselineComparison() {
        var result = new PublicExperimentReportService(new ClassPathResource("modeling/public_sales_report.json")).report();
        assertEquals(true, result.get("available"));
        assertEquals("public_sales_20261012T090638369705Z", result.get("run_id"));
        var metrics = (java.util.Map<?, ?>) result.get("test_metrics");
        double baseline = ((Number)((java.util.Map<?, ?>) metrics.get("pred_same_weekday_mean4")).get("mae")).doubleValue();
        double model = ((Number)((java.util.Map<?, ?>) metrics.get("pred_lgbm")).get("mae")).doubleValue();
        assertTrue(model > baseline);
        assertFalse(result.containsKey("enhanced_hit_rate"));
        assertNotNull(result.get("splits"));
        assertNotNull(result.get("source_sha256"));
    }
}
