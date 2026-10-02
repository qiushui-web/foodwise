package org.foodwise.service;

import jakarta.servlet.http.HttpServletRequest;
import org.foodwise.api.ApiTrace;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

@Service
public class AuditService {
    private final JdbcTemplate jdbcTemplate;

    public AuditService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void record(HttpServletRequest request, String operation, String resourceType, String resourceId) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        String operator = authentication == null ? "anonymous" : authentication.getName();
        String role = authentication == null ? "ANONYMOUS" : authentication.getAuthorities().stream()
                .map(a -> a.getAuthority().replaceFirst("^ROLE_", ""))
                .findFirst().orElse("UNKNOWN");
        jdbcTemplate.update("""
                INSERT INTO audit_log(trace_id, operator_name, operator_role, operation, resource_type,
                    resource_id, request_method, request_path, result, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS', NULL)
                """, ApiTrace.id(request), operator, role, operation, resourceType, resourceId,
                request.getMethod(), request.getRequestURI());
    }
}

