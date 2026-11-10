UPDATE data_source_metadata
SET source_type='project_snapshot_unverified',
    truth_boundary='历史登记保留；原始文件、授权、采样过程与地域尚未独立核验，不能作为河北校园实测或现场收益证据',
    updated_at=CURRENT_TIMESTAMP
WHERE source_id IN ('REAL_OPS_001','REAL_INTERVIEW_001','REAL_SURVEY_001',
                    'REAL_OBSERVE_001','REAL_LEDGER_001','REAL_ACCOUNT_001','OPS_MEASURE_001');
