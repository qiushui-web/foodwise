package org.foodwise.assistant;

import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * 参谋契约与评测摘要：数据只来自 {@code assistant/eval_cases.csv}，页面看到的条数就是测试跑过的条数。
 *
 * 之所以做成接口而不是写死在页面里，是因为"50 条评测全绿"这种说法一旦离开测试就没人能核对——
 * 这里让测试和页面读同一个文件，两边对不上就是 bug。
 */
@Service
public class AssistantContractService {

    static final String CASES_RESOURCE = "/assistant/eval_cases.csv";

    /** 每条拒绝码的解释：为什么拒、拒的是哪类问法。 */
    private static final Map<String, String> REFUSAL_REASONS = Map.of(
            "NO_POINT_FORECAST", "不输出单点预测：只给区间与建议量，单个数会掩盖边界条件",
            "NO_EFFECT_CLAIM", "不承诺减损比例或收益：当前只能证明方法与程序可复现",
            "OUT_OF_SCOPE_FOOD_SAFETY", "不判断食品安全：交给食堂监管与留样制度",
            "OUT_OF_SCOPE", "不回答与备餐经营无关的问题",
            "REVIEW_NEEDS_ACTUALS", "复盘必须给实际备餐量与实际售出量，否则只能复述建议值");

    private static final Map<String, String> CATEGORY_LABELS = new LinkedHashMap<>();

    static {
        CATEGORY_LABELS.put("explain", "解释依据");
        CATEGORY_LABELS.put("what_if", "成本试算");
        CATEGORY_LABELS.put("review", "复盘对账");
        CATEGORY_LABELS.put("forecast", "点预测（必拒）");
        CATEGORY_LABELS.put("effect", "效果承诺（必拒）");
        CATEGORY_LABELS.put("food_safety", "食品安全（必拒）");
        CATEGORY_LABELS.put("out_of_scope", "无关问题（必拒）");
    }

    record EvalCase(int id, String category, String question, String intent, String refusal) {
    }

    public Map<String, Object> contract() {
        List<EvalCase> cases = loadCases();
        Map<String, Integer> byCategory = new LinkedHashMap<>();
        Map<String, List<String>> examples = new LinkedHashMap<>();
        int refused = 0;
        for (EvalCase c : cases) {
            byCategory.merge(c.category(), 1, Integer::sum);
            if (!c.refusal().isBlank()) {
                refused += 1;
                examples.computeIfAbsent(c.refusal(), k -> new ArrayList<>()).add(c.question());
            }
        }

        List<Map<String, Object>> categories = new ArrayList<>();
        byCategory.forEach((key, count) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("key", key);
            row.put("label", CATEGORY_LABELS.getOrDefault(key, key));
            row.put("count", count);
            categories.add(row);
        });

        List<Map<String, Object>> refusals = new ArrayList<>();
        for (String code : List.of("NO_POINT_FORECAST", "NO_EFFECT_CLAIM", "OUT_OF_SCOPE_FOOD_SAFETY",
                "OUT_OF_SCOPE", "REVIEW_NEEDS_ACTUALS")) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("code", code);
            row.put("reason", REFUSAL_REASONS.get(code));
            row.put("examples", examples.getOrDefault(code, List.of()));
            row.put("count", examples.getOrDefault(code, List.of()).size());
            refusals.add(row);
        }

        List<Map<String, String>> answerable = new ArrayList<>();
        for (AssistantIntent intent : List.of(AssistantIntent.EXPLAIN, AssistantIntent.WHAT_IF,
                AssistantIntent.REVIEW)) {
            answerable.add(Map.of("intent", intent.name(), "description", intent.description()));
        }

        Map<String, Object> eval = new LinkedHashMap<>();
        eval.put("cases", cases.size());
        eval.put("refused", refused);
        eval.put("answerable", cases.size() - refused);
        eval.put("by_category", categories);
        eval.put("resource", CASES_RESOURCE);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("answerable", answerable);
        payload.put("refusals", refusals);
        payload.put("eval", eval);
        payload.put("citations", List.of(
                Map.of("type", "plan", "meaning", "建议量、中心值"),
                Map.of("type", "interval", "meaning", "区间上下限"),
                Map.of("type", "cost", "meaning", "临界比、缺货与剩余损失"),
                Map.of("type", "model", "meaning", "模型版本"),
                Map.of("type", "request", "meaning", "本次请求里你给的参数")));
        payload.put("rules", List.of(
                "回答里的每个数字都必须来自决策预览或你给的参数，否则直接报错而不是编一个",
                "口径与 /api/v1/decisions/preview 完全一致，可用同一 dishId 对照"));
        return payload;
    }

    List<EvalCase> loadCases() {
        try (var stream = getClass().getResourceAsStream(CASES_RESOURCE)) {
            if (stream == null) throw new IllegalStateException("EVAL_CASES_MISSING:" + CASES_RESOURCE);
            BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
            String line = reader.readLine();
            List<EvalCase> cases = new ArrayList<>();
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] cells = line.split(",", -1);
                if (cells.length < 5) throw new IllegalStateException("EVAL_CASE_MALFORMED:" + line);
                cases.add(new EvalCase(Integer.parseInt(cells[0].trim()), cells[1].trim(), cells[2].trim(),
                        cells[3].trim(), cells[4].trim()));
            }
            return cases;
        } catch (IOException error) {
            throw new UncheckedIOException(error);
        }
    }
}