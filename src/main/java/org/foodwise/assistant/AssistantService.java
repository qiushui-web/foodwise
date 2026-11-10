package org.foodwise.assistant;

import org.foodwise.decision.BaselineDecisionEngine;
import org.foodwise.decision.DecisionCostModel;
import org.foodwise.decision.DecisionPreview;
import org.foodwise.decision.NormalQuantile;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 确定性参谋：不接大模型，所有数字都来自决策预览或用户给定的参数。
 *
 * 三条硬规则：
 * 1. 不做点预测、不做效果承诺、不判断食品安全——这三类直接拒绝；
 * 2. 回答里的每个数字必须出现在"允许集合"里，否则抛异常（宁可报错也不编数）；
 * 3. 每句话都带引用，指回具体字段或请求参数。
 */
@Service
public class AssistantService {

    static final Pattern NUMBER = Pattern.compile("\\d+(?:\\.\\d+)?");
    static final Set<String> FOOD_SAFETY_WORDS = Set.of("新鲜", "变质", "能不能吃", "食品安全", "保质", "卫生");
    static final Set<String> EFFECT_WORDS = Set.of("省", "减损", "降低浪费", "提升利润", "回报", "能省多少", "百分之");
    static final Set<String> FORECAST_WORDS = Set.of("能卖多少", "卖多少", "销量预测", "卖几份", "明天卖");
    static final Set<String> REVIEW_WORDS = Set.of("复盘", "对账", "实际备", "偏差");
    static final Set<String> WHAT_IF_WORDS = Set.of("如果", "假如", "要是", "换成", "改成", "假设");
    static final Set<String> EXPLAIN_WORDS = Set.of("为什么", "怎么算", "依据", "来源", "怎么来的", "解释");
    static final Set<String> DOMAIN_WORDS = Set.of("菜", "备", "建议", "份", "成本", "区间", "剩余",
            "售", "库存", "档口", "折价", "定价");

    private final BaselineDecisionEngine engine;

    public AssistantService(BaselineDecisionEngine engine) {
        this.engine = engine;
    }

    public AssistantAdvice advise(AssistantRequest request) {
        AssistantIntent intent = classify(request.question());
        if (intent == AssistantIntent.POINT_FORECAST) {
            return AssistantAdvice.refuse(intent.name(),
                    new AssistantAdvice.Refusal("NO_POINT_FORECAST",
                            "只能给出区间与建议量，不给点预测；单一数字会让边界条件看起来比实际确定。"),
                    null, null);
        }
        if (intent == AssistantIntent.EFFECT_CLAIM) {
            return AssistantAdvice.refuse(intent.name(),
                    new AssistantAdvice.Refusal("NO_EFFECT_CLAIM",
                            "不能承诺减损或收益比例。当前能证明的只有方法与程序可复现，校园成效尚未验证。"),
                    null, null);
        }
        if (intent == AssistantIntent.FOOD_SAFETY) {
            return AssistantAdvice.refuse(intent.name(),
                    new AssistantAdvice.Refusal("OUT_OF_SCOPE_FOOD_SAFETY",
                            "食品安全判断不在本系统范围内，请交给食堂监管与留样制度。"),
                    null, null);
        }
        if (intent == AssistantIntent.OUT_OF_SCOPE) {
            return AssistantAdvice.refuse(intent.name(),
                    new AssistantAdvice.Refusal("OUT_OF_SCOPE",
                            "这个问题与备餐经营无关。可问：建议量怎么来的、换一组成本参数会怎样、建议与实际差多少。"),
                    null, null);
        }

        DecisionPreview preview = engine.preview(request.dishId(),
                request.targetDate() == null ? java.time.LocalDate.now().plusDays(1) : request.targetDate());
        Set<String> allowed = allowedNumbers(preview);
        List<AssistantAdvice.Citation> citations = baseCitations(preview);

        return switch (intent) {
            case EXPLAIN -> explain(preview, allowed, citations);
            case WHAT_IF -> whatIf(request, preview, allowed, citations);
            case REVIEW -> review(request, preview, allowed, citations);
            default -> throw new IllegalStateException("未处理意图:" + intent);
        };
    }

