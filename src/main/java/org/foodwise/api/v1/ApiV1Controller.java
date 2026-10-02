package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.api.ApiIdempotency;
import org.foodwise.model.PredictionResult;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.PredictionOrchestrator;
import org.foodwise.service.AnalyticsService;
import org.foodwise.service.FoodwiseService;
import org.foodwise.service.OperationFeedbackService;
import org.foodwise.service.IntelligentDecisionService;
import org.foodwise.service.ApiIdempotencyService;
import org.foodwise.service.AuditService;
import org.foodwise.service.AmapWeatherService;
import org.foodwise.api.PageResponse;
import org.foodwise.model.OfferRecommendation;
import org.foodwise.model.OperationLearningResult;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalTime;
import org.foodwise.model.dto.DashboardSummary;
import org.foodwise.model.dto.DishInfo;
import org.foodwise.model.dto.OperationRow;
import org.foodwise.model.dto.ReportSummary;
import org.foodwise.model.dto.StallInfo;
import org.foodwise.model.dto.TrendPoint;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.Map;

@RestController
@RequestMapping("/api/v1")
public class ApiV1Controller {
    private final PredictionOrchestrator predictions;
    private final AnalyticsService analytics;
    private final FoodwiseService foodwise;
    private final OperationFeedbackService feedback;
    private final IntelligentDecisionService intelligence;
    private final ApiIdempotencyService idempotency;
    private final AuditService audit;
    private final AmapWeatherService amapWeather;
    @Value("${foodwise.data.demo-enabled:false}")
    private boolean demoEnabled;

    public ApiV1Controller(PredictionOrchestrator predictions, AnalyticsService analytics, FoodwiseService foodwise,
                           OperationFeedbackService feedback, IntelligentDecisionService intelligence,
                           ApiIdempotencyService idempotency, AuditService audit, AmapWeatherService amapWeather) {
        this.predictions = predictions;
        this.analytics = analytics;
        this.foodwise = foodwise;
        this.feedback = feedback;
        this.intelligence = intelligence;
        this.idempotency = idempotency;
        this.audit = audit;
        this.amapWeather = amapWeather;
    }

    @PostMapping("/predictions")
    public ApiResponse<PredictionEngineResult> predict(@Valid @RequestBody PredictionRequest request,
                                                        HttpServletRequest httpRequest) {
        idempotency.reserve(httpRequest, "predictions.create");
        String idempotencyKey = ApiIdempotency.require(httpRequest);
        PredictionEngineResult result = predictions.predict(
                new PredictionContext(request.dishId(), request.weather(), request.examWeek(), request.campusEvent(),
                        ApiTrace.id(httpRequest), idempotencyKey, operatorName()),
                request.engine());
        audit.record(httpRequest, "predictions.create", "prediction", String.valueOf(request.dishId()));
        return ApiResponse.success(result, ApiTrace.id(httpRequest));
    }

    private String operatorName() {
        var authentication = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        return authentication == null ? "anonymous" : authentication.getName();
    }

    @GetMapping("/session")
    public ApiResponse<Map<String, Object>> session(HttpServletRequest request) {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        String role = authentication == null ? "ADMIN" : authentication.getAuthorities().stream()
                .map(authority -> authority.getAuthority().replace("ROLE_", ""))
                .filter(value -> value.equals("ADMIN") || value.equals("OPERATOR") || value.equals("ANALYST"))
                .findFirst().orElse(demoEnabled ? "ADMIN" : "ANALYST");
        return ApiResponse.success(Map.of("name", operatorName(), "role", role,
                "demo", demoEnabled), ApiTrace.id(request));
    }

    @GetMapping("/predictions/engines")
    public ApiResponse<?> engines(HttpServletRequest request) {
        return ApiResponse.success(predictions.availableEngines(), ApiTrace.id(request));
    }

    @GetMapping("/weather")
    public ApiResponse<Map<String, Object>> weather(@RequestParam @NotBlank String city,
                                                    HttpServletRequest request) {
        return ApiResponse.success(amapWeather.current(city), ApiTrace.id(request));
    }

