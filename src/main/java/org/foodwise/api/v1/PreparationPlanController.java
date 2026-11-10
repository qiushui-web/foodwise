package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.prediction.PreparationPlanner;
import org.foodwise.service.PreparationPlanService;
import org.foodwise.service.ApiIdempotencyService;
import org.foodwise.service.AuditService;
import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/v1")
public class PreparationPlanController {
    private final PreparationPlanService plans;
    private final ApiIdempotencyService idempotency;
    private final AuditService audit;
    public PreparationPlanController(PreparationPlanService plans, ApiIdempotencyService idempotency, AuditService audit) {
        this.plans = plans; this.idempotency = idempotency; this.audit = audit;
    }
    @PostMapping("/predictions/{id}/preparation-plans")
    @Transactional
    public ApiResponse<?> create(@PathVariable long id, @RequestBody PreparationPlanner.Inputs input, HttpServletRequest request) {
        idempotency.reserve(request, "preparation-plan.create");
        var auth = SecurityContextHolder.getContext().getAuthentication();
        var result = plans.create(id, input, auth == null ? "anonymous" : auth.getName());
        audit.record(request, "preparation-plan.create", "preparation_plan", String.valueOf(result.get("id")));
        return ApiResponse.success(result, ApiTrace.id(request));
    }
    @PostMapping("/decisions/{id}/preparation-plans")
    @Transactional
    public ApiResponse<?> createForDecision(@PathVariable long id, @RequestParam String mealPeriod,
            @RequestBody PreparationPlanner.Inputs input, HttpServletRequest request) {
        idempotency.reserve(request, "preparation-plan.create");
        var auth = SecurityContextHolder.getContext().getAuthentication();
        var result = plans.createForDecision(id, mealPeriod, input, auth == null ? "anonymous" : auth.getName());
        audit.record(request, "preparation-plan.create", "decision_preparation_plan", String.valueOf(result.get("id")));
        return ApiResponse.success(result, ApiTrace.id(request));
    }
    @GetMapping("/preparation-plans/{id}")
    public ApiResponse<?> read(@PathVariable long id, HttpServletRequest request) {
        return ApiResponse.success(plans.read(id), ApiTrace.id(request));
    }
    @GetMapping("/decision-preparation-plans/{id}")
    public ApiResponse<?> readDecision(@PathVariable long id, HttpServletRequest request) {
        return ApiResponse.success(plans.readDecisionPlan(id), ApiTrace.id(request));
    }
}
