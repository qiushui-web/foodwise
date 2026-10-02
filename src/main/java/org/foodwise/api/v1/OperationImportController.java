package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.service.ApiIdempotencyService;
import org.foodwise.service.AuditService;
import org.foodwise.service.OperationImportService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/operations")
public class OperationImportController {
    private final OperationImportService importService;
    private final ApiIdempotencyService idempotency;
    private final AuditService audit;

    public OperationImportController(OperationImportService importService,
                                     ApiIdempotencyService idempotency,
                                     AuditService audit) {
        this.importService = importService;
        this.idempotency = idempotency;
        this.audit = audit;
    }

    @PostMapping(value = "/import/preview", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Map<String, Object>> preview(@RequestPart("file") MultipartFile file,
                                                     HttpServletRequest request) {
        return ApiResponse.success(importService.previewCsv(file), ApiTrace.id(request));
    }

    @PostMapping(value = "/import", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Map<String, Object>> importCsv(@RequestPart("file") MultipartFile file,
                                                       @RequestParam String operatorName,
                                                       @RequestParam boolean safetyConfirmed,
                                                       HttpServletRequest request) {
        idempotency.reserve(request, "operations.import");
        Map<String, Object> result = importService.importCsv(file, operatorName, safetyConfirmed);
        audit.record(request, "operations.import", "operation_import", String.valueOf(result.getOrDefault("batchId", "unknown")));
        return ApiResponse.success(result, ApiTrace.id(request));
    }
}

