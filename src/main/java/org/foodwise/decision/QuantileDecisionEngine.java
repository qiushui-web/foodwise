package org.foodwise.decision;

import jakarta.annotation.PostConstruct;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.IntelligentDecisionService;
import org.foodwise.service.PredictionService;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 未校准对照引擎：同样的分位模型与成本规则，但**不套 CQR 偏移与位置校正**。
 *
 * 存在的意义是把“校准到底值多少”变成界面上可切换的对照，
 * 而不是只在论文里给一张表。它的区间更窄、建议量更少，覆盖率也没有保证。
 */
@Service
public class QuantileDecisionEngine extends CalibratedDecisionEngine {

    public static final String KEY = "quantile";

    /** 未校准引擎没有 90% 覆盖率，界面上必须显示实测值而不是清单里的校准指标。 */
    private double measuredCoverage;

    public QuantileDecisionEngine(FoodwiseRepository repository,
                                  IntelligentDecisionService adviceService,
                                  PredictionService ruleEngine,
                                  DecisionRecorder recorder) {
        super(repository, adviceService, ruleEngine, recorder);
    }

    @PostConstruct
    void loadMeasuredCoverage() {
        try (InputStream input = new ClassPathResource("modeling/interval_backtest_metrics.json").getInputStream()) {
            Map<?, ?> metrics = new ObjectMapper()
                    .readValue(new String(input.readAllBytes(), StandardCharsets.UTF_8), Map.class);
            Map<?, ?> methods = (Map<?, ?>) metrics.get("methods");
            Map<?, ?> raw = (Map<?, ?>) methods.get("quantile_raw");
            if (raw != null && raw.get("picp") instanceof Number picp) measuredCoverage = picp.doubleValue();
        } catch (Exception ignored) {
            measuredCoverage = 0.0;
        }
    }

    @Override
    public String key() {
        return KEY;
    }

    @Override
    protected boolean applyCalibration() {
        return false;
    }

    @Override
    protected String intervalMethod() {
        return "quantile-raw";
    }

    @Override
    protected boolean calibrated() {
        return false;
    }

    @Override
    protected String confidenceKind() {
        return "uncalibrated_interval";
    }

    @Override
    public DecisionPreview preview(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                   LocalDate targetDate) {
        DecisionPreview base = super.preview(dishId, weather, examWeek, campusEvent, targetDate);
        // 父类已经写过一句“未校准对照”，这里替换成带实测覆盖率的那一句，避免三条同义提示堆叠。
        List<String> notes = new ArrayList<>();
        for (String note : base.notes()) {
            if (!note.startsWith("未校准对照")) notes.add(note);
        }
        if ("ready".equals(base.status())) {
            notes.add("未校准对照：不套用 CQR 偏移与位置校正，测试集实测覆盖率 "
                    + Math.round(measuredCoverage * 100) + "%，不应按 90% 区间理解。");
        }
        return new DecisionPreview(KEY, base.modelVersion(), base.status(), base.unavailableReason(),
                base.targetDate(), base.dayOfWeek(), base.categoryId(), base.q05(), base.q95(),
                base.offset(), base.intervalLow(), base.intervalHigh(), base.center(), base.sigma(),
                base.criticalRatio(), base.underage(), base.overage(), base.quantity(),
                base.firstBatch(), base.replenish(), base.price(), base.unitCost(),
                base.lossRate(), base.effectiveUnitCost(), base.regretUpper(), measuredCoverage,
                "quantile-raw", notes);
    }
}