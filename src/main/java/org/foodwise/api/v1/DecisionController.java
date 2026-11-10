package org.foodwise.api.v1;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.foodwise.api.ApiIdempotency;
import org.foodwise.api.ApiResponse;
import org.foodwise.api.ApiTrace;
import org.foodwise.decision.BaselineDecisionEngine;
import org.foodwise.decision.CalibratedDecisionEngine;
import org.foodwise.decision.DecisionPreview;
import org.foodwise.decision.DecisionRecorder;
import org.foodwise.decision.QuantileDecisionEngine;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngine;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.service.ApiIdempotencyService;
import org.foodwise.service.AuditService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 校准决策接口：区间 → 成本 → 建议量，并留下可重放的决策记录。
 *
 * GET  /api/v1/decisions/preview   只读预览（不落库）
 * POST /api/v1/decisions           生成一次决策并留痕
 * GET  /api/v1/decisions/{id}      读取留痕
 * GET  /api/v1/decisions/{id}/replay 用当前产物重算并比对
 * GET  /api/v1/decisions/recent    最近决策列表（证据页用）
 */
@RestController
@RequestMapping("/api/v1/decisions")
public class DecisionController {

    private final CalibratedDecisionEngine engine;
    private final QuantileDecisionEngine quantileEngine;
    private final BaselineDecisionEngine baselineEngine;
    private final DecisionRecorder recorder;
    private final ApiIdempotencyService idempotency;
    private final AuditService audit;

    public DecisionController(@org.springframework.beans.factory.annotation.Qualifier("calibratedDecisionEngine") CalibratedDecisionEngine engine,
                              QuantileDecisionEngine quantileEngine,
                              BaselineDecisionEngine baselineEngine,
                              DecisionRecorder recorder, ApiIdempotencyService idempotency, AuditService audit,
                              org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.engine = engine;
        this.quantileEngine = quantileEngine;
        this.baselineEngine = baselineEngine;
        this.recorder = recorder;
        this.idempotency = idempotency;
        this.audit = audit;
        this.jdbc = jdbc;
    }

    private PredictionEngine select(String engineKey) {
        if (engineKey == null || engineKey.isBlank() || CalibratedDecisionEngine.KEY.equalsIgnoreCase(engineKey)) {
            return engine;
        }
        if (QuantileDecisionEngine.KEY.equalsIgnoreCase(engineKey)) return quantileEngine;
        if (BaselineDecisionEngine.KEY.equalsIgnoreCase(engineKey)) return baselineEngine;
        // 规则基线只在预测链路（/api/v1/predictions）提供，决策链路不接受它，
        // 否则用户以为在看规则结果，实际拿到的是校准数字。
        throw new IllegalArgumentException("UNSUPPORTED_ENGINE:" + engineKey
                + "（决策链路仅支持 " + CalibratedDecisionEngine.KEY + " / " + QuantileDecisionEngine.KEY
                + " / " + BaselineDecisionEngine.KEY + "）");
    }

    /** 基线引擎只吃菜品与日期，校准引擎还要天气与事件，这里统一成一种调用形态。 */
    private DecisionPreview previewFor(PredictionEngine selected, long dishId, String weather, boolean examWeek,
                                       boolean campusEvent, LocalDate date) {
        return previewFor(selected, dishId, weather, examWeek, campusEvent, date, null);
    }

    private DecisionPreview previewFor(PredictionEngine selected, long dishId, String weather, boolean examWeek,
                                       boolean campusEvent, LocalDate date, org.foodwise.decision.DecisionCostModel cost) {
        if (selected instanceof BaselineDecisionEngine baseline) return baseline.preview(dishId, date, cost);
        return ((CalibratedDecisionEngine) selected).preview(dishId, weather, examWeek, campusEvent, date, cost);
    }

