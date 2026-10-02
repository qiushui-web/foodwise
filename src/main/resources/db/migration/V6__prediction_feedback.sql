CREATE TABLE IF NOT EXISTS prediction_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    prediction_id BIGINT NOT NULL,
    adopted BOOLEAN NOT NULL,
    adjusted_qty INT,
    reason VARCHAR(300),
    operator_name VARCHAR(60) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prediction_feedback_prediction FOREIGN KEY (prediction_id) REFERENCES prediction_record(id)
);

CREATE INDEX idx_prediction_feedback_prediction ON prediction_feedback(prediction_id);
