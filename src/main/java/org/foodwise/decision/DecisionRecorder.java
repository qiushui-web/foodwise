package org.foodwise.decision;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Component;

import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** decision_record 的读写：一次决策 + 可重放的完整输入。 */
@Component
public class DecisionRecorder {

    private final JdbcTemplate jdbcTemplate;

    public DecisionRecorder(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public long save(long dishId, LocalDate targetDate, String mealPeriod, String weather, boolean examWeek, boolean campusEvent,
                     String engine, String modelVersion, String calibrationSha256, double[] features,
                     CalibratedDecisionEngine.Computation computation) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        DecisionCostModel cost = computation.cost();
        String featuresJson = toJson(features);
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO decision_record(dish_id, target_date, meal_period, weather, exam_week, campus_event,
                        engine, model_version, calibration_sha256, features_json, category_id, day_of_week,
                        q05, q95, interval_offset, interval_low, interval_high, center, sigma,
                        price, unit_cost, discount_price, salvage_probability, shortage_lambda,
                        critical_ratio, quantity, first_batch, replenish)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            statement.setLong(1, dishId);
            statement.setObject(2, targetDate);
            statement.setString(3, mealPeriod);
            statement.setString(4, weather);
            statement.setBoolean(5, examWeek);
            statement.setBoolean(6, campusEvent);
            statement.setString(7, engine);
            statement.setString(8, modelVersion);
            statement.setString(9, calibrationSha256);
            statement.setString(10, featuresJson);
            statement.setInt(11, computation.categoryId());
            statement.setInt(12, computation.dayOfWeek());
            statement.setDouble(13, computation.q05());
            statement.setDouble(14, computation.q95());
            statement.setDouble(15, computation.offset());
            statement.setInt(16, computation.intervalLow());
            statement.setInt(17, computation.intervalHigh());
            statement.setDouble(18, computation.center());
            statement.setDouble(19, computation.sigma());
            statement.setDouble(20, cost.price());
            statement.setDouble(21, cost.unitCost());
            statement.setDouble(22, cost.discountPrice());
            statement.setDouble(23, cost.salvageProbability());
            statement.setDouble(24, cost.shortageLambda());
            statement.setDouble(25, computation.criticalRatio());
            statement.setInt(26, computation.quantity());
            statement.setInt(27, computation.firstBatch());
            statement.setInt(28, computation.replenish());
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("DECISION_RECORD_NOT_SAVED");
        return key.longValue();
    }

    public Optional<DecisionRecord> find(long id) {
        List<DecisionRecord> rows = jdbcTemplate.query("""
                        SELECT id, dish_id, target_date, weather, exam_week, campus_event, engine, model_version,
                               calibration_sha256, features_json, category_id, day_of_week, q05, q95,
                               interval_offset, interval_low, interval_high, center, sigma, price, unit_cost,
                               discount_price, salvage_probability, shortage_lambda, critical_ratio,
                               quantity, first_batch, replenish, created_at
                        FROM decision_record WHERE id = ?
                        """,
                (rs, rowNum) -> new DecisionRecord(
                        rs.getLong("id"),
                        rs.getLong("dish_id"),
                        rs.getObject("target_date", LocalDate.class),
                        rs.getString("weather"),
                        rs.getBoolean("exam_week"),
                        rs.getBoolean("campus_event"),
                        rs.getString("engine"),
                        rs.getString("model_version"),
                        rs.getString("calibration_sha256"),
                        fromJson(rs.getString("features_json")),
                        rs.getInt("category_id"),
                        rs.getInt("day_of_week"),
                        rs.getDouble("q05"),
                        rs.getDouble("q95"),
                        rs.getDouble("interval_offset"),
                        rs.getInt("interval_low"),
                        rs.getInt("interval_high"),
                        rs.getDouble("center"),
                        rs.getDouble("sigma"),
                        rs.getDouble("price"),
                        rs.getDouble("unit_cost"),
                        rs.getDouble("discount_price"),
                        rs.getDouble("salvage_probability"),
                        rs.getDouble("shortage_lambda"),
                        rs.getDouble("critical_ratio"),
                        rs.getInt("quantity"),
                        rs.getInt("first_batch"),
                        rs.getInt("replenish"),
                        rs.getObject("created_at", LocalDateTime.class)),
                id);
        return rows.stream().findFirst();
    }

    public List<Map<String, Object>> recent(int limit) {
        int size = Math.min(Math.max(limit, 1), 100);
        return jdbcTemplate.query("""
                        SELECT id, dish_id, target_date, engine, model_version, q05, q95, interval_low,
                               interval_high, critical_ratio, quantity, first_batch, replenish, created_at
                        FROM decision_record ORDER BY id DESC LIMIT ?
                        """,
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", rs.getLong("id"));
                    row.put("dishId", rs.getLong("dish_id"));
                    row.put("targetDate", rs.getObject("target_date", LocalDate.class));
                    row.put("engine", rs.getString("engine"));
                    row.put("modelVersion", rs.getString("model_version"));
                    row.put("q05", rs.getDouble("q05"));
                    row.put("q95", rs.getDouble("q95"));
                    row.put("intervalLow", rs.getInt("interval_low"));
                    row.put("intervalHigh", rs.getInt("interval_high"));
                    row.put("criticalRatio", rs.getDouble("critical_ratio"));
                    row.put("quantity", rs.getInt("quantity"));
                    row.put("firstBatch", rs.getInt("first_batch"));
                    row.put("replenish", rs.getInt("replenish"));
                    row.put("createdAt", rs.getObject("created_at", Timestamp.class));
                    return row;
                },
                size);
    }

    static String toJson(double[] features) {
        StringBuilder builder = new StringBuilder("[");
        for (int i = 0; i < features.length; i++) {
            if (i > 0) builder.append(',');
            builder.append(features[i]);
        }
        return builder.append(']').toString();
    }

    static double[] fromJson(String json) {
        if (json == null || json.isBlank()) return new double[0];
        String body = json.trim();
        if (body.startsWith("[")) body = body.substring(1);
        if (body.endsWith("]")) body = body.substring(0, body.length() - 1);
        if (body.isBlank()) return new double[0];
        String[] tokens = body.split(",");
        List<Double> values = new ArrayList<>(tokens.length);
        for (String token : tokens) values.add(Double.parseDouble(token.trim()));
        double[] out = new double[values.size()];
        for (int i = 0; i < out.length; i++) out[i] = values.get(i);
        return out;
    }
}
