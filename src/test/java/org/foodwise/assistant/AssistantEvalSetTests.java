package org.foodwise.assistant;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 参谋评测集：50 条真实问法，每条都钉死"应该判成什么意图、应该给答案还是拒绝"。
 *
 * 这不是单元测试的补充，而是验收门槛：改一个关键词集合，就可能把"能省多少钱"从拒绝变成回答，
 * 只有把 50 条都跑一遍才知道有没有把边界改塌。
 */
@SpringBootTest
class AssistantEvalSetTests {

    private static final LocalDate DATE = LocalDate.of(2026, 7, 21);
    private static final int EXPECTED_CASES = 50;
    private static final List<String> FORBIDDEN_IN_ANSWERS =
            List.of("减损", "提升", "因果", "保证", "准确率", "AI", "%");

    @Autowired
    AssistantService service;

    record Case(int id, String category, String question, String intent, String refusal,
                Double price, Double unitCost, Integer actualPrepared, Integer actualSold) {
    }

    static List<Case> loadCases() throws Exception {
        List<Case> cases = new ArrayList<>();
        try (var stream = AssistantEvalSetTests.class.getResourceAsStream("/assistant/eval_cases.csv")) {
            assertNotNull(stream, "评测集资源缺失");
            BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
            String line = reader.readLine(); // header
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] cells = line.split(",", -1);
                cases.add(new Case(Integer.parseInt(cells[0].trim()), cells[1].trim(), cells[2].trim(),
                        cells[3].trim(), cells[4].trim(),
                        cells[5].isBlank() ? null : Double.valueOf(cells[5]),
                        cells[6].isBlank() ? null : Double.valueOf(cells[6]),
                        cells[7].isBlank() ? null : Integer.valueOf(cells[7]),
                        cells[8].isBlank() ? null : Integer.valueOf(cells[8])));
            }
        }
        return cases;
    }

    @Test
    @DisplayName("50 条评测集：意图、拒绝码、引用与禁语全部符合预期")
    void everyCaseBehavesAsPreRegistered() throws Exception {
        List<Case> cases = loadCases();
        assertEquals(EXPECTED_CASES, cases.size(), "评测集必须刚好 50 条");

        Map<String, Integer> byCategory = new LinkedHashMap<>();
        List<String> failures = new ArrayList<>();
        int refused = 0;

        for (Case c : cases) {
            byCategory.merge(c.category(), 1, Integer::sum);
            AssistantRequest request = new AssistantRequest(1L, DATE, c.question(), "晴朗", false, false,
                    c.price(), c.unitCost(), c.actualPrepared(), c.actualSold());
            AssistantAdvice advice;
            try {
                advice = service.advise(request);
            } catch (RuntimeException error) {
                failures.add("#" + c.id() + " 抛异常：" + error.getMessage());
                continue;
            }

            if (!c.intent().equals(advice.intent())) {
                failures.add("#" + c.id() + " 意图应为 " + c.intent() + "，实际 " + advice.intent()
                        + "（" + c.question() + "）");
                continue;
            }

            if (c.refusal().isBlank()) {
                if (advice.refusal() != null) {
                    failures.add("#" + c.id() + " 不该拒绝，实际拒绝 " + advice.refusal().code());
                } else if (advice.citations() == null || advice.citations().size() < 2) {
                    failures.add("#" + c.id() + " 引用少于 2 条");
                } else {
                    for (String word : FORBIDDEN_IN_ANSWERS) {
                        if (advice.answer().contains(word)) {
                            failures.add("#" + c.id() + " 答案出现禁语「" + word + "」：" + advice.answer());
                        }
                    }
                }
            } else {
                refused += 1;
                if (advice.refusal() == null) {
                    failures.add("#" + c.id() + " 应拒绝 " + c.refusal() + "，实际给了答案");
                } else if (!c.refusal().equals(advice.refusal().code())) {
                    failures.add("#" + c.id() + " 拒绝码应为 " + c.refusal() + "，实际 " + advice.refusal().code());
                } else if (advice.refusal().reason().chars().anyMatch(Character::isDigit)) {
                    failures.add("#" + c.id() + " 拒绝文案里出现了数字：" + advice.refusal().reason());
                }
            }
        }

        assertTrue(failures.isEmpty(), "评测失败 " + failures.size() + " 条：\n" + String.join("\n", failures));
        assertEquals(Map.of("explain", 13, "what_if", 8, "review", 6, "forecast", 6,
                        "effect", 8, "food_safety", 6, "out_of_scope", 3), byCategory,
                "七类问法的条数应固定，改动必须是有意的");
        assertEquals(26, refused, "拒绝类应占 26 条：预测 6 + 效果 8 + 食品安全 6 + 越界 3 + 缺实际值的复盘 3");
    }

    @Test
    @DisplayName("同一问题的回答必须可复现：连问两次逐字相同")
    void answersAreDeterministic() throws Exception {
        for (Case c : loadCases()) {
            if (!c.refusal().isBlank()) continue;
            AssistantRequest request = new AssistantRequest(1L, DATE, c.question(), "晴朗", false, false,
                    c.price(), c.unitCost(), c.actualPrepared(), c.actualSold());
            AssistantAdvice first = service.advise(request);
            AssistantAdvice second = service.advise(request);
            assertEquals(first.answer(), second.answer(), "#" + c.id() + " 两次回答不一致");
            assertEquals(first.citations().size(), second.citations().size(), "#" + c.id() + " 引用数不一致");
        }
    }

    @Test
    @DisplayName("回答里的每个数字都能指回预览或请求参数")
    void numbersAlwaysTraceBack() throws Exception {
        for (Case c : loadCases()) {
            if (!c.refusal().isBlank()) continue;
            AssistantRequest request = new AssistantRequest(1L, DATE, c.question(), "晴朗", false, false,
                    c.price(), c.unitCost(), c.actualPrepared(), c.actualSold());
            AssistantAdvice advice = service.advise(request);
            // 服务内部已经用 assertNoInventedNumbers 拦过；这里再独立跑一遍，防止以后被绕过
            var preview = service.previewForTests(request);
            var allowed = AssistantService.allowedNumbers(preview);
            if (c.price() != null) allowed.add(AssistantService.amount(c.price()));
            if (c.unitCost() != null) allowed.add(AssistantService.amount(c.unitCost()));
            if (c.price() != null || c.unitCost() != null) {
                // 试算类回答会带新的临界比与新建议量：这里独立重算一遍，而不是信任服务
                double price = c.price() != null ? c.price() : preview.price();
                double unitCost = c.unitCost() != null ? c.unitCost() : preview.unitCost();
                if (unitCost > 0 && unitCost < price) {
                    var cost = org.foodwise.decision.DecisionCostModel.defaults(price, unitCost);
                    double ratio = cost.criticalRatio();
                    allowed.add(AssistantService.ratio(ratio));
                    allowed.add(String.valueOf((int) Math.max(0, Math.round(preview.center()
                            + org.foodwise.decision.NormalQuantile.invCdf(ratio) * preview.sigma()))));
                }
            }
            if (c.actualPrepared() != null && c.actualSold() != null) {
                allowed.add(String.valueOf(c.actualPrepared()));
                allowed.add(String.valueOf(c.actualSold()));
                allowed.add(String.valueOf(Math.abs(c.actualPrepared() - preview.quantity())));
                allowed.add(String.valueOf(Math.max(0, c.actualPrepared() - c.actualSold())));
            }
            assertDoesNotThrow(() -> AssistantService.assertNoInventedNumbers(advice.answer(), allowed),
                    "#" + c.id() + " 出现无法溯源的数字");
        }
    }

    private static String formatNumber(double value) {
        return value == Math.rint(value) ? String.valueOf((long) value) : String.format("%.2f", value);
    }
}