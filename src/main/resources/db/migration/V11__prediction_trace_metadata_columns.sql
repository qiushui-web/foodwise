ALTER TABLE prediction_record ADD COLUMN trace_id VARCHAR(80);
ALTER TABLE prediction_record ADD COLUMN idempotency_key VARCHAR(120);
ALTER TABLE prediction_record ADD COLUMN operator_name VARCHAR(80);