    private AssistantAdvice explain(DecisionPreview preview, Set<String> allowed,
                                     List<AssistantAdvice.Citation> citations) {
        int quantity = preview.quantity();
        String answer = "建议 %s 份：基准是同菜品同星期近四周的售出中位数 %s 份，按成本临界比 %s 上浮、再按最小批次取整。"
                .formatted(integer(quantity), amount(preview.center()), ratio(preview.criticalRatio()))
                + "区间 %s–%s 份；建议量取的是少断货，因为缺货损失 %s 元远高于剩余损失 %s 元。"
                .formatted(amount(preview.intervalLow()), amount(preview.intervalHigh()),
                        amount(preview.underage()), amount(preview.overage()));
        assertNoInventedNumbers(answer, allowed);
        return new AssistantAdvice(AssistantIntent.EXPLAIN.name(), answer, citations,
                new AssistantAdvice.SuggestedAction(quantity, "按当前成本参数的最优备餐量"),
                null, preview.modelVersion(), null);
    }

    private AssistantAdvice whatIf(AssistantRequest request, DecisionPreview preview, Set<String> allowed,
                                   List<AssistantAdvice.Citation> citations) {
        double price = request.price() == null ? preview.price() : request.price();
        double unitCost = request.unitCost() == null ? preview.unitCost() : request.unitCost();
        DecisionCostModel costModel;
        try {
            costModel = DecisionCostModel.defaults(price, unitCost);
        } catch (IllegalArgumentException invalid) {
            return AssistantAdvice.refuse(AssistantIntent.WHAT_IF.name(),
                    new AssistantAdvice.Refusal("INVALID_COST_PARAMETERS",
                            "成本参数不合法：售价必须大于零，单位成本必须大于零且低于售价。"),
                    preview.modelVersion(), null);
        }
        double newRatio = costModel.criticalRatio();
        int newQuantity = (int) Math.max(0,
                Math.round(preview.center() + NormalQuantile.invCdf(newRatio) * preview.sigma()));
        allowed.add(amount(price));
        allowed.add(amount(unitCost));
        allowed.add(ratio(newRatio));
        allowed.add(integer(newQuantity));
        List<AssistantAdvice.Citation> merged = new ArrayList<>(citations);
        merged.add(new AssistantAdvice.Citation("request", "price=" + amount(price) + ", unitCost=" + amount(unitCost)));
        String answer = "若按售价 %s 元、单位成本 %s 元重算：临界比从 %s 变为 %s，建议量从 %s 变为 %s 份（未按批次取整）。"
                .formatted(amount(price), amount(unitCost), ratio(preview.criticalRatio()), ratio(newRatio),
                        integer(preview.quantity()), integer(newQuantity));
        assertNoInventedNumbers(answer, allowed);
        return new AssistantAdvice(AssistantIntent.WHAT_IF.name(), answer, merged,
                new AssistantAdvice.SuggestedAction(newQuantity, "按你给的成本参数重算的建议量"),
                null, preview.modelVersion(), null);
    }

    private AssistantAdvice review(AssistantRequest request, DecisionPreview preview, Set<String> allowed,
                                   List<AssistantAdvice.Citation> citations) {
        if (request.actualPrepared() == null || request.actualSold() == null) {
            return AssistantAdvice.refuse(AssistantIntent.REVIEW.name(),
                    new AssistantAdvice.Refusal("REVIEW_NEEDS_ACTUALS",
                            "复盘需要你提供实际备餐量与实际售出量，否则只能复述建议值。"),
                    preview.modelVersion(), null);
        }
        int actualPrepared = request.actualPrepared();
        int actualSold = request.actualSold();
        int gap = actualPrepared - preview.quantity();
        int leftover = Math.max(0, actualPrepared - actualSold);
        allowed.add(integer(actualPrepared));
        allowed.add(integer(actualSold));
        allowed.add(integer(Math.abs(gap)));
        allowed.add(integer(leftover));
        List<AssistantAdvice.Citation> merged = new ArrayList<>(citations);
        merged.add(new AssistantAdvice.Citation("request",
                "actualPrepared=" + actualPrepared + ", actualSold=" + actualSold));
        String answer = "建议 %s 份，实际备 %s 份，比建议%s备 %s 份；按实际售出 %s 份算，剩余 %s 份。"
                .formatted(integer(preview.quantity()), integer(actualPrepared), gap >= 0 ? "多" : "少",
                        integer(Math.abs(gap)), integer(actualSold), integer(leftover));
        assertNoInventedNumbers(answer, allowed);
        return new AssistantAdvice(AssistantIntent.REVIEW.name(), answer, merged, null, null,
                preview.modelVersion(), null);
    }

