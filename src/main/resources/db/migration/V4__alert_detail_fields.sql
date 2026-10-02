ALTER TABLE operation_alert ADD COLUMN suggestion VARCHAR(500);
ALTER TABLE operation_alert ADD COLUMN current_leftover INT NOT NULL DEFAULT 0;
ALTER TABLE operation_alert ADD COLUMN threshold INT NOT NULL DEFAULT 0;
