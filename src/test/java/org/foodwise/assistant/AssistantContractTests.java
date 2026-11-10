package org.foodwise.assistant;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 契约接口与评测集必须同源：页面上的"50 条 / 26 条拒绝"只能来自 CSV。
 */
@SpringBootTest
class AssistantContractTests {

    @Autowired
    AssistantContractService service;

    @Test
    @DisplayName("契约里的条数与 CSV 完全一致")
    void countsComeFromTheCsv() {
        Map<String, Object> payload = service.contract();
        @SuppressWarnings("unchecked")
        Map<String, Object> eval = (Map<String, Object>) payload.get("eval");

        List<AssistantContractService.EvalCase> cases = service.loadCases();
        assertEquals(cases.size(), eval.get("cases"));
        assertEquals(50, eval.get("cases"), "评测集应为 50 条");

        long refused = cases.stream().filter(c -> !c.refusal().isBlank()).count();
        assertEquals((int) refused, eval.get("refused"));
        assertEquals(26, eval.get("refused"), "其中 26 条必须拒绝");
        assertEquals((int) (cases.size() - refused), eval.get("answerable"));
    }

    @Test
    @DisplayName("五类拒绝码都有解释与示例问法")
    void everyRefusalCodeExplainsItself() {
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> refusals = (List<Map<String, Object>>) service.contract().get("refusals");
        assertEquals(5, refusals.size());
        for (var row : refusals) {
            assertNotNull(row.get("code"));
            assertTrue(((String) row.get("reason")).length() > 10, "拒绝码 " + row.get("code") + " 缺少解释");
            @SuppressWarnings("unchecked")
            List<String> examples = (List<String>) row.get("examples");
            assertFalse(examples.isEmpty(), "拒绝码 " + row.get("code") + " 没有示例问法");
        }
    }

    @Test
    @DisplayName("七类问法的条数之和等于评测集总数")
    void categoryCountsAddUp() {
        @SuppressWarnings("unchecked")
        Map<String, Object> eval = (Map<String, Object>) service.contract().get("eval");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> categories = (List<Map<String, Object>>) eval.get("by_category");
        assertEquals(7, categories.size());
        int sum = categories.stream().mapToInt(c -> (int) c.get("count")).sum();
        assertEquals(eval.get("cases"), sum);
    }
}