    @GetMapping("/analytics/metadata")
    public ApiResponse<Map<String, Object>> metadata(HttpServletRequest request) {
        return ApiResponse.success(analytics.metadata(), ApiTrace.id(request));
    }

    @GetMapping("/analytics/backtest")
    public ApiResponse<Map<String, Object>> backtest(HttpServletRequest request) {
        return ApiResponse.success(analytics.backtest(), ApiTrace.id(request));
    }

    @GetMapping("/operations/dashboard")
    public ApiResponse<Map<String, Object>> dashboard(HttpServletRequest request) {
        return ApiResponse.success(foodwise.dashboard(), ApiTrace.id(request));
    }

    @GetMapping("/operations/summary")
    public ApiResponse<DashboardSummary> summary(HttpServletRequest request) {
        return ApiResponse.success(foodwise.getDashboardSummary(), ApiTrace.id(request));
    }

    @GetMapping("/operations/rows")
    public ApiResponse<PageResponse<OperationRow>> rows(@RequestParam(defaultValue = "1") @Min(1) int page,
                                                        @RequestParam(defaultValue = "20") @Min(1) int size,
                                                        HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.getOperationRows(), page, size), ApiTrace.id(request));
    }

    @GetMapping("/stalls")
    public ApiResponse<PageResponse<StallInfo>> stalls(@RequestParam(defaultValue = "1") @Min(1) int page,
                                                       @RequestParam(defaultValue = "20") @Min(1) int size,
                                                       HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.getStalls(), page, size), ApiTrace.id(request));
    }

    @GetMapping("/dishes")
    public ApiResponse<PageResponse<DishInfo>> dishes(@RequestParam(defaultValue = "1") @Min(1) int page,
                                                      @RequestParam(defaultValue = "50") @Min(1) int size,
                                                      HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.getDishes(), page, size), ApiTrace.id(request));
    }

    @GetMapping("/operations/trend")
    public ApiResponse<java.util.List<TrendPoint>> trend(HttpServletRequest request) {
        return ApiResponse.success(foodwise.getTrend(), ApiTrace.id(request));
    }

    @GetMapping("/reports/summary")
    public ApiResponse<ReportSummary> reportSummary(HttpServletRequest request) {
        return ApiResponse.success(foodwise.getReportSummary(), ApiTrace.id(request));
    }

    @GetMapping("/reports")
    public ApiResponse<Map<String, Object>> report(HttpServletRequest request) {
        return ApiResponse.success(foodwise.report(), ApiTrace.id(request));
    }

    @GetMapping("/offers")
    public ApiResponse<?> offers(@RequestParam(defaultValue = "1") @Min(1) int page,
                                 @RequestParam(defaultValue = "20") @Min(1) int size,
                                 HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.offers(), page, size), ApiTrace.id(request));
    }

    @PostMapping("/intelligence/offers/recommend")
    public ApiResponse<OfferRecommendation> recommendOffer(@Valid @RequestBody OfferRequest request,
                                                            HttpServletRequest httpRequest) {
        return ApiResponse.success(intelligence.recommendOffer(request.dishId()), ApiTrace.id(httpRequest));
    }

    @PostMapping("/offers")
    public ApiResponse<Map<String, Object>> createOffer(@Valid @RequestBody OfferCreateRequest request,
                                                        HttpServletRequest httpRequest) {
        idempotency.reserve(httpRequest, "offers.create");
        long id = foodwise.createOffer(request.dishId(), request.quantity(), request.offerPrice(),
                request.startTime(), request.endTime(), request.safetyConfirmed());
        audit.record(httpRequest, "offers.create", "offer", String.valueOf(id));
        return ApiResponse.success(Map.of("id", id, "message", "优惠活动已发布"), ApiTrace.id(httpRequest));
    }

    @GetMapping("/orders")
    public ApiResponse<?> orders(@RequestParam(defaultValue = "1") @Min(1) int page,
                                 @RequestParam(defaultValue = "20") @Min(1) int size,
                                 HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.orders(), page, size), ApiTrace.id(request));
    }

    @GetMapping("/orders/lookup")
    public ApiResponse<Map<String, Object>> lookupOrder(@RequestParam String pickupCode,
                                                         HttpServletRequest request) {
        return ApiResponse.success(foodwise.orderByPickupCode(pickupCode), ApiTrace.id(request));
    }

    @PostMapping("/orders/{id}/verify")
    public ApiResponse<Map<String, Object>> verify(@PathVariable @Min(1) long id, HttpServletRequest request) {
        idempotency.reserve(request, "orders.verify");
        foodwise.verify(id);
        audit.record(request, "orders.verify", "order", String.valueOf(id));
        return ApiResponse.success(Map.of("message", "核销成功"), ApiTrace.id(request));
    }

    @GetMapping("/alerts")
    public ApiResponse<?> alerts(@RequestParam(defaultValue = "1") @Min(1) int page,
                                 @RequestParam(defaultValue = "20") @Min(1) int size,
                                 HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(foodwise.alerts(), page, size), ApiTrace.id(request));
    }

    @PostMapping("/alerts/{id}/resolve")
    public ApiResponse<Map<String, Object>> resolveAlert(@PathVariable @Min(1) long id, HttpServletRequest request) {
        idempotency.reserve(request, "alerts.resolve");
        foodwise.resolveAlert(id);
        audit.record(request, "alerts.resolve", "alert", String.valueOf(id));
        return ApiResponse.success(Map.of("message", "预警已处理"), ApiTrace.id(request));
    }

    @GetMapping("/operations/learning-status")
    public ApiResponse<?> learningStatus(HttpServletRequest request) {
        return ApiResponse.success(feedback.learningStatus(), ApiTrace.id(request));
    }

    @GetMapping("/operations/feedback")
    public ApiResponse<?> recentFeedback(@RequestParam(defaultValue = "1") @Min(1) int page,
                                         @RequestParam(defaultValue = "20") @Min(1) int size,
                                         HttpServletRequest request) {
        return ApiResponse.success(PageResponse.of(feedback.recentFeedback(), page, size), ApiTrace.id(request));
    }

    @PostMapping("/operations/feedback")
    public ApiResponse<OperationLearningResult> operationFeedback(@Valid @RequestBody FeedbackRequest request,
                                                                   HttpServletRequest httpRequest) {
        idempotency.reserve(httpRequest, "operations.feedback");
        OperationLearningResult result = feedback.submit(request.businessDate(), request.mealPeriod(), request.dishId(), request.plannedQty(),
                request.preparedQty(), request.soldQty(), request.discountSoldQty(), request.leftoverQty(),
                request.revenue(), request.weather(), request.eventTag(), request.recommendationAdopted(),
                request.safetyConfirmed(), request.operatorName(), request.note());
        audit.record(httpRequest, "operations.feedback", "operation", String.valueOf(result.operationId()));
        return ApiResponse.success(result, ApiTrace.id(httpRequest));
    }

    public record PredictionRequest(@Min(1) long dishId, @NotBlank String weather,
                                    boolean examWeek, boolean campusEvent,
                                    String engine) {
        public PredictionRequest {
            engine = engine == null || engine.isBlank() ? "rule" : engine;
        }
    }

    public record OfferRequest(@Min(1) long dishId) {}

    public record OfferCreateRequest(@Min(1) long dishId, @Min(1) int quantity,
                                     @NotNull @DecimalMin("0.01") BigDecimal offerPrice,
                                     @NotNull LocalTime startTime, @NotNull LocalTime endTime,
                                     boolean safetyConfirmed) {}

    public record FeedbackRequest(@NotNull LocalDate businessDate, String mealPeriod, @Min(1) long dishId,
                                  @Min(0) int plannedQty, @Min(0) int preparedQty,
                                  @Min(0) int soldQty, @Min(0) int discountSoldQty,
                                  @Min(0) int leftoverQty, @NotNull @DecimalMin("0.00") BigDecimal revenue,
                                  @NotBlank String weather, String eventTag, boolean recommendationAdopted,
                                   boolean safetyConfirmed, @NotBlank String operatorName, String note) {
        public FeedbackRequest {
            mealPeriod = mealPeriod == null || mealPeriod.isBlank() ? "未标注" : mealPeriod;
        }
    }
}

