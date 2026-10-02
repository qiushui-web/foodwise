CREATE TABLE IF NOT EXISTS stall (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    category VARCHAR(40) NOT NULL,
    location VARCHAR(80) NOT NULL,
    manager_name VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,
    rating DECIMAL(3,1) NOT NULL DEFAULT 5.0
);

CREATE TABLE IF NOT EXISTS dish (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    stall_id BIGINT NOT NULL,
    name VARCHAR(80) NOT NULL,
    category VARCHAR(40) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    prep_minutes INT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    color VARCHAR(20) NOT NULL DEFAULT '#1f8a70',
    CONSTRAINT fk_dish_stall FOREIGN KEY (stall_id) REFERENCES stall(id)
);

CREATE TABLE IF NOT EXISTS daily_operation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    business_date DATE NOT NULL,
    phase VARCHAR(20) NOT NULL,
    dish_id BIGINT NOT NULL,
    planned_qty INT NOT NULL,
    prepared_qty INT NOT NULL,
    sold_qty INT NOT NULL,
    discount_sold_qty INT NOT NULL DEFAULT 0,
    leftover_qty INT NOT NULL,
    revenue DECIMAL(12,2) NOT NULL,
    weather VARCHAR(20) NOT NULL,
    event_tag VARCHAR(80),
    recommendation_adopted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_operation_dish FOREIGN KEY (dish_id) REFERENCES dish(id)
);

CREATE TABLE IF NOT EXISTS prediction_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_date DATE NOT NULL,
    dish_id BIGINT NOT NULL,
    predicted_low INT NOT NULL,
    predicted_mid INT NOT NULL,
    predicted_high INT NOT NULL,
    first_batch INT NOT NULL,
    replenish_qty INT NOT NULL,
    confidence DECIMAL(5,2) NOT NULL,
    weather_factor DECIMAL(5,2) NOT NULL,
    calendar_factor DECIMAL(5,2) NOT NULL,
    trend_factor DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prediction_dish FOREIGN KEY (dish_id) REFERENCES dish(id)
);

CREATE TABLE IF NOT EXISTS discount_offer (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    dish_id BIGINT NOT NULL,
    title VARCHAR(100) NOT NULL,
    original_price DECIMAL(10,2) NOT NULL,
    offer_price DECIMAL(10,2) NOT NULL,
    total_qty INT NOT NULL,
    remaining_qty INT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    pickup_location VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_offer_dish FOREIGN KEY (dish_id) REFERENCES dish(id)
);

CREATE TABLE IF NOT EXISTS meal_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no VARCHAR(40) NOT NULL UNIQUE,
    offer_id BIGINT NOT NULL,
    student_alias VARCHAR(40) NOT NULL,
    quantity INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    pickup_code VARCHAR(12) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP NULL,
    CONSTRAINT fk_order_offer FOREIGN KEY (offer_id) REFERENCES discount_offer(id)
);

CREATE TABLE IF NOT EXISTS verification_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    result VARCHAR(20) NOT NULL,
    operator_name VARCHAR(40) NOT NULL,
    verified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remark VARCHAR(200),
    CONSTRAINT fk_verify_order FOREIGN KEY (order_id) REFERENCES meal_order(id)
);

CREATE TABLE IF NOT EXISTS data_source_metadata (
    source_id VARCHAR(40) PRIMARY KEY,
    source_name VARCHAR(160) NOT NULL,
    source_type VARCHAR(40) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    source_url VARCHAR(500),
    license_info VARCHAR(120),
    local_path VARCHAR(500),
    project_usage VARCHAR(500) NOT NULL,
    truth_boundary VARCHAR(500) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_advice_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scenario VARCHAR(40) NOT NULL,
    title VARCHAR(120) NOT NULL,
    summary VARCHAR(800) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    source VARCHAR(160) NOT NULL,
    ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    input_snapshot TEXT NOT NULL,
    structured_result TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS advice_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    advice_id BIGINT NOT NULL,
    adopted BOOLEAN NOT NULL,
    adjusted_value VARCHAR(200),
    reject_reason VARCHAR(300),
    operator_name VARCHAR(60) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_feedback_advice FOREIGN KEY (advice_id) REFERENCES ai_advice_record(id)
);

CREATE TABLE IF NOT EXISTS operation_alert (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    business_date DATE NOT NULL,
    dish_id BIGINT,
    alert_type VARCHAR(60) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    alert_message VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT '待处理',
    handled_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_dish FOREIGN KEY (dish_id) REFERENCES dish(id)
);

CREATE TABLE IF NOT EXISTS campus_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_date DATE NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    event_name VARCHAR(120) NOT NULL,
    expected_impact VARCHAR(20) NOT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_feedback_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operation_id BIGINT NOT NULL,
    operator_name VARCHAR(60) NOT NULL,
    safety_confirmed BOOLEAN NOT NULL,
    submission_note VARCHAR(300),
    submission_type VARCHAR(20) NOT NULL DEFAULT '新增',
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_operation_feedback FOREIGN KEY (operation_id) REFERENCES daily_operation(id)
);

CREATE TABLE IF NOT EXISTS model_learning_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operation_id BIGINT NOT NULL,
    dish_id BIGINT NOT NULL,
    method_name VARCHAR(100) NOT NULL,
    sample_count INT NOT NULL,
    baseline_before DECIMAL(10,2) NOT NULL,
    baseline_after DECIMAL(10,2) NOT NULL,
    adjustment_rate DECIMAL(8,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_learning_operation FOREIGN KEY (operation_id) REFERENCES daily_operation(id),
    CONSTRAINT fk_learning_dish FOREIGN KEY (dish_id) REFERENCES dish(id)
);
