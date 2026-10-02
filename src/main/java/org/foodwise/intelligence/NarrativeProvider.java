package org.foodwise.intelligence;

import java.util.Map;
import java.util.Optional;

public interface NarrativeProvider {
    Optional<Narrative> generateNarrative(String scenario, Map<String, Object> facts);
}

