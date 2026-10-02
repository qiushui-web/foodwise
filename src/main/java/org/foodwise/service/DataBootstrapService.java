package org.foodwise.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class DataBootstrapService implements ApplicationRunner {

    private final JdbcTemplate jdbcTemplate;
    private final String csvPath;
    private final String classpathFallback;
    private final boolean demoEnabled;

    public DataBootstrapService(
            JdbcTemplate jdbcTemplate,
            @Value("${foodwise.data.csv-path:}") String csvPath,
            @Value("${foodwise.data.classpath-fallback:data/foodwise_operations_14d.csv}") String classpathFallback,
            @Value("${foodwise.data.demo-enabled:false}") boolean demoEnabled
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.csvPath = csvPath;
        this.classpathFallback = classpathFallback;
        this.demoEnabled = demoEnabled;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) throws Exception {
        if (!demoEnabled) return;
        CsvSource source = openCsv();
        List<OperationRow> rows;
        try (InputStream input = source.inputStream()) {
            rows = readRows(input);
        }
        validate(rows);
        upsertMasterData(rows);
        Integer operationCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM daily_operation", Integer.class);
        if (operationCount == null || operationCount == 0) {
            replaceOperations(rows);
        }
        upsertSources(source.label());
        seedDemoTransactionsIfEmpty();
        seedOperationAlertsIfEmpty();
    }

    private CsvSource openCsv() throws IOException {
        if (csvPath != null && !csvPath.isBlank()) {
            Path external = Path.of(csvPath);
            if (Files.isRegularFile(external)) {
                return new CsvSource(Files.newInputStream(external), external.toAbsolutePath().toString());
            }
        }
        ClassPathResource fallback = new ClassPathResource(classpathFallback);
        return new CsvSource(fallback.getInputStream(), "classpath:" + classpathFallback);
    }

    private List<OperationRow> readRows(InputStream input) throws IOException {
        List<OperationRow> rows = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String headerLine = reader.readLine();
            if (headerLine == null) throw new IllegalStateException("经营CSV为空");
            headerLine = headerLine.replace("\uFEFF", "");
            List<String> headers = parseCsvLine(headerLine);
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                List<String> values = parseCsvLine(line);
                if (values.size() != headers.size()) {
                    throw new IllegalStateException("经营CSV字段数量不一致: " + line);
                }
                Map<String, String> row = new LinkedHashMap<>();
                for (int i = 0; i < headers.size(); i++) row.put(headers.get(i), values.get(i));
                rows.add(OperationRow.from(row));
            }
        }
        return rows;
    }

    private List<String> parseCsvLine(String line) {
        List<String> values = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int index = 0; index < line.length(); index++) {
            char character = line.charAt(index);
            if (character == '"') {
                if (quoted && index + 1 < line.length() && line.charAt(index + 1) == '"') {
                    current.append('"');
                    index++;
                } else {
                    quoted = !quoted;
                }
            } else if (character == ',' && !quoted) {
                values.add(current.toString());
                current.setLength(0);
            } else {
                current.append(character);
            }
        }
        values.add(current.toString());
        return values;
    }

    private void validate(List<OperationRow> rows) {
        if (rows.isEmpty()) throw new IllegalStateException("经营CSV没有数据行");
        for (OperationRow row : rows) {
            if (row.soldQty() + row.leftoverQty() != row.preparedQty()) {
                throw new IllegalStateException("数量不守恒: " + row.businessDate() + " / " + row.dishName());
            }
            if (row.discountSoldQty() > row.soldQty()) {
                throw new IllegalStateException("优惠销量大于总销量: " + row.businessDate() + " / " + row.dishName());
            }
        }
    }

    private void upsertMasterData(List<OperationRow> rows) {
        upsertStall(1, "拾味小厨", "套餐快餐", "一层东区 08 号", "陈店长", 4.8);
        upsertStall(2, "谷禾轻食", "健康轻食", "一层南区 12 号", "周店长", 4.7);
        upsertStall(3, "暖食面坊", "粉面现制", "二层西区 03 号", "林店长", 4.6);
        upsertStall(4, "麦香烘焙", "烘焙简餐", "一层入口 02 号", "许店长", 4.9);

        Map<Integer, OperationRow> dishes = new LinkedHashMap<>();
        for (OperationRow row : rows) dishes.putIfAbsent(row.dishId(), row);
        upsertDish(dishes.get(1), 1, "套餐", 18, "#1f8a70");
        upsertDish(dishes.get(2), 1, "套餐", 25, "#df7a42");
        upsertDish(dishes.get(3), 1, "套餐", 20, "#e0a03b");
        upsertDish(dishes.get(4), 2, "轻食", 12, "#63a55c");
        upsertDish(dishes.get(5), 2, "轻食", 8, "#4f8faf");
        upsertDish(dishes.get(6), 3, "粉面", 7, "#c65a47");
        upsertDish(dishes.get(7), 4, "烘焙", 6, "#b8863b");
    }

    private void upsertStall(long id, String name, String category, String location, String manager, double rating) {
        int updated = jdbcTemplate.update("""
                UPDATE stall SET name=?, category=?, location=?, manager_name=?, status='正常经营', rating=?
                WHERE id=?
                """, name, category, location, manager, rating, id);
        if (updated == 0) {
            jdbcTemplate.update("""
                    INSERT INTO stall(id, name, category, location, manager_name, status, rating)
                    VALUES (?, ?, ?, ?, ?, '正常经营', ?)
                    """, id, name, category, location, manager, rating);
        }
    }

    private void upsertDish(OperationRow row, long stallId, String category, int prepMinutes, String color) {
        if (row == null) throw new IllegalStateException("经营CSV缺少菜品主数据");
        int updated = jdbcTemplate.update("""
                UPDATE dish SET stall_id=?, name=?, category=?, price=?, unit_cost=?, prep_minutes=?, active=TRUE, color=?
                WHERE id=?
                """, stallId, row.dishName(), category, row.price(), row.unitCost(), prepMinutes, color, row.dishId());
        if (updated == 0) {
            jdbcTemplate.update("""
                    INSERT INTO dish(id, stall_id, name, category, price, unit_cost, prep_minutes, active, color)
                    VALUES (?, ?, ?, ?, ?, ?, ?, TRUE, ?)
                    """, row.dishId(), stallId, row.dishName(), category, row.price(), row.unitCost(), prepMinutes, color);
        }
    }

    private void replaceOperations(List<OperationRow> rows) {
        jdbcTemplate.update("DELETE FROM daily_operation");
        jdbcTemplate.batchUpdate("""
                INSERT INTO daily_operation(business_date, phase, dish_id, planned_qty, prepared_qty,
                    sold_qty, discount_sold_qty, leftover_qty, revenue, weather, event_tag, recommendation_adopted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows, 100, (statement, row) -> {
            statement.setObject(1, row.businessDate());
            statement.setString(2, row.phase());
            statement.setInt(3, row.dishId());
            statement.setInt(4, row.predictedQty());
            statement.setInt(5, row.preparedQty());
            statement.setInt(6, row.soldQty());
            statement.setInt(7, row.discountSoldQty());
            statement.setInt(8, row.leftoverQty());
            statement.setBigDecimal(9, row.revenue());
            statement.setString(10, row.weather());
            statement.setString(11, row.eventTag());
            statement.setBoolean(12, row.recommendationAdopted());
        });
    }

    private void upsertSources(String importedFrom) {
        List<SourceRow> sources = List.of(
                new SourceRow("OPS_MEASURE_001", "高校食堂经营追踪数据（14日）", "operational_measurement", "某高校食堂档口经营者",
                        null, "经档口经营者授权采集", importedFrom, "经营指标分析、效果评估与界面展示", "2026年6-7月实地采集，经档口经营者授权"),
                new SourceRow("MOE_2025", "全国高等学校名单（截至2025年6月20日）", "public_statistics", "中华人民共和国教育部",
                        "https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A03/202506/t20250627_1195683.html", "政府公开信息", null,
                        "高校餐饮市场宏观背景", "不直接等同于可服务高校或档口数量"),
                new SourceRow("OPEN_METEO", "廊坊市级历史天气", "open_api", "Open-Meteo",
                        "https://archive-api.open-meteo.com/", "CC BY 4.0", null,
                        "需求预测外部天气特征", "城市级公开天气，不是校内传感器实测"),
                new SourceRow("AV_FOOD_DEMAND", "Food Demand Forecasting", "benchmark_dataset", "Analytics Vidhya",
                        "https://datahack.analyticsvidhya.com/contest/genpact-machine-learning-hackathon-1/", "平台条款，未随项目再分发", null,
                        "算法字段与方法基准", "不是本校食堂或本项目试点数据")
        );
        for (SourceRow source : sources) {
            int updated = jdbcTemplate.update("""
                    UPDATE data_source_metadata SET source_name=?, source_type=?, provider=?, source_url=?,
                        license_info=?, local_path=?, project_usage=?, truth_boundary=?, updated_at=CURRENT_TIMESTAMP
                    WHERE source_id=?
                    """, source.name(), source.type(), source.provider(), source.url(), source.licenseInfo(),
                    source.localPath(), source.usage(), source.boundary(), source.id());
            if (updated == 0) {
                jdbcTemplate.update("""
                        INSERT INTO data_source_metadata(source_id, source_name, source_type, provider, source_url,
                            license_info, local_path, project_usage, truth_boundary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, source.id(), source.name(), source.type(), source.provider(), source.url(),
                        source.licenseInfo(), source.localPath(), source.usage(), source.boundary());
            }
        }
    }

    private void seedDemoTransactionsIfEmpty() {
        Integer offerCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM discount_offer", Integer.class);
        if (offerCount != null && offerCount == 0) {
            jdbcTemplate.update("""
                    INSERT INTO discount_offer(id, dish_id, title, original_price, offer_price, total_qty,
                        remaining_qty, start_time, end_time, pickup_location, status)
                    VALUES (1, 1, '午间安心减损计划', 13.00, 9.90, 8, 3, CURRENT_TIMESTAMP,
                        TIMESTAMPADD(HOUR, 2, CURRENT_TIMESTAMP), '拾味小厨 08 号窗口', '进行中')
                    """);
            jdbcTemplate.update("""
                    INSERT INTO discount_offer(id, dish_id, title, original_price, offer_price, total_qty,
                        remaining_qty, start_time, end_time, pickup_location, status)
                    VALUES (2, 4, '轻食限量预约', 18.00, 13.90, 6, 2, CURRENT_TIMESTAMP,
                        TIMESTAMPADD(HOUR, 2, CURRENT_TIMESTAMP), '谷禾轻食 12 号窗口', '进行中')
                    """);
            jdbcTemplate.update("""
                    INSERT INTO discount_offer(id, dish_id, title, original_price, offer_price, total_qty,
                        remaining_qty, start_time, end_time, pickup_location, status)
                    VALUES (3, 7, '闭餐前全麦加餐', 9.00, 6.90, 10, 6, CURRENT_TIMESTAMP,
                        TIMESTAMPADD(HOUR, 3, CURRENT_TIMESTAMP), '麦香烘焙 02 号窗口', '进行中')
                    """);
        }
        Integer orderCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM meal_order", Integer.class);
        if (orderCount != null && orderCount == 0) {
            seedOrder(1, "FW20260629001", 1, "匿名用户 A102", 1, 9.90, "583921");
            seedOrder(2, "FW20260630002", 1, "匿名用户 B307", 1, 9.90, "294610");
            seedOrder(3, "FW20260701003", 2, "匿名用户 C118", 1, 13.90, "761204");
            seedOrder(4, "FW20260702004", 3, "匿名用户 D205", 2, 13.80, "435872");
            seedOrder(5, "FW20260703005", 2, "匿名用户 E411", 1, 13.90, "908315");
        }
    }

    private void seedOperationAlertsIfEmpty() {
        Integer alertCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM operation_alert", Integer.class);
        if (alertCount != null && alertCount > 0) return;
        jdbcTemplate.update("""
                INSERT INTO operation_alert(business_date, dish_id, alert_type, risk_level,
                    alert_message, status)
                SELECT o.business_date, o.dish_id, '剩余偏高',
                       CASE WHEN o.leftover_qty >= 7 THEN '高' ELSE '中' END,
                       CONCAT('闭餐剩余', o.leftover_qty, '份，建议复核下一餐首批备餐量'), '待处理'
                FROM daily_operation o
                WHERE o.business_date=(SELECT MAX(business_date) FROM daily_operation)
                  AND o.leftover_qty >= 4
                """);
    }

    private void seedOrder(long id, String orderNo, long offerId, String alias, int quantity, double amount, String code) {
        jdbcTemplate.update("""
                INSERT INTO meal_order(id, order_no, offer_id, student_alias, quantity, amount, pickup_code, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, '待取餐')
                """, id, orderNo, offerId, alias, quantity, amount, code);
    }

    private record CsvSource(InputStream inputStream, String label) {}

    private record SourceRow(String id, String name, String type, String provider, String url,
                             String licenseInfo, String localPath, String usage, String boundary) {}

    private record OperationRow(
            LocalDate businessDate, String phase, String stall, int dishId, String dishName,
            BigDecimal price, BigDecimal unitCost, int predictedQty, int preparedQty, int soldQty,
            int discountSoldQty, int leftoverQty, BigDecimal revenue, String weather, String eventTag,
            boolean recommendationAdopted
    ) {
        static OperationRow from(Map<String, String> row) {
            return new OperationRow(
                    LocalDate.parse(row.get("business_date")), row.get("phase"), row.get("stall"),
                    Integer.parseInt(row.get("dish_id")), row.get("dish_name"), new BigDecimal(row.get("price")),
                    new BigDecimal(row.get("unit_cost")), Integer.parseInt(row.get("predicted_qty")),
                    Integer.parseInt(row.get("prepared_qty")), Integer.parseInt(row.get("sold_qty")),
                    Integer.parseInt(row.get("discount_sold_qty")), Integer.parseInt(row.get("leftover_qty")),
                    new BigDecimal(row.get("revenue")), row.get("weather"), row.get("event_tag"),
                    Boolean.parseBoolean(row.get("recommendation_adopted"))
            );
        }
    }
}

