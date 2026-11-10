package org.foodwise.assistant;

/**
 * 参谋能回答的五类问题，以及五类必须挡回去的问题。
 * 分类是确定性的：同一句话永远得到同一类，便于测试与审计。
 */
public enum AssistantIntent {
    EXPLAIN("解释建议量怎么来的"),
    WHAT_IF("给定新的成本参数，建议量会怎么变"),
    REVIEW("把建议与实际备餐对账"),
    POINT_FORECAST("要求一个点预测（拒绝）"),
    EFFECT_CLAIM("要求减损/收益承诺（拒绝）"),
    FOOD_SAFETY("食品安全判断（拒绝）"),
    OUT_OF_SCOPE("与经营无关（拒绝）");

    private final String description;

    AssistantIntent(String description) {
        this.description = description;
    }

    public String description() {
        return description;
    }
}