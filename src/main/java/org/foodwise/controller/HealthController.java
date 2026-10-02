package org.foodwise.controller;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;

@RestController
public class HealthController {
    private final JdbcTemplate jdbcTemplate;

    public HealthController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        try {
            Integer one = jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            return Map.of("status", one != null && one == 1 ? "UP" : "DOWN",
                    "database", "UP", "timestamp", Instant.now());
        } catch (RuntimeException exception) {
            return Map.of("status", "DOWN", "database", "DOWN", "timestamp", Instant.now());
        }
    }
}

