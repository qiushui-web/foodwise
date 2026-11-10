CREATE TABLE operation_revision (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    operation_id BIGINT NOT NULL,
    business_date DATE NOT NULL,
    meal_period VARCHAR(20) NOT NULL,
    dish_id BIGINT NOT NULL,
    planned_qty INT NOT NULL,
    prepared_qty INT NOT NULL,
    sold_qty INT NOT NULL,
    discount_sold_qty INT NOT NULL,
    leftover_qty INT NOT NULL,
    revenue DECIMAL(12,2) NOT NULL,
    weather VARCHAR(40),
    event_tag VARCHAR(255),
    recommendation_adopted BOOLEAN NOT NULL,
    available_at DATETIME(6) NOT NULL,
    revision_at DATETIME(6) NOT NULL,
    origin VARCHAR(40) NOT NULL,
    FOREIGN KEY (operation_id) REFERENCES daily_operation(id)
);
CREATE INDEX idx_revision_visible ON operation_revision(operation_id, available_at, revision_at, id);
CREATE INDEX idx_revision_dish_date ON operation_revision(dish_id, business_date);
