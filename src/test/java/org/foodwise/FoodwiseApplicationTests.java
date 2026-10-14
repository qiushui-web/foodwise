package org.foodwise;

import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.AnalyticsService;
import org.foodwise.service.FoodwiseService;
import org.foodwise.service.IntelligentDecisionService;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.PredictionOrchestrator;
import org.foodwise.modules.ModuleCatalog;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletRequest;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiIdempotency;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.Map;
import org.springframework.transaction.annotation.Transactional;

import static org.junit.jupiter.api.Assertions.assertEquals;

@SpringBootTest
public class FoodwiseApplicationTests {

    @Autowired
    private FoodwiseRepository repository;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private AnalyticsService analyticsService;

    @Autowired
    private FoodwiseService foodwiseService;

    @Autowired
    private IntelligentDecisionService intelligentDecisionService;

    @Autowired
    private PredictionOrchestrator predictionOrchestrator;


    @Test
    @Transactional
    void predictionHandlesZeroSalesHistoryWithoutNonFiniteNumbers() {
        jdbcTemplate.update("UPDATE daily_operation SET sold_qty=0, discount_sold_qty=0, leftover_qty=prepared_qty WHERE dish_id=1");
        PredictionEngineResult result = predictionOrchestrator.predict(new PredictionContext(1, "晴", false, false));
        org.junit.jupiter.api.Assertions.assertNotNull(result.prediction());
        org.junit.jupiter.api.Assertions.assertTrue(result.prediction().predictedHigh() >= result.prediction().predictedLow());
    }

    @Test
    void contextLoads() {
    }

    @Test void mapAndDtoShareScenarioCalculationAndRounding() {
        var dto = foodwiseService.getDashboardSummary();
        var summary = (Map<?, ?>)foodwiseService.dashboard().get("summary");
        assertEquals(dto.costSaved(), summary.get("cost_saved"));
        assertEquals(dto.carbonSaved(), summary.get("carbon_saved"));
        assertEquals(dto.waterSaved(), summary.get("water_saved"));
        org.junit.jupiter.api.Assertions.assertTrue(summary.get("scenario_statement").toString().contains("非实测收益"));
    }

    @Test
    void predictionDeclaresHeuristicRangeInsteadOfClaimingCalibration() {
        PredictionEngineResult result = predictionOrchestrator.predict(
                new PredictionContext(1, "晴", false, false));
        assertEquals("heuristic", result.prediction().intervalMethod());
        org.junit.jupiter.api.Assertions.assertFalse(result.prediction().intervalCalibrated());
        assertEquals("heuristic_score_not_accuracy", result.prediction().confidenceKind());
    }

    @Test
    void reportUsesDishLevelCostsAndUnifiedSimulationMetrics() {
        Map<String, Object> summary = repository.reportSummary();

        assertEquals(0, new BigDecimal("13.1").compareTo(new BigDecimal(summary.get("baseline_leftover_rate").toString())));
        assertEquals(0, new BigDecimal("5.4").compareTo(new BigDecimal(summary.get("intervention_leftover_rate").toString())));
        assertEquals(0, new BigDecimal("7.7").compareTo(new BigDecimal(summary.get("baseline_prediction_error").toString())));
        assertEquals(0, new BigDecimal("3.3").compareTo(new BigDecimal(summary.get("prediction_error").toString())));
        assertEquals(0, new BigDecimal("1405.90").compareTo(new BigDecimal(summary.get("avoided_loss").toString())));
    }

