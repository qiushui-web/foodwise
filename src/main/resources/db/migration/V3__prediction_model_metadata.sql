CREATE TABLE IF NOT EXISTS model_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_key VARCHAR(80) NOT NULL,
    version VARCHAR(40) NOT NULL,
    engine_type VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    feature_schema TEXT NOT NULL,
    metrics_snapshot TEXT,
    artifact_path VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (model_key, version)
);

CREATE TABLE IF NOT EXISTS prediction_input_snapshot (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prediction_id BIGINT NOT NULL,
    model_version_id BIGINT,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_snapshot_prediction FOREIGN KEY (prediction_id) REFERENCES prediction_record(id),
    CONSTRAINT fk_snapshot_model FOREIGN KEY (model_version_id) REFERENCES model_version(id)
);
