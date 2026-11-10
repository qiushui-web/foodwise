package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.assistant.AssistantContractService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 参谋契约（只读）：能问什么、什么必拒、评测集有多大，页面与测试读同一份 CSV。 */
@RestController
@RequestMapping("/api/v1/assistant")
public class AssistantContractController {

    private final AssistantContractService service;

    public AssistantContractController(AssistantContractService service) {
        this.service = service;
    }

    @GetMapping("/contract")
    public ApiResponse<Map<String, Object>> contract(HttpServletRequest httpRequest) {
        return ApiResponse.success(service.contract(), ApiTrace.id(httpRequest));
    }
}