    /**
     * 成本试算：只在预览里生效，不写进决策记录。
     * 落库的记录必须用菜品主数据里的成本参数，否则重放时对不上——"可调"不能变成"不可复现"。
     */
    private org.foodwise.decision.DecisionCostModel costOverride(Double price, Double unitCost, Double discountPrice,
                                                                 Double salvage, Double lambda, Double lossRate) {
        if (price == null && unitCost == null && discountPrice == null && salvage == null
                && lambda == null && lossRate == null) {
            return null;
        }
        if (price == null || unitCost == null) {
            throw new IllegalArgumentException("COST_OVERRIDE_NEEDS_PRICE_AND_UNIT_COST");
        }
        double discount = discountPrice != null ? discountPrice : price * org.foodwise.decision.DecisionCostModel.DEFAULT_DISCOUNT_RATIO;
        double salvageProbability = salvage != null ? salvage : org.foodwise.decision.DecisionCostModel.DEFAULT_SALVAGE_PROBABILITY;
        double shortageLambda = lambda != null ? lambda : org.foodwise.decision.DecisionCostModel.DEFAULT_SHORTAGE_LAMBDA;
        double loss = lossRate != null ? lossRate : org.foodwise.decision.DecisionCostModel.DEFAULT_LOSS_RATE;
        return new org.foodwise.decision.DecisionCostModel(price, unitCost, discount, salvageProbability,
                shortageLambda, loss);
    }

    private CalibratedDecisionEngine.ReplayReport replayFor(PredictionEngine selected, long id) {
        if (selected instanceof BaselineDecisionEngine baseline) return baseline.replay(id);
        return ((CalibratedDecisionEngine) selected).replay(id);
    }

    @GetMapping("/preview")
    public ApiResponse<DecisionPreview> preview(@RequestParam @Min(1) long dishId,
                                                @RequestParam(defaultValue = "晴朗") String weather,
                                                @RequestParam(defaultValue = "false") boolean examWeek,
                                                @RequestParam(defaultValue = "false") boolean campusEvent,
                                                @RequestParam(required = false)
                                                @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate targetDate,
                                                @RequestParam(defaultValue = "robust-baseline") String engine,
                                                @RequestParam(required = false) Double price,
                                                @RequestParam(required = false) Double unitCost,
                                                @RequestParam(required = false) Double discountPrice,
                                                @RequestParam(required = false) Double salvage,
                                                @RequestParam(required = false) Double lambda,
                                                @RequestParam(required = false) Double lossRate,
                                                HttpServletRequest httpRequest) {
        LocalDate date = targetDate == null ? LocalDate.now().plusDays(1) : targetDate;
        var cost = costOverride(price, unitCost, discountPrice, salvage, lambda, lossRate);
        return ApiResponse.success(previewFor(select(engine), dishId, weather, examWeek, campusEvent, date, cost),
                ApiTrace.id(httpRequest));
    }

    @org.springframework.transaction.annotation.Transactional
    @PostMapping
    public ApiResponse<Map<String, Object>> create(@Valid @RequestBody DecisionRequest request,
                                                   HttpServletRequest httpRequest) {
        idempotency.reserve(httpRequest, "decisions.create");
        String idempotencyKey = ApiIdempotency.require(httpRequest);
        LocalDate date = request.targetDate() == null ? LocalDate.now().plusDays(1) : request.targetDate();
        PredictionContext context = new PredictionContext(request.dishId(), request.weather(),
                request.examWeek(), request.campusEvent(), ApiTrace.id(httpRequest), idempotencyKey,
                operatorName(), date, "全日", "本地构造验收；输入来自当前台账与场景参数");
        PredictionEngineResult result = select(request.engine()).predict(context);
        long recordId = result.prediction().predictionId();
        audit.record(httpRequest, "decisions.create", "decision", String.valueOf(recordId));

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("recordId", recordId);
        payload.put("prediction", result.prediction());
        payload.put("preview", previewFor(select(request.engine()), request.dishId(), request.weather(),
                request.examWeek(), request.campusEvent(), date));
        return ApiResponse.success(payload, ApiTrace.id(httpRequest));
    }

