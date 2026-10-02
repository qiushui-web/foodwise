package org.foodwise.service;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class AmapWeatherService {
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final String apiKey;

    public AmapWeatherService(ObjectMapper objectMapper, @Value("${foodwise.amap.key:}") String apiKey) {
        this.objectMapper = objectMapper;
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(4)).build();
    }

    @Cacheable(cacheNames = "weather", key = "#city.trim().toLowerCase()", unless = "#result == null")
    public Map<String, Object> current(String city) {
        if (city == null || city.isBlank()) throw new IllegalArgumentException("请提供校区所在城市");
        if (apiKey.isBlank()) throw new IllegalStateException("高德天气接口未配置");
        try {
            String encodedCity = URLEncoder.encode(city.trim(), StandardCharsets.UTF_8);
            URI uri = URI.create("https://restapi.amap.com/v3/weather/weatherInfo?city=" + encodedCity
                    + "&extensions=base&output=JSON&key=" + apiKey);
            HttpRequest request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(8)).GET().build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode root = objectMapper.readTree(response.body());
            if (response.statusCode() < 200 || response.statusCode() >= 300 || !"1".equals(root.path("status").asText())) {
                throw new IllegalStateException("高德天气查询失败: " + root.path("info").asText("服务不可用"));
            }
            JsonNode live = root.path("lives").path(0);
            if (live.isMissingNode()) throw new IllegalStateException("高德未返回该城市天气");
            int temperature = live.path("temperature").asInt(20);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("city", live.path("city").asText(city.trim()));
            result.put("weather", normalizeWeather(live.path("weather").asText("晴"), temperature));
            result.put("weatherDetail", live.path("weather").asText(""));
            result.put("temperatureC", temperature);
            result.put("windDirection", live.path("winddirection").asText(""));
            result.put("windPower", live.path("windpower").asText(""));
            result.put("reportTime", live.path("reporttime").asText(""));
            result.put("source", "高德地图天气接口");
            return result;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("高德天气请求被中断", exception);
        } catch (Exception exception) {
            if (exception instanceof IllegalStateException state) throw state;
            throw new IllegalStateException("高德天气请求失败", exception);
        }
    }

    private String normalizeWeather(String detail, int temperature) {
        if (detail.contains("暴雨") || detail.contains("大雨") || detail.contains("雷阵雨")) return "大雨";
        if (detail.contains("雨") || detail.contains("雪")) return "小雨";
        if (temperature >= 32 || detail.contains("高温")) return "高温";
        if (temperature <= 5 || detail.contains("寒潮") || detail.contains("降温")) return "降温";
        return "晴";
    }
}

