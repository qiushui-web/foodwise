# 本机持久化重启验证

日期：2026-10-15

范围：独立文件型 H2 数据库 `data/runtime/persistence-validation`，不是项目默认演示库，也不是 MySQL。

步骤与结果：

1. 以 `local-persistent` profile、端口 8091 启动空库；Flyway 完成 v17，演示初始化得到 98 条台账。
2. 通过 `POST /api/v1/operations/feedback` 写入合成记录，使用 Idempotency-Key `persistence-validation-20261015`，返回 `operationId=99`、制作 10、售出 7、剩余 3、收入 126.00。
3. 停止应用并重新启动同一文件库。
4. 通过 `GET /api/v1/operations/rows?page=1&size=200` 读回 `total=99`，找到 `operationId=99`，日期 `2026-10-15`、售出 7、剩余 3、收入 126.0 与写入值一致。

验证结论：本机文件型 H2 的真实写入、停止、重启和读回通过。隔离库文件仍保留在被 Git 忽略的 `data/runtime/persistence-validation*`，便于复核；项目演示库 `data/runtime/foodwise` 未修改。

限制：该结果只证明本机文件库的重启保留，不证明 MySQL 备份恢复、生产权限、容灾或现场成效。MySQL 隔离实例仍因 Windows `0xC0000142` 未能启动。
