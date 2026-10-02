package org.foodwise.intelligence;

import java.util.List;

public record Narrative(String summary, List<String> reasons, List<String> actions, List<String> warnings) {
}

