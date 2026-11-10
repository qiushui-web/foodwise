package org.foodwise;

import org.foodwise.api.v1.DecisionController;
import org.foodwise.decision.CalibratedDecisionEngine;
import org.foodwise.decision.DecisionPreview;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.prediction.PredictionOrchestrator;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class CalibratedDecisionEngineTests {

    @Autowired
    @org.springframework.beans.factory.annotation.Qualifier("calibratedDecisionEngine")
    CalibratedDecisionEngine engine;
    @Autowired
    org.foodwise.decision.QuantileDecisionEngine contrastEngine;
    @Autowired
    PredictionOrchestrator orchestrator;

    @Test
    void engineLoadsCalibratedArtifactsAndReportsCalibratedInterval() {
        assertTrue(engine.isReady(), "校准引擎应通过哈希校验：" + engine.unavailableReason());
        assertTrue(orchestrator.availableEngines().contains("calibrated-quantile"));
        assertTrue(orchestrator.availableEngines().contains("quantile"));
        assertTrue(orchestrator.availableEngines().contains("rule"));
        assertEquals("2026.10.27-interval-v1", engine.modelVersion());
    }

    @Test
    void previewReturnsCostAwareDecisionInsideReasonableBounds() {
        DecisionPreview preview = engine.preview(1L, "晴朗", false, false, LocalDate.now().plusDays(1));
        assertEquals("ready", preview.status());
        assertEquals("cqr+stratified-aci", preview.calibrationMethod());
        assertTrue(preview.intervalLow() < preview.intervalHigh());
        assertTrue(preview.quantity() > 0);
        assertTrue(preview.criticalRatio() > 0 && preview.criticalRatio() < 1);
        assertTrue(preview.quantity() <= 250, "建议量必须落在产能上限内");
        assertEquals(0, preview.quantity() % 5, "建议量必须对齐最小批量");
        assertTrue(preview.coverage() > 0.9 && preview.coverage() <= 1.0);
        assertFalse(preview.notes().isEmpty());
    }

    @Test
    @Transactional
    void decisionIsPersistedAndReplayReproducesTheSameQuantity() {
        PredictionContext context = new PredictionContext(1L, "晴朗", false, false, "test-trace",
                "test-idem-" + System.nanoTime(), "tester", LocalDate.now().plusDays(1), "全日", "本地构造验收");
        PredictionEngineResult result = engine.predict(context);
        long recordId = result.prediction().predictionId();
        assertTrue(recordId > 0, "决策应写入 decision_record 并返回 id");
        assertEquals("cqr-stratified-aci", result.prediction().intervalMethod());
        assertTrue(result.prediction().intervalCalibrated());

        CalibratedDecisionEngine.ReplayReport replay = engine.replay(recordId);
        assertTrue(replay.match(), "同一份输入重放应得到同一建议量");
        assertEquals(replay.recordedQuantity(), replay.replayedQuantity());
        assertFalse(replay.drift(), "模型与校准产物未变化时不应报告漂移");
    }

    @Test
    void requestPayloadIsNormalisedWhenWeatherIsBlank() {
        DecisionController.DecisionRequest request = new DecisionController.DecisionRequest(
                1L, " ", false, false, null, null);
        assertEquals("晴朗", request.weather());
        assertEquals("robust-baseline", request.engine(), "v3 起默认引擎改为稳健基线");
    }

    @Test
    void uncalibratedContrastEngineKeepsRawInterval() {
        DecisionPreview calibrated = engine.preview(1L, "晴朗", false, false, LocalDate.now().plusDays(1));
        DecisionPreview contrast = contrastEngine.preview(1L, "晴朗", false, false, LocalDate.now().plusDays(1));
        assertEquals("quantile-raw", contrast.calibrationMethod());
        assertTrue(contrast.intervalHigh() - contrast.intervalLow()
                        <= calibrated.intervalHigh() - calibrated.intervalLow(),
                "未校准区间不应比校准区间更宽");
        assertEquals(0.0, contrast.offset(), 1e-9);
        assertTrue(contrast.coverage() < 0.7,
                "未校准引擎必须报实测覆盖率，不能沿用清单里的 90% 校准指标");
    }
}