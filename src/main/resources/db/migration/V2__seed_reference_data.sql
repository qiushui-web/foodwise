INSERT INTO campus_event (event_date, event_type, event_name, expected_impact, confirmed) VALUES
('2026-06-22', '教学日', '正常教学周', '正常', TRUE),
('2026-06-23', '教学日', '正常教学周', '正常', TRUE),
('2026-06-24', '教学日', '正常教学周', '正常', TRUE),
('2026-06-25', '教学日', '正常教学周', '正常', TRUE),
('2026-06-26', '教学日', '正常教学周', '正常', TRUE),
('2026-06-27', '考试', '期末考试周开始', '下降', TRUE),
('2026-06-28', '考试', '期末考试周', '下降', TRUE),
('2026-06-29', '教学日', '正常教学周', '正常', TRUE),
('2026-06-30', '教学日', '正常教学周', '正常', TRUE),
('2026-07-01', '教学日', '正常教学周', '正常', TRUE),
('2026-07-02', '教学日', '正常教学周', '正常', TRUE),
('2026-07-03', '教学日', '正常教学周', '正常', TRUE),
('2026-07-04', '考试', '期末考试周', '下降', TRUE),
('2026-07-05', '考试', '期末考试周结束', '下降', TRUE)
ON DUPLICATE KEY UPDATE event_name=VALUES(event_name), expected_impact=VALUES(expected_impact);

INSERT INTO data_source_metadata (source_id, source_name, source_type, provider, source_url, license_info, local_path, project_usage, truth_boundary) VALUES
('REAL_OPS_001', '食刻有数14日经营追踪数据', '经营数据', '档口经营者', NULL, '经档口经营者授权采集', '统一数据与来源/02_经营测算/foodwise_operations_14d.csv', '经营指标分析与效果评估', '经档口经营者授权采集'),
('REAL_INTERVIEW_001', '档口经营者访谈记录（5条）', '调研数据', '项目团队', NULL, '经受访者同意', '统一数据与来源/03_调研数据/01_档口访谈/档口访谈.csv', '需求调研与产品设计', '已脱敏处理'),
('REAL_SURVEY_001', '学生问卷回收（100条）', '调研数据', '项目团队', NULL, '匿名回收', '统一数据与来源/03_调研数据/02_学生问卷/学生问卷_100条.csv', '用户需求验证', '已脱敏处理'),
('REAL_OBSERVE_001', '现场观察记录（56条）', '调研数据', '项目团队', NULL, '现场记录', '统一数据与来源/03_调研数据/03_现场观察/现场观察_56条.csv', '经营场景分析', '已脱敏处理'),
('REAL_LEDGER_001', '档口连续台账（14日）', '调研数据', '档口经营者', NULL, '经档口经营者确认', '统一数据与来源/03_调研数据/04_连续台账/档口连续台账_14日.csv', '经营数据复算', '经档口经营者确认'),
('REAL_ACCOUNT_001', '单档口经营价值核算', '调研数据', '项目团队', NULL, '内部核算', '统一数据与来源/03_调研数据/05_经营核算/单档口经营价值核算.csv', '财务分析与定价参考', '基于台账数据核算')
ON DUPLICATE KEY UPDATE project_usage=VALUES(project_usage), truth_boundary=VALUES(truth_boundary);
