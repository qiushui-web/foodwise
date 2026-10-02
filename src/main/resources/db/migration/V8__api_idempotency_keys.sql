CREATE TABLE IF NOT EXISTS api_idempotency_key (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    idempotency_key VARCHAR(120) NOT NULL,
    operation VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_api_idempotency_key UNIQUE (idempotency_key)
);
