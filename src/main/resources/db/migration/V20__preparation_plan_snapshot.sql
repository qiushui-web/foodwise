CREATE TABLE IF NOT EXISTS preparation_plan (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prediction_id BIGINT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    planned_total INT NOT NULL,
    created_by VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_preparation_prediction FOREIGN KEY (prediction_id) REFERENCES prediction_record(id)
);
CREATE INDEX idx_preparation_prediction ON preparation_plan(prediction_id, id);
