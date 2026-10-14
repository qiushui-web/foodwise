package org.foodwise;

import org.foodwise.service.LgbmCampusModel;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.*;

class CampusInferenceParityTests {
    private byte[] resource(String path) throws Exception {
        try (var stream = getClass().getResourceAsStream(path)) {
            assertNotNull(stream, "Missing frozen Python fixture: " + path);
            return stream.readAllBytes();
        }
    }

    @Test
    void javaMatchesNativeLightgbmOnFrozenFiniteVectors() throws Exception {
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(resource("/modeling/lgbm_campus_model.txt")));
        assertEquals(new String(resource("/modeling/campus_native_model.sha256"), StandardCharsets.US_ASCII).trim(), hash,
                "Model changed: independently regenerate/review native reference predictions");
        var model = new LgbmCampusModel();
        model.init();
        assertTrue(model.isReady());
        String[] lines = new String(resource("/modeling/campus_native_predictions.csv"), StandardCharsets.UTF_8).split("\\R");
        assertEquals(26, lines[0].split(",").length);
        assertEquals(35, lines.length); // 32 chronological samples + zero/high probes + header
        for (int row = 1; row < lines.length; row++) {
            String[] columns = lines[row].split(",");
            double[] values = new double[24];
            for (int j = 0; j < values.length; j++) values[j] = Double.parseDouble(columns[j]);
            assertEquals(Double.parseDouble(columns[24]), model.explain(values).getRawScore(), 1e-8, "raw row " + row);
            assertEquals(Double.parseDouble(columns[25]), model.predict(values), 1e-8, "transformed row " + row);
        }
    }
}
