package org.foodwise;

import org.foodwise.prediction.PredictionContext;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.service.PredictionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDate;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.datasource.url=jdbc:h2:mem:concurrent-ledger;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "foodwise.ai.enabled=false"})
class ConcurrentLedgerVisibilityTests {
    @org.springframework.test.context.DynamicPropertySource
    static void optionalIsolatedMysql(org.springframework.test.context.DynamicPropertyRegistry properties) {
        var url = System.getenv("FOODWISE_VALIDATION_MYSQL_URL");
        if (url == null || url.isBlank()) return;
        if (!url.startsWith("jdbc:mysql://127.0.0.1:33317/foodwise_validation_publication?"))
            throw new IllegalArgumentException("MySQL validation requires the isolated loopback database on port 33317");
        properties.add("spring.datasource.url", () -> url);
        properties.add("spring.datasource.driver-class-name", () -> "com.mysql.cj.jdbc.Driver");
        properties.add("spring.datasource.username", () -> "root");
        properties.add("spring.datasource.password", () -> "");
    }
    @Autowired FoodwiseRepository repository;
    @Autowired PredictionService predictions;
    @Autowired PlatformTransactionManager transactions;
    @LocalServerPort int port;

    @Test void uncommittedCorrectionCannotEnterTheReplayAfterItEventuallyCommits() throws Exception {
        var day = LocalDate.now().minusDays(1);
        repository.upsertOperation(day, "午餐", 1, 20, 20, 18, 0, 2,
                new BigDecimal("180"), "晴", "committed baseline", false);
        var written = new CountDownLatch(1);
        var release = new CountDownLatch(1);
        try (var pool = Executors.newSingleThreadExecutor()) {
            var writer = pool.submit(() -> new TransactionTemplate(transactions).execute(status -> {
                repository.upsertOperation(day, "午餐", 1, 200, 200, 180, 0, 20,
                        new BigDecimal("1800"), "晴", "uncommitted correction", false);
                written.countDown();
                try {
                    if (!release.await(20, TimeUnit.SECONDS)) throw new IllegalStateException("test release timed out");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt(); throw new IllegalStateException(e);
                }
                return null;
            }));
            try {
                assertTrue(written.await(10, TimeUnit.SECONDS));
                var original = predictions.predict(new PredictionContext(1, "晴", false, false,
                        "test", null, "test", LocalDate.now(), "午餐", "constructed concurrency test"));
                release.countDown();
                writer.get(10, TimeUnit.SECONDS);
                var response = HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create(
                        "http://127.0.0.1:" + port + "/api/v1/predictions/" + original.prediction().predictionId() + "/replay"))
                        .GET().build(), HttpResponse.BodyHandlers.ofString());
                assertEquals(200, response.statusCode(), response.body());
                var data = new tools.jackson.databind.ObjectMapper().readTree(response.body()).path("data");
                assertTrue(data.path("dataVerified").asBoolean());
                assertEquals(original.revisionIds().get(0).longValue(), data.path("revisionIds").get(0).asLong());
                assertEquals(18, data.path("observations").get(0).path("sold").asInt());
                var current = predictions.predict(new PredictionContext(1, "晴", false, false,
                        "test", null, "test", LocalDate.now(), "午餐", "constructed concurrency test"));
                assertTrue(current.prediction().predictedMid() > original.prediction().predictedMid());
            } finally {
                release.countDown();
                writer.get(10, TimeUnit.SECONDS);
            }
        }
    }
}