    @Test
    void importsProjectDataCenterCsvIntoDatabase() {
        Integer records = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM daily_operation", Integer.class);
        Integer violations = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM daily_operation
                WHERE sold_qty + leftover_qty <> prepared_qty
                """, Integer.class);
        assertEquals(98, records);
        assertEquals(0, violations);
    }

    @Test
    void calculatesMetadataBacktestAndFinancialAnalysis() {
        Map<String, Object> metadata = analyticsService.metadata();
        Map<String, Object> backtest = analyticsService.backtest();
        Map<String, Object> financial = analyticsService.financial();

        assertEquals(98, ((Number) metadata.get("records")).intValue());
        assertEquals(100.0, metadata.get("validation_rate"));
        assertEquals(true, backtest.get("available"));
        org.junit.jupiter.api.Assertions.assertNotNull(backtest.get("test_metrics"));
        org.junit.jupiter.api.Assertions.assertTrue(((Map<?, ?>) financial.get("change")).containsKey("avoided_leftover_cost"));
    }

    @Test
    void exposesVersionedPredictionEngineAndModelMetadata() {
        org.junit.jupiter.api.Assertions.assertTrue(predictionOrchestrator.availableEngines().contains("rule"));
        PredictionEngineResult result = predictionOrchestrator.predict(
                new PredictionContext(1, "晴朗", false, false));
        assertEquals("rule", result.engineKey());
        assertEquals("rule-v1", result.modelVersion());
        org.junit.jupiter.api.Assertions.assertNotNull(result.prediction());
        assertEquals(1, jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM model_version WHERE model_key='demand' AND version='rule-v1'", Integer.class));
        assertEquals(1, jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM prediction_input_snapshot WHERE prediction_id=?", Integer.class,
                result.prediction().predictionId()));
        Map<String, Object> trace = jdbcTemplate.queryForMap(
                "SELECT trace_id, operator_name FROM prediction_record WHERE id=?",
                result.prediction().predictionId());
        assertEquals("system", trace.get("operator_name"));
        org.junit.jupiter.api.Assertions.assertNotNull(trace.get("trace_id"));
    }

    @Test
    void declaresStableModularMonolithBoundaries() {
        assertEquals(7, ModuleCatalog.definitions().size());
        assertEquals("prediction", ModuleCatalog.definitions().get(1).name());
        org.junit.jupiter.api.Assertions.assertTrue(ModuleCatalog.definitions().stream()
                .allMatch(module -> module.packageName().startsWith("org.foodwise.modules.")));
    }

    @Test
    void apiWriteRequestsRequireIdempotencyKey() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        org.junit.jupiter.api.Assertions.assertThrows(org.foodwise.api.ApiIdempotencyException.class,
                () -> ApiIdempotency.require(request));
        request.addHeader("Idempotency-Key", "test-write-001");
        ApiIdempotency.require(request);
    }

    @Test
    void apiFailureCarriesMachineReadableCode() {
        ApiResponse<Void> response = ApiResponse.failure("VALIDATION_ERROR", "字段无效", "trace-1");
        assertEquals("VALIDATION_ERROR", response.code());
        assertEquals("trace-1", response.traceId());
    }

    @Test
    @Transactional
    void keepsMealPeriodsSeparateAndUpdatesOnlyTheMatchingPeriod() {
        LocalDate date = LocalDate.of(2026, 9, 1);
        long breakfast = repository.upsertOperation(date, "早餐", 1, 10, 10, 8, 0, 2,
                new BigDecimal("80.00"), "晴", "", false).operationId();
        long lunch = repository.upsertOperation(date, "午餐", 1, 20, 20, 18, 0, 2,
                new BigDecimal("180.00"), "晴", "", false).operationId();
        assertEquals(2, jdbcTemplate.queryForObject("SELECT COUNT(*) FROM daily_operation WHERE business_date=? AND dish_id=1",
                Integer.class, date));
        assertEquals(breakfast, repository.upsertOperation(date, "早餐", 1, 11, 11, 9, 0, 2,
                new BigDecimal("90.00"), "晴", "", false).operationId());
        assertEquals(18, jdbcTemplate.queryForObject("SELECT sold_qty FROM daily_operation WHERE id=?", Integer.class, lunch));
        assertEquals(27, repository.recentSales(1).get(0));
        org.junit.jupiter.api.Assertions.assertTrue(
                new String(foodwiseService.exportOperationsCsv(), java.nio.charset.StandardCharsets.UTF_8)
                        .startsWith("\uFEFF营业日期,餐次,档口"));
    }

    @Test
    void rejectsDiscountsBasedOnHistoricalLeftovers() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> intelligentDecisionService.recommendOffer(1));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> foodwiseService.createOffer(1, 1, new BigDecimal("15.00"), LocalTime.MIN,
                        LocalTime.MAX, true));
    }

    @Test
    @Transactional
    void verifiesEachOrderOnlyOnce() {
        Long orderId = jdbcTemplate.queryForObject(
                "SELECT id FROM meal_order WHERE status='待取餐' ORDER BY id LIMIT 1", Long.class);
        foodwiseService.verify(orderId);
        assertEquals("已核销", jdbcTemplate.queryForObject("SELECT status FROM meal_order WHERE id=?", String.class, orderId));
        assertEquals(1, jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM verification_record WHERE order_id=?", Integer.class, orderId));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalStateException.class, () -> foodwiseService.verify(orderId));
    }

    @Test
    @Transactional
    void resolvesEachAlertOnlyOnce() {
        Long alertId = jdbcTemplate.queryForObject(
                "SELECT id FROM operation_alert WHERE status='待处理' ORDER BY id LIMIT 1", Long.class);
        foodwiseService.resolveAlert(alertId);
        assertEquals("已处理", jdbcTemplate.queryForObject("SELECT status FROM operation_alert WHERE id=?", String.class, alertId));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalStateException.class, () -> foodwiseService.resolveAlert(alertId));
    }

}

