package org.foodwise.model;

import java.util.List;

public record IntelligentAdvice(
        long id,
        String title,
        String summary,
        String riskLevel,
        List<String> reasons,
        List<Action> actions,
        List<String> warnings,
        String source,
        boolean aiGenerated,
        String generatedAt
) {
    public record Action(String type, String title, String detail, String priority) {
    }
}

