CREATE TABLE IF NOT EXISTS model_backtest_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_version_id BIGINT NOT NULL,
    dataset_label VARCHAR(160) NOT NULL,
    split_method VARCHAR(160) NOT NULL,
    sample_count INT NOT NULL,
    mape DECIMAL(10,4) NOT NULL,
    mae DECIMAL(10,4) NOT NULL,
    evaluated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_backtest_model_version FOREIGN KEY (model_version_id) REFERENCES model_version(id)
);

INSERT INTO model_version(model_key, version, engine_type, status, feature_schema, metrics_snapshot)
SELECT 'demand', 'rule-v1', 'RULE', 'ACTIVE',
       '{"features":["recent_sales","weather","exam_week","campus_event","trend"]}',
       '{"source":"runtime"}'
WHERE NOT EXISTS (SELECT 1 FROM model_version WHERE model_key='demand' AND version='rule-v1');
