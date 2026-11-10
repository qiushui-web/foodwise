-- 校准分位引擎的决策留痕：保存 24 维输入、分位、校准偏移、成本参数与最终建议量。
-- 目的不是“记录一次预测”，而是让 /decisions/{id}/replay 能用同一份输入重算并比对，
-- 从而证明模型文件与校准产物没有被悄悄替换。
CREATE TABLE IF NOT EXISTS decision_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    dish_id BIGINT NOT NULL,
    target_date DATE NOT NULL,
    weather VARCHAR(20) NOT NULL,
    exam_week BOOLEAN NOT NULL,
    campus_event BOOLEAN NOT NULL,
    engine VARCHAR(40) NOT NULL,
    model_version VARCHAR(60) NOT NULL,
    calibration_sha256 VARCHAR(64) NOT NULL,
    features_json TEXT NOT NULL,
    category_id INT NOT NULL,
    day_of_week INT NOT NULL,
    q05 DOUBLE NOT NULL,
    q95 DOUBLE NOT NULL,
    interval_offset DOUBLE NOT NULL,
    interval_low INT NOT NULL,
    interval_high INT NOT NULL,
    center DOUBLE NOT NULL,
    sigma DOUBLE NOT NULL,
    price DOUBLE NOT NULL,
    unit_cost DOUBLE NOT NULL,
    discount_price DOUBLE NOT NULL,
    salvage_probability DOUBLE NOT NULL,
    shortage_lambda DOUBLE NOT NULL,
    critical_ratio DOUBLE NOT NULL,
    quantity INT NOT NULL,
    first_batch INT NOT NULL,
    replenish INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_decision_record_dish (dish_id),
    INDEX idx_decision_record_created (created_at)
);

INSERT INTO model_version(model_key, version, engine_type, status, feature_schema, metrics_snapshot, artifact_path)
SELECT 'demand', '2026.10.27-interval-v1', 'CALIBRATED_QUANTILE', 'ACTIVE',
       '{"features":["day_of_week","is_weekend","is_exam_week","has_campus_event","weather_code","temp_max_c","category_id","price","unit_cost","discount_rate","promotion_flag","lag_1_sold","lag_2_sold","lag_3_sold","lag_7_sold","rolling_mean_3","rolling_mean_7","rolling_std_7","same_dow_last_4w_mean","is_school_holiday","is_state_holiday","special_day","comp_price_ratio","recent_trend_3d"],"quantiles":[0.05,0.95]}',
       '{"method":"cqr+stratified-aci","picp90":0.9667,"pinaw90":0.2844,"winkler90":19.01,"evaluated_on":"finetune_uwaste:test(390rows)"}',
       'modeling/model_manifest.json'
WHERE NOT EXISTS (SELECT 1 FROM model_version WHERE model_key='demand' AND version='2026.10.27-interval-v1');