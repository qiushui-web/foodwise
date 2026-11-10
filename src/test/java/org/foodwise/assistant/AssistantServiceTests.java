package org.foodwise.assistant;

import org.foodwise.decision.BaselineDecisionEngine;
import org.foodwise.decision.DecisionPreview;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.time.LocalDate;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 参谋的五条边界 + 一条不变量：回答里的每个数字都必须能指回预览或请求。
 */
@SpringBootTest
class AssistantServiceTests {

    @Autowired
    AssistantService service;

    @Autowired
    BaselineDecisionEngine engine;

    private static final LocalDate DATE = LocalDate.of(2026, 7, 21);

    private DecisionPreview previewFor(long dishId) {
        return engine.preview(dishId, DATE);
    }

    @Test
    void explainUsesOnlyNumbersFromThePreview() {
        DecisionPreview preview = previewFor(1L);
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "为什么建议这么多份？",
                null, null, null, null, null, null, null));

        assertEquals("EXPLAIN", advice.intent());
        assertNull(advice.refusal());
        assertTrue(advice.answer().contains(Integer.toString(preview.quantity())),
                "回答必须带出建议量：" + advice.answer());
        assertEquals(4, advice.citations().size());
        assertEquals("plan", advice.citations().get(0).type());
        assertEquals(preview.quantity(), advice.suggestedAction().quantity());
        // 不变量：不允许出现预览之外的数字
        AssistantService.assertNoInventedNumbers(advice.answer(), AssistantService.allowedNumbers(preview));
    }

    @Test
    void pointForecastIsRefused() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "明天能卖多少份？",
                null, null, null, null, null, null, null));
        assertEquals("POINT_FORECAST", advice.intent());
        assertEquals("NO_POINT_FORECAST", advice.refusal().code());
        assertFalse(advice.answer().chars().anyMatch(Character::isDigit), "拒绝文案里不应出现数字");
    }

    @Test
    void effectClaimIsRefused() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "用了你们能省多少？",
                null, null, null, null, null, null, null));
        assertEquals("NO_EFFECT_CLAIM", advice.refusal().code());
    }

    @Test
    void foodSafetyIsOutOfScope() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "这个菜还新鲜吗，会不会变质？",
                null, null, null, null, null, null, null));
        assertEquals("OUT_OF_SCOPE_FOOD_SAFETY", advice.refusal().code());
    }

    @Test
    void unrelatedQuestionIsOutOfScope() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "今天下午会下雨吗？",
                null, null, null, null, null, null, null));
        assertEquals("OUT_OF_SCOPE", advice.refusal().code());
    }

    @Test
    void whatIfRecomputesQuantityFromGivenCosts() {
        DecisionPreview preview = previewFor(1L);
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "如果成本降到 4 元会怎样？",
                null, null, null, 13.0, 4.0, null, null));

        assertEquals("WHAT_IF", advice.intent());
        assertNotNull(advice.suggestedAction());
        assertTrue(advice.suggestedAction().quantity() >= preview.quantity(),
                "成本降低、缺货更贵，建议量不应下降");
        assertTrue(advice.citations().stream().anyMatch(c -> c.type().equals("request")));
    }

    @Test
    void reviewNeedsActuals() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "帮我复盘一下昨天的执行情况",
                null, null, null, null, null, null, null));
        assertEquals("REVIEW_NEEDS_ACTUALS", advice.refusal().code());
    }

    @Test
    void reviewComparesActualAgainstSuggestion() {
        DecisionPreview preview = previewFor(1L);
        int actual = preview.quantity() - 8;
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "帮我复盘一下昨天的执行情况",
                null, null, null, null, null, actual, actual - 4));

        assertEquals("REVIEW", advice.intent());
        assertTrue(advice.answer().contains("少"), advice.answer());
        assertTrue(advice.answer().contains("8"), advice.answer());
        assertTrue(advice.citations().stream().anyMatch(c -> c.type().equals("request")));
    }

    @Test
    void invalidCostParametersAreReported() {
        AssistantAdvice advice = service.advise(new AssistantRequest(1L, DATE, "如果把成本改成 20 元呢？",
                null, null, null, 5.0, 20.0, null, null));
        assertEquals("INVALID_COST_PARAMETERS", advice.refusal().code());
    }

    @Test
    void guardRejectsInventedNumbers() {
        Set<String> allowed = Set.of("100", "82");
        AssistantService.assertNoInventedNumbers("建议 100 份，基准 82 份。", allowed);
        assertThrows(IllegalStateException.class,
                () -> AssistantService.assertNoInventedNumbers("建议 100 份，预计能省 30 元。", allowed));
    }

    @Test
    void classificationIsDeterministic() {
        assertEquals(AssistantIntent.WHAT_IF, AssistantService.classify("假如售价 12 元呢"));
        assertEquals(AssistantIntent.EXPLAIN, AssistantService.classify("这个建议量怎么算的"));
        assertEquals(AssistantIntent.POINT_FORECAST, AssistantService.classify("销量预测一下"));
    }
}