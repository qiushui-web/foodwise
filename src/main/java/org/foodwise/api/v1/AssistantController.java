package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.assistant.AssistantAdvice;
import org.foodwise.assistant.AssistantIntent;
import org.foodwise.assistant.AssistantRequest;
import org.foodwise.assistant.AssistantService;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 经营参谋接口：只解释、只对账、只回答给定参数下的变化；不预测点值、不承诺效果。
 *
 * POST /api/v1/assistant/advice  问一次
 * GET  /api/v1/assistant/scope   列出能问什么、什么会被挡回去
 */
@RestController
@RequestMapping("/api/v1/assistant")
public class AssistantController {

    private final AssistantService service;

    public AssistantController(AssistantService service) {
        this.service = service;
    }

    @PostMapping("/advice")
    public ApiResponse<AssistantAdvice> advice(@Valid @RequestBody AssistantRequest request,
                                               HttpServletRequest httpRequest) {
        return ApiResponse.success(service.advise(request), ApiTrace.id(httpRequest));
    }

    @GetMapping("/scope")
    public ApiResponse<Map<String, Object>> scope(HttpServletRequest httpRequest) {
        List<Map<String, String>> answerable = List.of(
                Map.of("intent", "EXPLAIN", "description", AssistantIntent.EXPLAIN.description()),
                Map.of("intent", "WHAT_IF", "description", AssistantIntent.WHAT_IF.description()),
                Map.of("intent", "REVIEW", "description", AssistantIntent.REVIEW.description()));
        List<Map<String, String>> refused = List.of(
                Map.of("code", "NO_POINT_FORECAST", "description", "不给单点预测，只给区间与建议量"),
                Map.of("code", "NO_EFFECT_CLAIM", "description", "不承诺减损比例或收益"),
                Map.of("code", "OUT_OF_SCOPE_FOOD_SAFETY", "description", "不判断食品安全"),
                Map.of("code", "OUT_OF_SCOPE", "description", "不回答与经营无关的问题"),
                Map.of("code", "REVIEW_NEEDS_ACTUALS", "description", "复盘需要实际备餐与实际售出"),
                Map.of("code", "INVALID_COST_PARAMETERS", "description", "成本参数不合法"));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("answerable", answerable);
        payload.put("refused", refused);
        payload.put("rules", List.of(
                "回答中的每个数字都必须来自决策预览或你给的参数",
                "口径与 /api/v1/decisions/preview 完全一致，可用同一 dishId 对照"));
        return ApiResponse.success(payload, ApiTrace.id(httpRequest));
    }
}