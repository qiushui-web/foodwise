CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(80) NOT NULL,
    operator_name VARCHAR(120) NOT NULL,
    operator_role VARCHAR(40) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    resource_id VARCHAR(80),
    request_method VARCHAR(12) NOT NULL,
    request_path VARCHAR(255) NOT NULL,
    result VARCHAR(20) NOT NULL,
    error_code VARCHAR(80),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
