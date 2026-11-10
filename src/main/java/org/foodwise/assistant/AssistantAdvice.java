package org.foodwise.assistant;

import java.util.List;

/**
 * 一次参谋问答的结果。所有数字必须来自 DecisionPreview 或请求本身，
 * 服务端在返回前用 {@link AssistantService#assertNoInventedNumbers} 逐字校验。
 */
public record AssistantAdvice(
        String intent,
        String answer,
        List<Citation> citations,
        SuggestedAction suggestedAction,
        Refusal refusal,
        String modelVersion,
        String calibrationSha256
) {
    public record Citation(String type, String ref) {
    }

    public record SuggestedAction(int quantity, String reason) {
    }

    public record Refusal(String code, String reason) {
    }

    public static AssistantAdvice refuse(String intent, Refusal refusal, String modelVersion,
                                         String calibrationSha256) {
        return new AssistantAdvice(intent, refusal.reason(), List.of(), null, refusal,
                modelVersion, calibrationSha256);
    }
}