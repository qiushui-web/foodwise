package org.foodwise.service;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import org.foodwise.intelligence.Narrative;
import org.foodwise.intelligence.NarrativeProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class ZhipuAiService implements NarrativeProvider {

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final String apiKey;
    private final String model;
    private final String endpoint;
    private final boolean enabled;

    public ZhipuAiService(
            ObjectMapper objectMapper,
            @Value("${foodwise.ai.api-key:}") String apiKey,
            @Value("${foodwise.ai.model:glm-4-flash}") String model,
            @Value("${foodwise.ai.endpoint:https://open.bigmodel.cn/api/paas/v4/chat/completions}") String endpoint,
            @Value("${foodwise.ai.enabled:true}") boolean enabled
    ) {
        this.objectMapper = objectMapper;
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.model = model;
        this.endpoint = endpoint;
        this.enabled = enabled;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(4))
                .build();
    }

    public boolean available() {
        return enabled && !apiKey.isBlank();
    }

    public String modelName() {
        return model;
    }

    public Optional<AiNarrative> generate(String scenario, Map<String, Object> facts) {
        if (!available()) return Optional.empty();
        try {
            String system = """
                    你只负责填写高校餐饮经营页面中的“经营概括”文字槽位，不负责计算、决策或改变展示结构。
                    所有数量、金额、时间、比例、风险等级、原因、经营动作和食品安全提示均由后端固定模板提供。
                    只返回JSON对象：{"summary":"简短概括"}。summary不超过70个汉字；如需引用数字，只能原样引用用户事实中已有的数字，
                    不增加用户事实中没有的结论，不使用夸张宣传语言，不返回标题、列表、Markdown或额外字段。
                    """;
            Map<String, Object> userPayload = Map.of("scenario", scenario, "facts", facts);
            Map<String, Object> requestBody = new LinkedHashMap<>();
            requestBody.put("model", model);
            requestBody.put("temperature", 0.2);
            requestBody.put("max_tokens", 650);
            requestBody.put("response_format", Map.of("type", "json_object"));
            requestBody.put("messages", List.of(
                    Map.of("role", "system", "content", system),
                    Map.of("role", "user", "content", objectMapper.writeValueAsString(userPayload))
            ));

            HttpRequest request = HttpRequest.newBuilder(URI.create(endpoint))
                    .timeout(Duration.ofSeconds(12))
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(requestBody), StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) return Optional.empty();

            JsonNode root = objectMapper.readTree(response.body());
            String content = root.path("choices").path(0).path("message").path("content").asText("");
            JsonNode narrative = objectMapper.readTree(extractJson(content));
            String summary = safeText(narrative.path("summary").asText(), 80);
            if (!usesOnlyProvidedNumbers(summary, userPayload)) summary = "";
            return Optional.of(new AiNarrative(
                    summary,
                    stringList(narrative.path("reasons"), 4),
                    stringList(narrative.path("actions"), 4),
                    stringList(narrative.path("warnings"), 3)
            ));
        } catch (Exception ignored) {
            return Optional.empty();
        }
    }

    @Override
    public Optional<Narrative> generateNarrative(String scenario, Map<String, Object> facts) {
        return generate(scenario, facts).map(value -> new Narrative(value.summary(), value.reasons(),
                value.actions(), value.warnings()));
    }

    /**
     * 通用 JSON 生成：允许大模型输出自己的独立判断数值（不做事实数字白名单过滤）。
     * 用于"训练模型 vs 大模型"混测：大模型需要基于事实独立给出预估区间与结论。
     */
    @SuppressWarnings("unchecked")
    public Optional<Map<String, Object>> generateJson(String systemPrompt, Map<String, Object> facts) {
        if (!available()) return Optional.empty();
        try {
            Map<String, Object> requestBody = new LinkedHashMap<>();
            requestBody.put("model", model);
            requestBody.put("temperature", 0.2);
            requestBody.put("max_tokens", 650);
            requestBody.put("response_format", Map.of("type", "json_object"));
            requestBody.put("messages", List.of(
                    Map.of("role", "system", "content", systemPrompt),
                    Map.of("role", "user", "content", objectMapper.writeValueAsString(facts))
            ));

            HttpRequest request = HttpRequest.newBuilder(URI.create(endpoint))
                    .timeout(Duration.ofSeconds(15))
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(requestBody), StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) return Optional.empty();

            JsonNode root = objectMapper.readTree(response.body());
            String content = root.path("choices").path(0).path("message").path("content").asText("");
            JsonNode parsedNode = objectMapper.readTree(extractJson(content));
            Map<String, Object> parsed = objectMapper.convertValue(parsedNode, Map.class);
            return Optional.of(parsed);
        } catch (Exception ignored) {
            return Optional.empty();
        }
    }

    private String extractJson(String text) {
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}');
        return start >= 0 && end > start ? text.substring(start, end + 1) : "{}";
    }

    private List<String> stringList(JsonNode node, int limit) {
        List<String> values = new ArrayList<>();
        if (!node.isArray()) return values;
        for (JsonNode item : node) {
            String value = safeText(item.asText(), 70);
            if (!value.isBlank()) values.add(value);
            if (values.size() >= limit) break;
        }
        return values;
    }

    private String safeText(String value, int maxLength) {
        if (value == null) return "";
        String cleaned = value.replaceAll("[\\r\\n]+", " ").trim();
        return cleaned.length() <= maxLength ? cleaned : cleaned.substring(0, maxLength);
    }

    private boolean usesOnlyProvidedNumbers(String summary, Map<String, Object> userPayload) {
        Pattern numberPattern = Pattern.compile("\\d+(?:\\.\\d+)?");
        Set<String> allowed = new HashSet<>();
        try {
            Matcher factNumbers = numberPattern.matcher(objectMapper.writeValueAsString(userPayload));
            while (factNumbers.find()) allowed.add(factNumbers.group());
        } catch (Exception exception) {
            return false;
        }
        Matcher summaryNumbers = numberPattern.matcher(summary);
        while (summaryNumbers.find()) {
            if (!allowed.contains(summaryNumbers.group())) return false;
        }
        return true;
    }

    public record AiNarrative(String summary, List<String> reasons, List<String> actions, List<String> warnings) {
    }
}

