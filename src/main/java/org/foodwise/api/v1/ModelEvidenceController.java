package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.decision.ModelEvidenceService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 只读证据接口：前端“证据与复现”页的全部数据来源。 */
@RestController
@RequestMapping("/api/v1/model")
public class ModelEvidenceController {

    private final ModelEvidenceService evidenceService;

    public ModelEvidenceController(ModelEvidenceService evidenceService) {
        this.evidenceService = evidenceService;
    }

    @GetMapping("/evidence")
    public ApiResponse<Map<String, Object>> evidence(HttpServletRequest httpRequest) {
        return ApiResponse.success(evidenceService.evidence(), ApiTrace.id(httpRequest));
    }
}