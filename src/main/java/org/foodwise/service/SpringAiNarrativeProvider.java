package org.foodwise.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.foodwise.intelligence.Narrative;
import org.foodwise.intelligence.NarrativeProvider;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Primary;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.Map;
import java.util.Optional;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@Primary
@ConditionalOnProperty(name = "foodwise.ai.spring-ai-enabled", havingValue = "true")
public class SpringAiNarrativeProvider implements NarrativeProvider {
    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    public SpringAiNarrativeProvider(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    @Override
    public Optional<Narrative> generateNarrative(String scenario, Map<String, Object> facts) {
        try {
            String content = chatClient.prompt()
                    .system("你只返回JSON对象 {\"summary\":\"简短概括\"}，只做经营文字解释，不改变事实数字和经营决策。")
                    .user("场景: " + scenario + "\n事实: " + objectMapper.writeValueAsString(facts))
                    .call()
                    .content();
            if (content == null || content.isBlank()) return Optional.empty();
            JsonNode root = objectMapper.readTree(extractJson(content));
            String summary = root.path("summary").asText("").replaceAll("[\\r\\n]+", " ").trim();
            if (summary.isBlank()) return Optional.empty();
            if (summary.length() > 80 || !usesOnlyProvidedNumbers(summary, facts)) return Optional.empty();
            return Optional.of(new Narrative(summary, Collections.emptyList(), Collections.emptyList(), Collections.emptyList()));
        } catch (Exception ignored) {
            return Optional.empty();
        }
    }

    private String extractJson(String content) {
        int start = content.indexOf('{');
        int end = content.lastIndexOf('}');
        return start >= 0 && end > start ? content.substring(start, end + 1) : "{}";
    }

    private boolean usesOnlyProvidedNumbers(String summary, Map<String, Object> facts) throws Exception {
        Pattern pattern = Pattern.compile("\\d+(?:\\.\\d+)?");
        Set<String> allowed = new HashSet<>();
        Matcher factsMatcher = pattern.matcher(objectMapper.writeValueAsString(facts));
        while (factsMatcher.find()) allowed.add(factsMatcher.group());
        Matcher summaryMatcher = pattern.matcher(summary);
        while (summaryMatcher.find()) {
            if (!allowed.contains(summaryMatcher.group())) return false;
        }
        return true;
    }
}

