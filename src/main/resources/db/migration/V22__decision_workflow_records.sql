ALTER TABLE decision_record ADD COLUMN meal_period VARCHAR(20) NOT NULL DEFAULT '全日';

CREATE TABLE IF NOT EXISTS decision_preparation_plan (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    decision_record_id BIGINT NOT NULL,
    meal_period VARCHAR(20) NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    planned_total INT NOT NULL,
    created_by VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_decision_plan_record FOREIGN KEY (decision_record_id) REFERENCES decision_record(id)
);
CREATE INDEX idx_decision_plan_record ON decision_preparation_plan(decision_record_id, id);

CREATE TABLE IF NOT EXISTS decision_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    decision_record_id BIGINT NOT NULL,
    adopted BOOLEAN NOT NULL,
    adjusted_qty INT NOT NULL,
    reason VARCHAR(300),
    operator_name VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_decision_feedback_record FOREIGN KEY (decision_record_id) REFERENCES decision_record(id)
);
CREATE INDEX idx_decision_feedback_record ON decision_feedback(decision_record_id, id);
