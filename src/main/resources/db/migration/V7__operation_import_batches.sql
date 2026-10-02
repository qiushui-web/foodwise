CREATE TABLE IF NOT EXISTS operation_import_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    operator_name VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_rows INT NOT NULL DEFAULT 0,
    imported_rows INT NOT NULL DEFAULT 0,
    rejected_rows INT NOT NULL DEFAULT 0,
    duplicate_rows INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS operation_import_row (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_id BIGINT NOT NULL,
    row_no INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    business_date DATE NULL,
    dish_id BIGINT NULL,
    source_key VARCHAR(160) NULL,
    error_message VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_operation_import_row_batch FOREIGN KEY (batch_id) REFERENCES operation_import_batch(id),
    INDEX idx_operation_import_row_batch (batch_id),
    INDEX idx_operation_import_row_source (source_key)
);
