ALTER TABLE daily_operation ADD COLUMN meal_period VARCHAR(12) NOT NULL DEFAULT '未标注';

CREATE INDEX idx_daily_operation_meal ON daily_operation(business_date, meal_period, dish_id);