    /** 评测集用它独立复算允许集合，避免"服务自己说自己没编数"。 */
    DecisionPreview previewForTests(AssistantRequest request) {
        return engine.preview(request.dishId(),
                request.targetDate() == null ? java.time.LocalDate.now().plusDays(1) : request.targetDate());
    }

    static AssistantIntent classify(String question) {
        String text = question == null ? "" : question;
        if (containsAny(text, FOOD_SAFETY_WORDS)) return AssistantIntent.FOOD_SAFETY;
        if (containsAny(text, EFFECT_WORDS)) return AssistantIntent.EFFECT_CLAIM;
        if (containsAny(text, FORECAST_WORDS)) return AssistantIntent.POINT_FORECAST;
        if (containsAny(text, REVIEW_WORDS) || text.contains("昨天")) return AssistantIntent.REVIEW;
        if (containsAny(text, WHAT_IF_WORDS)) return AssistantIntent.WHAT_IF;
        if (containsAny(text, EXPLAIN_WORDS)) return AssistantIntent.EXPLAIN;
        if (containsAny(text, DOMAIN_WORDS)) return AssistantIntent.EXPLAIN;
        return AssistantIntent.OUT_OF_SCOPE;
    }

    private static boolean containsAny(String text, Set<String> words) {
        return words.stream().anyMatch(text::contains);
    }

    static Set<String> allowedNumbers(DecisionPreview preview) {
        Set<String> allowed = new LinkedHashSet<>();
        allowed.add(integer(preview.quantity()));
        allowed.add(integer(preview.firstBatch()));
        allowed.add(integer(preview.replenish()));
        allowed.add(amount(preview.center()));
        allowed.add(amount(preview.sigma()));
        allowed.add(amount(preview.intervalLow()));
        allowed.add(amount(preview.intervalHigh()));
        allowed.add(amount(preview.q05()));
        allowed.add(amount(preview.q95()));
        allowed.add(amount(preview.underage()));
        allowed.add(amount(preview.overage()));
        allowed.add(amount(preview.price()));
        allowed.add(amount(preview.unitCost()));
        allowed.add(ratio(preview.criticalRatio()));
        return allowed;
    }

    /** 回答里出现任何未被允许的数字，就直接失败——这是"不编数"的最后一道闸。 */
    public static void assertNoInventedNumbers(String answer, Set<String> allowed) {
        Matcher matcher = NUMBER.matcher(answer);
        while (matcher.find()) {
            String token = matcher.group();
            if (!allowed.contains(token) && !allowed.contains(normalize(token))) {
                throw new IllegalStateException("INVENTED_NUMBER:" + token + " in: " + answer);
            }
        }
    }

    private static String normalize(String token) {
        return new BigDecimal(token).stripTrailingZeros().toPlainString();
    }

    static String integer(int value) {
        return Integer.toString(value);
    }

    static String amount(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString();
    }

    static String ratio(double value) {
        return BigDecimal.valueOf(value).setScale(3, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString();
    }

    private static String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private List<AssistantAdvice.Citation> baseCitations(DecisionPreview preview) {
        List<AssistantAdvice.Citation> citations = new ArrayList<>();
        citations.add(new AssistantAdvice.Citation("plan",
                "quantity=" + preview.quantity() + ", center=" + amount(preview.center())));
        citations.add(new AssistantAdvice.Citation("interval",
                "low=" + amount(preview.intervalLow()) + ", high=" + amount(preview.intervalHigh())));
        citations.add(new AssistantAdvice.Citation("cost",
                "criticalRatio=" + ratio(preview.criticalRatio()) + ", underage=" + amount(preview.underage())
                        + ", overage=" + amount(preview.overage())));
        citations.add(new AssistantAdvice.Citation("model", "modelVersion=" + preview.modelVersion()));
        return citations;
    }
}