package org.foodwise.service;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiIdempotency;
import org.foodwise.api.ApiIdempotencyException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class ApiIdempotencyService {
    private final JdbcTemplate jdbcTemplate;

    public ApiIdempotencyService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void reserve(HttpServletRequest request, String operation) {
        String key = ApiIdempotency.require(request);
        try {
            jdbcTemplate.update("INSERT INTO api_idempotency_key (idempotency_key, operation) VALUES (?, ?)", key, operation);
        } catch (DuplicateKeyException exception) {
            throw new ApiIdempotencyException("该写请求已经提交，请勿重复操作");
        }
    }
}

