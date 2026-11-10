package org.foodwise;

import org.foodwise.prediction.*;
import org.foodwise.service.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;
import java.time.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Transactional
class PreparationPlanServiceTests {
    @Autowired PreparationPlanService plans;
    @Autowired PredictionService predictions;
    @Autowired FoodwiseService foodwise;
    @Autowired org.springframework.jdbc.core.JdbcTemplate jdbc;
    @Autowired org.foodwise.repository.FoodwiseRepository repository;
    @Autowired org.foodwise.decision.BaselineDecisionEngine baseline;
    private PreparationPlanner.Inputs input() {
        return new PreparationPlanner.Inputs(20, 30, 10, 20, LocalTime.of(10,0), LocalTime.of(11,0), LocalTime.of(13,0));
    }
    private long predict(String meal) {
        repository.upsertOperation(LocalDate.now().minusDays(1), meal, 1, 100, 100, 80, 0, 20,
                new java.math.BigDecimal("800"), "晴", "synthetic test only", true);
        return predictions.predict(new PredictionContext(1, "晴", false, false, "test", null, "test",
                LocalDate.now().plusDays(1), meal, "synthetic test only")).prediction().predictionId();
    }
    @Test void persistsAndReadsInputsAndRejectsDecisionAboveSavedConstraint() {
        long prediction = predict("午餐");
        var saved = plans.create(prediction, input(), "test");
        long id = ((Number)saved.get("id")).longValue();
        assertEquals(prediction, ((Number)plans.read(id).get("predictionId")).longValue());
        var json = new tools.jackson.databind.ObjectMapper().valueToTree(plans.read(id));
        assertEquals(20, json.path("inputs").path("stockServings").asInt());
        assertFalse(json.path("plan").path("automaticExecution").asBoolean());
        assertTrue(json.path("plan").path("plannedTotal").asInt() <= 20);
        assertThrows(IllegalArgumentException.class, () -> foodwise.validatePredictionFeedback(prediction,1,
                LocalDate.now().plusDays(1),"午餐",true,21,"人工调整"));
    }
    @Test void rejectsMissingPredictionDailyScopeAndNonServingUnits() {
        assertThrows(IllegalArgumentException.class, () -> plans.create(Long.MAX_VALUE,input(),"test"));
        assertThrows(IllegalArgumentException.class, () -> plans.read(Long.MAX_VALUE));
        assertThrows(IllegalArgumentException.class, () -> plans.create(predict("全日"),input(),"test"));
        long prediction = predict("午餐");
        jdbc.update("UPDATE dish SET quantity_unit='克' WHERE id=1");
        assertThrows(IllegalArgumentException.class, () -> plans.create(prediction,input(),"test"));
    }

    @Test void persistsAndReadsPlanForDecisionRecordAndRejectsInvalidMeal() {
        repository.upsertOperation(LocalDate.now().minusDays(1), "全日", 1, 100, 100, 80, 0, 20,
                new java.math.BigDecimal("800"), "晴", "synthetic test only", true);
        var context = new PredictionContext(1, "晴", false, false, "test", null, "test",
                LocalDate.now().plusDays(1), "午餐", "synthetic test only");
        long decision = baseline.predict(context).prediction().predictionId();
        var saved = plans.createForDecision(decision, "午餐", input(), "test");
        long id = ((Number) saved.get("id")).longValue();
        assertEquals(decision, ((Number) plans.readDecisionPlan(id).get("predictionId")).longValue());
        assertFalse(((tools.jackson.databind.JsonNode) saved.get("plan")).path("automaticExecution").asBoolean());
        assertThrows(IllegalArgumentException.class, () -> plans.createForDecision(decision, "晚餐", input(), "test"));
        assertThrows(IllegalArgumentException.class, () -> plans.createForDecision(decision, "全日", input(), "test"));
        assertThrows(IllegalArgumentException.class, () -> plans.createForDecision(Long.MAX_VALUE, "午餐", input(), "test"));
    }
}
