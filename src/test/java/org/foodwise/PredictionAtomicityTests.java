package org.foodwise;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.PredictionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@SpringBootTest(properties="spring.datasource.url=jdbc:h2:mem:prediction-atomicity;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
@DirtiesContext(classMode=DirtiesContext.ClassMode.AFTER_CLASS)
class PredictionAtomicityTests {
    @MockitoSpyBean FoodwiseRepository repository;
    @Autowired PredictionService predictions;
    @Autowired JdbcTemplate jdbc;

    @Test void snapshotFailureRollsBackPredictionAndAdviceTogether() {
        int before=jdbc.queryForObject("SELECT COUNT(*) FROM prediction_record",Integer.class);
        int adviceBefore=jdbc.queryForObject("SELECT COUNT(*) FROM ai_advice_record",Integer.class);
        doThrow(new IllegalStateException("snapshot test failure")).when(repository)
                .savePredictionSnapshot(anyLong(),anyString(),any(),any());
        assertThrows(IllegalStateException.class,()->predictions.predict(new PredictionContext(1,"晴",false,false)));
        assertEquals(before,jdbc.queryForObject("SELECT COUNT(*) FROM prediction_record",Integer.class));
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM prediction_input_snapshot",Integer.class));
        assertEquals(adviceBefore,jdbc.queryForObject("SELECT COUNT(*) FROM ai_advice_record",Integer.class));
    }
}
