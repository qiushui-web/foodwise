package org.foodwise.controller;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
public class HealthController {

    private static final ZoneId SITE_ZONE = ZoneId.of("Asia/Shanghai");

    private final JdbcTemplate jdbcTemplate;

    public HealthController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        String status;
        String database;
        try {
            Integer one = jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            database = one != null && one == 1 ? "UP" : "DOWN";
            status = "UP".equals(database) ? "UP" : "DOWN";
        } catch (RuntimeException exception) {
            database = "DOWN";
            status = "DOWN";
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", status);
        payload.put("database", database);
        // 站点时间：带 +08:00 偏移，避免运维看到 UTC 误判为异常。
        payload.put("timestamp", OffsetDateTime.now(SITE_ZONE));
        payload.put("timezone", SITE_ZONE.getId());
        return payload;
    }
}