    @org.springframework.transaction.annotation.Transactional
    @PostMapping("/{id}/feedback")
    public ApiResponse<?> feedback(@PathVariable @Min(1) long id, @Valid @RequestBody DecisionFeedbackRequest request,
                                   HttpServletRequest httpRequest) {
        idempotency.reserve(httpRequest, "decisions.feedback");
        var record = recorder.find(id).orElseThrow(() -> new IllegalArgumentException("备餐建议不存在或已失效"));
        var source = jdbc.queryForMap("SELECT dish_id,target_date,meal_period,quantity FROM decision_record WHERE id=?", id);
        if (((Number) source.get("dish_id")).longValue() != request.dishId()
                || !record.targetDate().equals(request.targetDate())
                || !String.valueOf(source.get("meal_period")).equals(request.mealPeriod()))
            throw new IllegalArgumentException("执行确认与原备餐建议的菜品、日期或餐次不一致");
        if (!List.of("早餐", "午餐", "晚餐").contains(request.mealPeriod()))
            throw new IllegalArgumentException("执行确认须选择早餐、午餐或晚餐");
        if (request.adjustedQty() > ((Number) source.get("quantity")).intValue()) {
            Integer cap = jdbc.queryForObject("SELECT MAX(planned_total) FROM decision_preparation_plan WHERE decision_record_id=?", Integer.class, id);
            if (cap == null || request.adjustedQty() > cap)
                throw new IllegalArgumentException("执行量超过已留档的现场备餐计划");
        }
        if ((!request.adopted() || request.adjustedQty() != record.quantity())
                && (request.reason() == null || request.reason().isBlank()))
            throw new IllegalArgumentException("调整或未采用建议时请填写原因");
        if (request.reason() != null && request.reason().length() > 300)
            throw new IllegalArgumentException("调整原因最多300字");
        var auth = SecurityContextHolder.getContext().getAuthentication();
        jdbc.update("INSERT INTO decision_feedback(decision_record_id,adopted,adjusted_qty,reason,operator_name) VALUES (?,?,?,?,?)",
                id, request.adopted(), request.adjustedQty(), request.reason(), auth == null ? "system" : auth.getName());
        audit.record(httpRequest, "decisions.feedback", "decision_record", String.valueOf(id));
        return ApiResponse.success(Map.of("message", "执行确认已保存"), ApiTrace.id(httpRequest));
    }

    @GetMapping("/recent")
    public ApiResponse<List<Map<String, Object>>> recent(@RequestParam(defaultValue = "20") int limit,
                                                         HttpServletRequest httpRequest) {
        return ApiResponse.success(recorder.recent(limit), ApiTrace.id(httpRequest));
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> record(@PathVariable @Min(1) long id,
                                                   HttpServletRequest httpRequest) {
        var record = recorder.find(id)
                .orElseThrow(() -> new IllegalArgumentException("DECISION_RECORD_NOT_FOUND:" + id));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", record.id());
        payload.put("dishId", record.dishId());
        payload.put("targetDate", record.targetDate());
        payload.put("engine", record.engine());
        payload.put("modelVersion", record.modelVersion());
        payload.put("calibrationSha256", record.calibrationSha256());
        payload.put("features", record.featureList());
        payload.put("q05", record.q05());
        payload.put("q95", record.q95());
        payload.put("intervalLow", record.intervalLow());
        payload.put("intervalHigh", record.intervalHigh());
        payload.put("criticalRatio", record.criticalRatio());
        payload.put("quantity", record.quantity());
        payload.put("firstBatch", record.firstBatch());
        payload.put("replenish", record.replenish());
        payload.put("createdAt", record.createdAt());
        return ApiResponse.success(payload, ApiTrace.id(httpRequest));
    }

    @GetMapping("/{id}/replay")
    public ApiResponse<CalibratedDecisionEngine.ReplayReport> replay(@PathVariable @Min(1) long id,
                                                                    HttpServletRequest httpRequest) {
        // 必须按记录自身的引擎重放：用错引擎会把 A 引擎的建议量当成漂移。
        var record = recorder.find(id)
                .orElseThrow(() -> new IllegalArgumentException("DECISION_RECORD_NOT_FOUND:" + id));
        return ApiResponse.success(replayFor(select(record.engine()), id), ApiTrace.id(httpRequest));
    }

    private String operatorName() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication == null ? "system" : authentication.getName();
    }

    public record DecisionRequest(@Min(1) long dishId,
                                  @NotBlank String weather,
                                  boolean examWeek,
                                  boolean campusEvent,
                                  @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate targetDate,
                                  String engine) {
        public DecisionRequest {
            if (weather == null || weather.isBlank()) weather = "晴朗";
            if (engine == null || engine.isBlank()) engine = BaselineDecisionEngine.KEY;
        }
    }

    public record DecisionFeedbackRequest(@Min(1) long dishId, @NotNull
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate targetDate,
            @NotBlank String mealPeriod, boolean adopted, @Min(0) int adjustedQty, String reason) {}

    private final org.springframework.jdbc.core.JdbcTemplate jdbc;
}
