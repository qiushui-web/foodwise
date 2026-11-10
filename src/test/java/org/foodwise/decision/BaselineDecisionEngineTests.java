package org.foodwise.decision;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.SalesObservation;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 基线引擎是 v3 的部署链路，它必须满足三条：能算、能重放、算不出来时明说。
 */
@SpringBootTest
class BaselineDecisionEngineTests {

    @Autowired
    BaselineDecisionEngine engine;

    private static final LocalDate DATE = LocalDate.of(2026, 7, 21);

    @Test
    void previewIsReadyAndInternallyConsistent() {
        DecisionPreview preview = engine.preview(1L, DATE);
        assertEquals("ready", preview.status(), preview.notes().toString());
        assertEquals(BaselineDecisionEngine.KEY, preview.engine());
        assertTrue(preview.intervalLow() <= preview.center());
        assertTrue(preview.center() <= preview.intervalHigh());
        assertEquals(0.0, preview.offset(), 1e-9);
        assertTrue(preview.sigma() > 0);
    }

    @Test
    void quantityFollowsTheNewsvendorSolution() {
        DecisionPreview preview = engine.preview(1L, DATE);
        double raw = preview.center() + NormalQuantile.invCdf(preview.criticalRatio()) * preview.sigma();
        int expected = (int) (Math.ceil(Math.max(raw, 0) / 5.0) * 5.0);
        expected = Math.min(expected, 250);
        assertEquals(expected, preview.quantity(),
                "建议量必须是 center + z(rho)*sigma 按最小批量取整");
        // 临界比 0.886 > 0.5，建议量应不低于中心
        assertTrue(preview.quantity() >= preview.center());
    }

    @Test
    void unknownDishIsReportedInsteadOfCrashing() {
        DecisionPreview preview = engine.preview(999_999L, DATE);
        assertEquals("insufficient_history", preview.status());
        assertNotNull(preview.unavailableReason());
        assertTrue(preview.unavailableReason().startsWith("DISH_NOT_FOUND"));
        assertEquals(0, preview.quantity());
    }

    @Test
    void predictThenReplayMatches() {
        PredictionContext context = new PredictionContext(1L, "晴朗", false, false, "trace-baseline",
                "idem-baseline-" + System.nanoTime(), "tester", DATE, "全日", "本地构造验收");
        PredictionEngineResult result = engine.predict(context);
        long recordId = result.prediction().predictionId();
        CalibratedDecisionEngine.ReplayReport report = engine.replay(recordId);
        assertTrue(report.match(), "同一台账、同一日期，基线重放必须给出同一个建议量：" + report.notes());
        assertEquals(report.recordedQuantity(), report.replayedQuantity());
    }

    @Test
    void sameWeekdayMedianIgnoresOtherWeekdays() {
        List<SalesObservation> history = List.of(
                new SalesObservation(LocalDate.of(2026, 7, 7), 90, 100),   // 周二
                new SalesObservation(LocalDate.of(2026, 7, 8), 10, 100),   // 周三
                new SalesObservation(LocalDate.of(2026, 7, 14), 100, 110), // 周二
                new SalesObservation(LocalDate.of(2026, 7, 15), 20, 100)); // 周三
        assertEquals(95.0, BaselineDecisionEngine.sameWeekdayMedian(history, 2), 1e-9);
        assertEquals(15.0, BaselineDecisionEngine.sameWeekdayMedian(history, 3), 1e-9);
    }

    @Test
    void residualsArePositiveAndNegative() {
        List<SalesObservation> history = List.of(
                new SalesObservation(LocalDate.of(2026, 7, 7), 80, 100),
                new SalesObservation(LocalDate.of(2026, 7, 14), 90, 100),
                new SalesObservation(LocalDate.of(2026, 7, 21), 70, 100));
        double[] residuals = BaselineDecisionEngine.leaveOneOutResiduals(history);
        assertEquals(2, residuals.length, "第一个点没有历史，不该产生残差");
        assertTrue(residuals[0] > 0);
        assertTrue(residuals[1] < 0);
    }

    @Test
    void quantileInterpolates() {
        assertEquals(3.0, BaselineDecisionEngine.quantile(new double[]{1, 3, 5}, 0.5), 1e-9);
        assertEquals(1.0, BaselineDecisionEngine.quantile(new double[]{1, 3, 5}, 0.0), 1e-9);
        assertEquals(5.0, BaselineDecisionEngine.quantile(new double[]{1, 3, 5}, 1.0), 1e-9);
    }
}