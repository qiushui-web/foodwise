package org.foodwise;

import org.foodwise.api.v1.DecisionController;
import org.foodwise.decision.CalibratedDecisionEngine;
import org.foodwise.decision.ModelEvidenceService;
import org.foodwise.decision.QuantileDecisionEngine;
import org.foodwise.prediction.PredictionContext;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 冒烟测试发现过的真实缺陷：重放必须按记录自身的引擎分派，
 * 否则会把对照引擎的建议量当成“漂移”。这里直接走 controller 的分派逻辑。
 */
@SpringBootTest
class DecisionEndpointTests {

    @Autowired
    DecisionController controller;
    @Autowired
    QuantileDecisionEngine contrastEngine;
    @Autowired
    ModelEvidenceService evidenceService;

    @Test
    void evidenceServiceServesRealExperimentArtifacts() {
        assertFalse(evidenceService.manifest().isEmpty(), "清单必须能从类路径读到");
        Map<String, Object> interval = evidenceService.intervalExperiment();
        Map<String, Object> methods = asMap(interval.get("methods"));
        assertEquals(7, methods.size(), "七种区间方法都应出现在证据页");
        assertTrue(methods.containsKey("cqr_stratified"));
        Map<String, Object> decision = evidenceService.decisionExperiment();
        assertFalse(asMap(decision.get("base_scenario")).isEmpty());
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    @Test
    void unsupportedEngineIsRejectedInsteadOfSilentlyFallingBack() {
        // 用户选择"规则引擎"时曾经拿到校准数字，属于静默错误；现在必须明确报错。
        IllegalArgumentException error = org.junit.jupiter.api.Assertions.assertThrows(
                IllegalArgumentException.class,
                () -> controller.preview(1L, "晴朗", false, false, LocalDate.now().plusDays(1), "rule",
                        null, null, null, null, null, null, new MockHttpServletRequest()));
        assertTrue(error.getMessage().startsWith("UNSUPPORTED_ENGINE:"), error.getMessage());
    }

    @Test
    @Transactional
    void replayRouteDispatchesToTheEngineThatCreatedTheRecord() {
        PredictionContext context = new PredictionContext(1L, "晴朗", false, false, "test-trace",
                "test-idem-" + System.nanoTime(), "tester", LocalDate.now().plusDays(1), "全日", "本地构造验收");
        long recordId = contrastEngine.predict(context).prediction().predictionId();

        CalibratedDecisionEngine.ReplayReport report =
                controller.replay(recordId, new MockHttpServletRequest()).data();
        assertTrue(report.match(), "对照引擎的记录应能被对照引擎重放一致");
        assertEquals(report.recordedQuantity(), report.replayedQuantity());
        assertEquals("quantile", contrastEngine.key());
    }
}