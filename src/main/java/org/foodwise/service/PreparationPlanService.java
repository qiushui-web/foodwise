package org.foodwise.service;

import org.foodwise.prediction.PreparationPlanner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.sql.PreparedStatement;
import java.util.Map;
import tools.jackson.databind.ObjectMapper;

@Service
public class PreparationPlanService {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    public PreparationPlanService(JdbcTemplate jdbc, ObjectMapper json) { this.jdbc = jdbc; this.json = json; }

    @Transactional
    public Map<String, Object> create(long predictionId, PreparationPlanner.Inputs input, String operator) {
        var rows = jdbc.queryForList("""
                SELECT p.predicted_mid,p.first_batch,s.input_json,d.quantity_unit
                FROM prediction_record p JOIN prediction_input_snapshot s ON s.prediction_id=p.id
                JOIN dish d ON d.id=p.dish_id WHERE p.id=?
                """, predictionId);
        if (rows.isEmpty()) throw new IllegalArgumentException("预测记录不存在或缺少可追溯快照");
        var row = rows.get(0);
        var snapshot = json.readTree(String.valueOf(row.get("input_json")));
        String meal = snapshot.path("mealPeriod").asString();
        if (!java.util.List.of("早餐", "午餐", "晚餐").contains(meal))
            throw new IllegalArgumentException("现场备餐计划须选择早餐、午餐或晚餐；全日请拆分到餐次");
        if (!"份".equals(row.get("quantity_unit"))) throw new IllegalArgumentException("现场备餐计划仅支持份数口径");
        var plan = PreparationPlanner.plan(((Number) row.get("predicted_mid")).intValue(),
                ((Number) row.get("first_batch")).intValue(), input);
        var holder = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO preparation_plan(prediction_id,input_json,output_json,planned_total,created_by)
                    VALUES (?,?,?,?,?)
                    """, new String[]{"id"});
            ps.setLong(1, predictionId); ps.setString(2, json.writeValueAsString(input));
            ps.setString(3, json.writeValueAsString(plan)); ps.setInt(4, plan.plannedTotal());
            ps.setString(5, operator == null ? "anonymous" : operator); return ps;
        }, holder);
        if (holder.getKey() == null) throw new IllegalStateException("备餐计划留档失败");
        return read(holder.getKey().longValue());
    }

    @Transactional
    public Map<String, Object> createForDecision(long decisionId, String mealPeriod,
                                                  PreparationPlanner.Inputs input, String operator) {
        var rows = jdbc.queryForList("""
                SELECT r.dish_id,r.target_date,r.meal_period,r.quantity,d.quantity_unit
                FROM decision_record r JOIN dish d ON d.id=r.dish_id WHERE r.id=?
                """, decisionId);
        if (rows.isEmpty()) throw new IllegalArgumentException("备餐建议不存在或已失效");
        if (!java.util.List.of("早餐", "午餐", "晚餐").contains(mealPeriod))
            throw new IllegalArgumentException("请为早餐、午餐或晚餐制定备餐计划");
        var row = rows.get(0);
        if (!mealPeriod.equals(String.valueOf(row.get("meal_period"))))
            throw new IllegalArgumentException("餐次与原备餐建议不一致，请重新生成建议");
        if (!"份".equals(row.get("quantity_unit"))) throw new IllegalArgumentException("现场备餐计划仅支持份数口径");
        int suggested = ((Number) row.get("quantity")).intValue();
        var plan = PreparationPlanner.plan(suggested, suggested, input);
        var holder = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO decision_preparation_plan(decision_record_id,meal_period,input_json,output_json,planned_total,created_by)
                    VALUES (?,?,?,?,?,?)
                    """, new String[]{"id"});
            ps.setLong(1, decisionId); ps.setString(2, mealPeriod); ps.setString(3, json.writeValueAsString(input));
            ps.setString(4, json.writeValueAsString(plan)); ps.setInt(5, plan.plannedTotal());
            ps.setString(6, operator == null ? "anonymous" : operator); return ps;
        }, holder);
        if (holder.getKey() == null) throw new IllegalStateException("备餐计划留档失败");
        return read(holder.getKey().longValue());
    }

    @Transactional(readOnly = true)
    public Map<String, Object> read(long id) {
        var rows = jdbc.queryForList("SELECT * FROM preparation_plan WHERE id=?", id);
        if (rows.isEmpty()) return readDecisionPlan(id);
        var row = rows.get(0);
        return Map.of("id", row.get("id"), "predictionId", row.get("prediction_id"),
                "inputs", json.readTree(String.valueOf(row.get("input_json"))),
                "plan", json.readTree(String.valueOf(row.get("output_json"))),
                "createdBy", row.get("created_by"), "createdAt", String.valueOf(row.get("created_at")));
    }

    @Transactional(readOnly = true)
    public Map<String, Object> readDecisionPlan(long id) {
        var rows = jdbc.queryForList("SELECT * FROM decision_preparation_plan WHERE id=?", id);
        if (rows.isEmpty()) throw new IllegalArgumentException("备餐计划不存在");
        var row = rows.get(0);
        return Map.of("id", row.get("id"), "predictionId", row.get("decision_record_id"),
                "inputs", json.readTree(String.valueOf(row.get("input_json"))),
                "plan", json.readTree(String.valueOf(row.get("output_json"))),
                "createdBy", row.get("created_by"), "createdAt", String.valueOf(row.get("created_at")));
    }
}
