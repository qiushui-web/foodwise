package org.foodwise;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.service.OperationImportService;
import org.foodwise.service.PredictionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = "spring.datasource.url=jdbc:h2:mem:source-evidence;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class OperationSourceEvidenceTests {
    @Autowired OperationImportService importer;
    @Autowired PredictionService predictions;
    @Autowired JdbcTemplate jdbcTemplate;
    @org.springframework.boot.test.web.server.LocalServerPort int port;

    @Test void sourceRegisterCanBeReadOverHttpWithoutPromotingVerification() throws Exception {
        var repository = new org.foodwise.repository.FoodwiseRepository(jdbcTemplate);
        long id = repository.createSourceEvidence("a".repeat(64), "register-test.csv", "构造测试来源",
                "测试提供方", "测试范围", "待核验", "test");
        var response = java.net.http.HttpClient.newHttpClient().send(
                java.net.http.HttpRequest.newBuilder(java.net.URI.create(
                        "http://127.0.0.1:" + port + "/api/v1/operations/source-evidence")).GET().build(),
                java.net.http.HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        var records = new tools.jackson.databind.ObjectMapper().readTree(response.body()).path("data");
        boolean found = false;
        for (var row : records) if (row.path("source_evidence_id").asLong() == id) {
            assertEquals("a".repeat(64), row.path("source_sha256").asText());
            assertEquals("DECLARED_UNVERIFIED", row.path("verification_status").asText());
            found = true;
        }
        assertTrue(found);
    }

    @Test void importedRevisionsAndPredictionReplayKeepTheSameUnverifiedSourceEvidence() {
        var firstDate = LocalDate.of(2026, 10, 12);
        var secondDate = LocalDate.of(2026, 10, 13);
        String csv = "business_date,meal_period,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather\n"
                + firstDate + ",午餐,1,10,10,8,1,2,80,晴\n"
                + secondDate + ",午餐,1,12,12,9,0,3,90,晴\n";
        var file = new MockMultipartFile("file", "authorized-ledger.csv", "text/csv", csv.getBytes(StandardCharsets.UTF_8));

        var imported = importer.importCsv(file, "operator", true, "档口日结台账", "试点档口", "河北省（声明）",
                "授权编号待核验：AUTH-REF-01");
        assertEquals(2, imported.get("imported"));
        assertEquals("d24c7326e6a4892a8234dd3cbeeb402504205989c199cec226be782e64c002d2", imported.get("sourceSha256"));
        assertEquals("DECLARED_UNVERIFIED", imported.get("sourceVerificationStatus"));

        var prediction = predictions.predict(new PredictionContext(1, "晴", false, false,
                "source-test", null, "test", LocalDate.now(), "午餐", "台账来源待核验"));
        var replay = predictions.replayPredictionInputs(prediction.prediction().predictionId());
        assertTrue((Boolean) replay.get("dataVerified"));
        @SuppressWarnings("unchecked")
        var evidence = (List<java.util.Map<String, Object>>) replay.get("sourceEvidence");
        assertEquals(2, evidence.size());
        assertTrue(evidence.stream().allMatch(row -> "SOURCE_DECLARED_UNVERIFIED".equals(row.get("verificationStatus"))));
        assertEquals(List.of(2, 3), evidence.stream().map(row -> ((Number) row.get("sourceRowNo")).intValue()).sorted().toList());
        assertTrue(evidence.stream().allMatch(row -> imported.get("sourceEvidenceId").equals(row.get("sourceEvidenceId"))));
    }

    @Test void importedSourceDeclarationMustBeCompleteBeforeAnyBatchIsAccepted() {
        var file = new MockMultipartFile("file", "ledger.csv", "text/csv", "business_date,dish_id\n".getBytes(StandardCharsets.UTF_8));
        assertThrows(IllegalArgumentException.class, () -> importer.importCsv(file, "operator", true, "", "provider", "河北", "AUTH-1"));
    }

    @Test
    @org.springframework.transaction.annotation.Transactional
    void replayRejectsSourceEvidenceTampering() {
        var file = new MockMultipartFile("file", "tamper-ledger.csv", "text/csv",
                ("business_date,meal_period,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather\n"
                        + "2026-10-14,午餐,1,10,10,8,0,2,80,晴\n").getBytes(StandardCharsets.UTF_8));
        var imported = importer.importCsv(file, "operator", true, "档口日结台账", "试点档口", "河北省（声明）",
                "授权编号待核验：AUTH-TAMPER");
        var prediction = predictions.predict(new PredictionContext(1, "晴", false, false,
                "source-tamper", null, "test", LocalDate.now(), "午餐", "台账来源待核验"));

        jdbcTemplate.update("UPDATE source_evidence SET provider=? WHERE id=?", "被篡改的提供方",
                imported.get("sourceEvidenceId"));

        var error = assertThrows(IllegalArgumentException.class,
                () -> predictions.replayPredictionInputs(prediction.prediction().predictionId()));
        assertTrue(error.getMessage().contains("来源证据"));
    }
}
