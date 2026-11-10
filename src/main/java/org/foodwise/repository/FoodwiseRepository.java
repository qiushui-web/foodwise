package org.foodwise.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.sql.PreparedStatement;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;
import org.foodwise.model.dto.DashboardSummary;
import org.foodwise.model.dto.TrendPoint;
import org.foodwise.model.dto.StallInfo;
import org.foodwise.model.dto.DishInfo;
import org.foodwise.model.dto.ReportSummary;
import org.foodwise.model.dto.OperationRow;
import org.foodwise.model.dto.StallEfficiency;
import org.foodwise.model.dto.AlertInfo;
import org.foodwise.model.dto.OfferInfo;
import org.foodwise.model.dto.DataMetadata;
import org.foodwise.model.dto.DtoMappers;
import org.foodwise.model.dto.DishDetail;
import org.foodwise.model.dto.LatestDishOperation;

@Repository
public class FoodwiseRepository {

    private final JdbcTemplate jdbcTemplate;

    public FoodwiseRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Map<String, Object> dashboardSummary() {
        return jdbcTemplate.queryForMap("""
                SELECT COALESCE(SUM(prepared_qty), 0) AS prepared,
                       COALESCE(SUM(sold_qty), 0) AS sold,
                       COALESCE(SUM(leftover_qty), 0) AS leftover,
                       COALESCE(SUM(discount_sold_qty), 0) AS rescued,
                       COALESCE(SUM(revenue), 0) AS revenue,
                       COALESCE(AVG(CASE WHEN prepared_qty = 0 THEN 0
                           ELSE (1 - ABS(planned_qty - sold_qty) * 1.0 / prepared_qty) * 100 END), 0) AS accuracy
                FROM daily_operation
                WHERE business_date = (SELECT MAX(business_date) FROM daily_operation)
                """);
    }

    public List<Map<String, Object>> trend() {
        return jdbcTemplate.queryForList("""
                SELECT business_date AS business_day,
                       SUM(prepared_qty) AS prepared,
                       SUM(sold_qty) AS sold,
                       SUM(leftover_qty) AS leftover,
                       SUM(discount_sold_qty) AS rescued
                FROM daily_operation
                GROUP BY business_date
                ORDER BY business_date
                """);
    }

    public List<Map<String, Object>> stalls() {
        return jdbcTemplate.queryForList("""
                SELECT s.id, s.name, s.category, s.location, s.manager_name, s.status, s.rating,
                       COUNT(DISTINCT d.id) AS dish_count,
                       COALESCE(SUM(CASE WHEN o.business_date = (SELECT MAX(business_date) FROM daily_operation) THEN o.revenue ELSE 0 END), 0) AS today_revenue,
                       COALESCE(SUM(CASE WHEN o.business_date = (SELECT MAX(business_date) FROM daily_operation) THEN o.leftover_qty ELSE 0 END), 0) AS today_leftover
                FROM stall s
                LEFT JOIN dish d ON d.stall_id = s.id
                LEFT JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY s.id, s.name, s.category, s.location, s.manager_name, s.status, s.rating
                ORDER BY s.id
                """);
    }

    public List<Map<String, Object>> dishes() {
        return jdbcTemplate.queryForList("""
                SELECT d.id, d.name, d.category, d.price, d.unit_cost, d.prep_minutes, d.quantity_unit,
                       d.active, d.color, s.name AS stall_name,
                       COALESCE(AVG(o.sold_qty), 0) AS avg_sales,
                       COALESCE(AVG(CASE WHEN o.prepared_qty = 0 THEN 0
                           ELSE o.leftover_qty * 100.0 / o.prepared_qty END), 0) AS leftover_rate
                FROM dish d
                JOIN stall s ON s.id = d.stall_id
                LEFT JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY d.id, d.name, d.category, d.price, d.unit_cost, d.prep_minutes, d.quantity_unit,
                         d.active, d.color, s.name
                ORDER BY d.id
                """);
    }

    public Map<String, Object> dish(long dishId) {
        return jdbcTemplate.queryForMap("""
                SELECT d.*, s.name AS stall_name
                FROM dish d JOIN stall s ON s.id = d.stall_id
                WHERE d.id = ?
                """, dishId);
    }

    public DishDetail dishDto(long dishId) {
        return jdbcTemplate.queryForObject("""
                SELECT d.id, d.stall_id, d.name, d.category, d.price, d.unit_cost,
                       d.prep_minutes, d.active, d.color, s.name AS stall_name
                FROM dish d JOIN stall s ON s.id = d.stall_id
                WHERE d.id = ?
                """, DtoMappers.dishDetail(), dishId);
    }

    public List<Integer> recentSales(long dishId) {
        return recentSales(dishId, LocalDate.now(), "全日");
    }

    public List<Integer> recentSales(long dishId, LocalDate cutoff, String mealPeriod) {
        return recentSalesObservations(dishId, cutoff, mealPeriod).stream()
                .map(org.foodwise.prediction.SalesObservation::sold).toList();
    }

    public List<org.foodwise.prediction.SalesObservation> recentSalesObservations(long dishId, LocalDate cutoff, String mealPeriod) {
        return recentSalesObservations(dishId, cutoff, mealPeriod, 7);
    }

    /**
     * 分层基线需要按星期取中位数，7 天窗口只够一个点，因此单独开一个可放大窗口的查询。
     * 返回按 business_date 倒序，调用方自己按日期重排。
     */
    public List<org.foodwise.prediction.SalesObservation> recentSalesObservations(long dishId, LocalDate cutoff,
                                                                                  String mealPeriod, int limit) {
        int window = Math.min(Math.max(limit, 1), 120);
        return jdbcTemplate.query("""
                SELECT business_date, SUM(sold_qty) AS sold, SUM(prepared_qty) AS prepared FROM daily_operation
                WHERE dish_id = ? AND business_date <= ? AND (? = '全日' OR meal_period = ?)
                GROUP BY business_date ORDER BY business_date DESC LIMIT ?
                """, (rs, index) -> new org.foodwise.prediction.SalesObservation(rs.getDate("business_date").toLocalDate(),
                rs.getInt("sold"), rs.getInt("prepared")), dishId, cutoff, mealPeriod, mealPeriod, window);
    }

    public Map<String, Object> latestDishOperation(long dishId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT o.business_date, o.prepared_qty, o.sold_qty, o.leftover_qty,
                       o.discount_sold_qty, o.weather, o.event_tag
                FROM daily_operation o
                WHERE o.dish_id = ?
                ORDER BY o.business_date DESC
                LIMIT 1
                """, dishId);
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("该菜品暂无经营记录，无法生成优惠建议");
        }
        return rows.get(0);
    }

    public LatestDishOperation latestDishOperationDto(long dishId) {
        List<LatestDishOperation> rows = jdbcTemplate.query("""
                SELECT o.business_date, o.prepared_qty, o.sold_qty, o.leftover_qty,
                       o.discount_sold_qty, o.weather, o.event_tag
                FROM daily_operation o
                WHERE o.dish_id = ?
                ORDER BY o.business_date DESC, o.id DESC
                LIMIT 1
                """, DtoMappers.latestDishOperation(), dishId);
        if (rows.isEmpty()) {
            throw new IllegalArgumentException("该菜品暂无经营记录，无法生成优惠建议");
        }
        return rows.get(0);
    }

    public List<Map<String, Object>> riskDishes() {
        return jdbcTemplate.queryForList("""
                SELECT d.id, d.name, s.name AS stall_name, o.prepared_qty, o.sold_qty, o.leftover_qty,
                       CASE
                           WHEN o.leftover_qty >= 7 THEN '高'
                           WHEN o.leftover_qty >= 4 THEN '中'
                           ELSE '低'
                       END AS risk_level
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                JOIN stall s ON s.id = d.stall_id
                WHERE o.business_date = (SELECT MAX(business_date) FROM daily_operation)
                ORDER BY o.leftover_qty DESC
                LIMIT 6
                """);
    }

    public List<Map<String, Object>> offers() {
        return jdbcTemplate.queryForList("""
                SELECT f.id, f.title, f.original_price, f.offer_price, f.total_qty, f.remaining_qty,
                       f.start_time, f.end_time, f.pickup_location,
                       CASE WHEN f.end_time < CURRENT_TIMESTAMP THEN '已结束' ELSE f.status END AS status,
                       d.name AS dish_name, s.name AS stall_name,
                       ROUND((1 - f.offer_price / f.original_price) * 100) AS discount_rate
                FROM discount_offer f
                JOIN dish d ON d.id = f.dish_id
                JOIN stall s ON s.id = d.stall_id
                ORDER BY f.id DESC
                """);
    }

    public long createOffer(long dishId, String title, BigDecimal originalPrice, BigDecimal offerPrice,
                            int totalQty, LocalDateTime startTime, LocalDateTime endTime,
                            String pickupLocation) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO discount_offer(dish_id, title, original_price, offer_price, total_qty,
                        remaining_qty, start_time, end_time, pickup_location, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '进行中')
                    """, new String[]{"id"});
            statement.setLong(1, dishId);
            statement.setString(2, title);
            statement.setBigDecimal(3, originalPrice);
            statement.setBigDecimal(4, offerPrice);
            statement.setInt(5, totalQty);
            statement.setInt(6, totalQty);
            statement.setObject(7, startTime);
            statement.setObject(8, endTime);
            statement.setString(9, pickupLocation);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("优惠活动创建失败");
        return key.longValue();
    }

    public List<Map<String, Object>> orders() {
        return jdbcTemplate.queryForList("""
                SELECT o.id, o.order_no, o.student_alias, o.quantity, o.amount, o.pickup_code,
                       o.status, o.created_at, o.verified_at, f.title, d.name AS dish_name,
                       f.pickup_location
                FROM meal_order o
                JOIN discount_offer f ON f.id = o.offer_id
                JOIN dish d ON d.id = f.dish_id
                ORDER BY o.created_at DESC, o.id DESC
                """);
    }

    public Map<String, Object> reportSummary() {
        return jdbcTemplate.queryForMap("""
                SELECT ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.leftover_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '基线期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS baseline_leftover_rate,
                       ROUND(SUM(CASE WHEN o.phase = '干预期' THEN o.leftover_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '干预期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS intervention_leftover_rate,
                       ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.sold_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '基线期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS baseline_sell_through_rate,
                       ROUND(SUM(CASE WHEN o.phase = '干预期' THEN o.sold_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '干预期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS intervention_sell_through_rate,
                       ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.revenue ELSE 0 END), 2) AS baseline_revenue,
                       ROUND(SUM(CASE WHEN o.phase = '干预期' THEN o.revenue ELSE 0 END), 2) AS intervention_revenue,
                       SUM(CASE WHEN o.phase = '干预期' THEN o.discount_sold_qty ELSE 0 END) AS rescued_meals,
                       ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.leftover_qty * d.unit_cost ELSE 0 END) -
                             SUM(CASE WHEN o.phase = '干预期' THEN o.leftover_qty * d.unit_cost ELSE 0 END), 2) AS avoided_loss,
                       ROUND(AVG(CASE WHEN o.phase = '基线期' AND o.sold_qty > 0
                           THEN ABS(o.planned_qty - o.sold_qty) * 100.0 / o.sold_qty END), 1) AS baseline_prediction_error,
                       ROUND(AVG(CASE WHEN o.phase = '干预期' AND o.sold_qty > 0
                           THEN ABS(o.planned_qty - o.sold_qty) * 100.0 / o.sold_qty END), 1) AS prediction_error,
                       ROUND(AVG(CASE WHEN o.phase = '干预期'
                           THEN CASE WHEN o.recommendation_adopted THEN 100 ELSE 0 END END), 1) AS adoption_rate
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                """);
    }

    public Map<String, Object> dataMetadataSummary() {
        return jdbcTemplate.queryForMap("""
                SELECT COUNT(*) AS records,
                       COUNT(DISTINCT o.dish_id) AS dishes,
                       COUNT(DISTINCT d.stall_id) AS stalls,
                       COUNT(DISTINCT o.business_date) AS operating_days,
                       MIN(o.business_date) AS period_start,
                       MAX(o.business_date) AS period_end,
                       SUM(CASE WHEN o.sold_qty + o.leftover_qty = o.prepared_qty THEN 0 ELSE 1 END) AS conservation_violations,
                       SUM(CASE WHEN o.discount_sold_qty <= o.sold_qty THEN 0 ELSE 1 END) AS discount_violations
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                """);
    }

    public List<Map<String, Object>> dataSources() {
        return jdbcTemplate.queryForList("""
                SELECT source_id, source_name, source_type, provider, source_url, license_info,
                       local_path, project_usage, truth_boundary, updated_at
                FROM data_source_metadata
                ORDER BY source_id
                """);
    }

    public List<Map<String, Object>> operationRows() {
        return jdbcTemplate.queryForList("""
                SELECT o.business_date, o.phase, o.dish_id, d.name AS dish_name, s.name AS stall_name,
                       o.planned_qty, o.prepared_qty, o.sold_qty, o.discount_sold_qty, o.leftover_qty,
                       o.revenue, o.weather, o.event_tag, o.recommendation_adopted, d.unit_cost
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                JOIN stall s ON s.id = d.stall_id
                ORDER BY o.dish_id, o.business_date
                """);
    }

    public List<Map<String, Object>> financialByPhase() {
        return jdbcTemplate.queryForList("""
                SELECT o.phase,
                       SUM(o.prepared_qty) AS prepared_qty,
                       SUM(o.sold_qty) AS sold_qty,
                       SUM(o.leftover_qty) AS leftover_qty,
                       ROUND(SUM(o.revenue), 2) AS revenue,
                       ROUND(SUM(o.prepared_qty * d.unit_cost), 2) AS food_cost,
                       ROUND(SUM(o.leftover_qty * d.unit_cost), 2) AS leftover_cost,
                       ROUND(SUM(o.revenue) - SUM(o.prepared_qty * d.unit_cost), 2) AS contribution_profit,
                       ROUND((SUM(o.revenue) - SUM(o.prepared_qty * d.unit_cost)) * 100.0 /
                           NULLIF(SUM(o.revenue), 0), 1) AS contribution_margin
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                GROUP BY o.phase
                ORDER BY MIN(o.business_date)
                """);
    }

    public List<Map<String, Object>> dailyForecastSeries() {
        return jdbcTemplate.queryForList("""
                SELECT business_date AS business_day,
                       SUM(planned_qty) AS predicted,
                       SUM(sold_qty) AS actual,
                       ROUND(SUM(planned_qty) * 0.92, 0) AS predicted_low,
                       ROUND(SUM(planned_qty) * 1.08, 0) AS predicted_high
                FROM daily_operation
                GROUP BY business_date
                ORDER BY business_date
                """);
    }

    public List<Map<String, Object>> latestDishOperations() {
        return jdbcTemplate.queryForList("""
                SELECT d.name, s.name AS stall_name, o.planned_qty, o.prepared_qty, o.sold_qty, o.leftover_qty,
                       o.discount_sold_qty,
                       ROUND(o.sold_qty * 100.0 / NULLIF(o.prepared_qty, 0), 1) AS sell_through_rate
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                JOIN stall s ON s.id = d.stall_id
                WHERE o.business_date = (SELECT MAX(business_date) FROM daily_operation)
                ORDER BY d.id
                """);
    }

    public List<Map<String, Object>> stallEfficiency() {
        return jdbcTemplate.queryForList("""
                SELECT s.name,
                       ROUND(SUM(o.sold_qty) * 100.0 / NULLIF(SUM(o.prepared_qty), 0), 1) AS score
                FROM stall s
                JOIN dish d ON d.stall_id = s.id
                JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY s.id, s.name
                ORDER BY score DESC
                """);
    }

    @org.springframework.transaction.annotation.Transactional
    public OperationSaveResult upsertOperation(LocalDate businessDate, String mealPeriod, long dishId, int plannedQty,
                                               int preparedQty, int soldQty, int discountSoldQty,
                                               int leftoverQty, BigDecimal revenue, String weather,
                                               String eventTag, boolean recommendationAdopted) {
        return upsertOperation(businessDate, mealPeriod, dishId, plannedQty, preparedQty, soldQty,
                discountSoldQty, leftoverQty, revenue, weather, eventTag, recommendationAdopted, null, null);
    }

    @org.springframework.transaction.annotation.Transactional
    public OperationSaveResult upsertOperation(LocalDate businessDate, String mealPeriod, long dishId, int plannedQty,
                                               int preparedQty, int soldQty, int discountSoldQty,
                                               int leftoverQty, BigDecimal revenue, String weather,
                                               String eventTag, boolean recommendationAdopted,
                                               Long sourceEvidenceId, Integer sourceRowNo) {
        long publication = nextLedgerPublication();
        // Serialize inserts and corrections for a dish, including initially absent business keys.
        jdbcTemplate.queryForObject("SELECT id FROM dish WHERE id=? FOR UPDATE", Long.class, dishId);
        List<Long> existing = jdbcTemplate.queryForList("""
                SELECT id FROM daily_operation
                 WHERE business_date = ? AND meal_period = ? AND dish_id = ?
                ORDER BY id DESC LIMIT 1
                 """, Long.class, businessDate, mealPeriod, dishId);
        if (!existing.isEmpty()) {
            long operationId = existing.get(0);
            captureOperationRevision(operationId, "legacy_unverified", true, publication, null, null, "LEGACY_UNVERIFIED");
            jdbcTemplate.update("""
                    UPDATE daily_operation SET phase='运营回传', planned_qty=?, prepared_qty=?,
                        sold_qty=?, discount_sold_qty=?, leftover_qty=?, revenue=?, weather=?,
                        event_tag=?, recommendation_adopted=?
                    WHERE id=?
                    """, plannedQty, preparedQty, soldQty, discountSoldQty, leftoverQty, revenue,
                    weather, eventTag, recommendationAdopted, operationId);
            captureOperationRevision(operationId, "online_unverified", false, publication, sourceEvidenceId, sourceRowNo,
                    sourceEvidenceId == null ? "ONLINE_UNVERIFIED" : "SOURCE_DECLARED_UNVERIFIED");
            return new OperationSaveResult(operationId, true);
        }

        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                     INSERT INTO daily_operation(business_date, phase, meal_period, dish_id, planned_qty,
                        prepared_qty, sold_qty, discount_sold_qty, leftover_qty, revenue,
                        weather, event_tag, recommendation_adopted)
                     VALUES (?, '运营回传', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            statement.setObject(1, businessDate);
            statement.setString(2, mealPeriod);
            statement.setLong(3, dishId);
            statement.setInt(4, plannedQty);
            statement.setInt(5, preparedQty);
            statement.setInt(6, soldQty);
            statement.setInt(7, discountSoldQty);
            statement.setInt(8, leftoverQty);
            statement.setBigDecimal(9, revenue);
            statement.setString(10, weather);
            statement.setString(11, eventTag);
            statement.setBoolean(12, recommendationAdopted);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("经营记录写入失败");
        captureOperationRevision(key.longValue(), "online_unverified", false, publication, sourceEvidenceId, sourceRowNo,
                sourceEvidenceId == null ? "ONLINE_UNVERIFIED" : "SOURCE_DECLARED_UNVERIFIED");
        return new OperationSaveResult(key.longValue(), false);
    }

    @org.springframework.transaction.annotation.Transactional
    public void captureUnversionedOperations() {
        long publication = nextLedgerPublication();
        for (Long id : jdbcTemplate.queryForList("SELECT id FROM daily_operation ORDER BY id", Long.class))
            captureOperationRevision(id, "legacy_unverified", true, publication, null, null, "LEGACY_UNVERIFIED");
    }

    private long nextLedgerPublication() {
        // The singleton row serializes publications until commit, so no uncommitted hole can
        // later appear below a watermark already observed by another transaction.
        jdbcTemplate.update("UPDATE ledger_publication_state SET sequence_value=sequence_value+1 WHERE id=1");
        return jdbcTemplate.queryForObject("SELECT sequence_value FROM ledger_publication_state WHERE id=1", Long.class);
    }

    public org.foodwise.prediction.PredictionContext captureLedgerBoundary(org.foodwise.prediction.PredictionContext context) {
        if (context.publicationWatermark() != null) return context;
        if (context.explicitCutoff() || context.targetDate().isBefore(LocalDate.now(java.time.ZoneId.of("Asia/Shanghai"))))
            throw new IllegalArgumentException("历史回放需要原预测编号和当时保存的版本边界，不能仅按日期重新生成");
        long watermark = jdbcTemplate.queryForObject("SELECT sequence_value FROM ledger_publication_state WHERE id=1", Long.class);
        return context.withPublicationBoundary(watermark, java.time.Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MICROS));
    }

    private void captureOperationRevision(long operationId, String origin, boolean onlyMissing, long publication,
                                          Long sourceEvidenceId, Integer sourceRowNo, String sourceStatus) {
        // Truncate explicitly: database rounding could make a completed write appear in the future.
        var now = java.time.LocalDateTime.ofInstant(java.time.Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MICROS), java.time.ZoneOffset.UTC);
        jdbcTemplate.update("""
                INSERT INTO operation_revision(operation_id, business_date, meal_period, dish_id,
                    planned_qty, prepared_qty, sold_qty, discount_sold_qty, leftover_qty, revenue,
                    weather, event_tag, recommendation_adopted, available_at, revision_at, origin, publication_seq,
                    source_evidence_id, source_row_no, source_verification_status)
                SELECT o.id, o.business_date, o.meal_period, o.dish_id, o.planned_qty,
                    o.prepared_qty, o.sold_qty, o.discount_sold_qty, o.leftover_qty, o.revenue,
                    o.weather, o.event_tag, o.recommendation_adopted, ?, ?, ?, ?, ?, ?, ?
                FROM daily_operation o WHERE o.id=?
                """ + (onlyMissing ? " AND NOT EXISTS (SELECT 1 FROM operation_revision r WHERE r.operation_id=o.id)" : ""),
                now, now, origin, publication, sourceEvidenceId, sourceRowNo, sourceStatus, operationId);
    }

    public record LedgerHistory(List<org.foodwise.prediction.SalesObservation> observations, List<Long> revisionIds,
                                List<Map<String, Object>> sourceEvidence) {}

    public LedgerHistory ledgerHistory(org.foodwise.prediction.PredictionContext context) {
        if (context.publicationWatermark() == null) throw new IllegalArgumentException("缺少原预测的已提交版本边界，不能按时间戳猜测历史输入");
        var cutoff = LocalDateTime.ofInstant(context.predictionCutoffAt(), java.time.ZoneOffset.UTC);
        var versions = jdbcTemplate.queryForList("""
                SELECT r.id, r.business_date, r.meal_period, r.sold_qty, r.prepared_qty,
                       r.source_evidence_id, r.source_row_no, r.source_verification_status,
                       se.source_sha256, se.file_name, se.source_name, se.provider,
                       se.declared_region, se.authorization_reference, se.verification_status AS evidence_status
                FROM operation_revision r LEFT JOIN source_evidence se ON se.id=r.source_evidence_id
                WHERE r.dish_id=? AND r.business_date<=? AND (?='全日' OR r.meal_period=?)
                  AND r.available_at<=? AND r.revision_at<=? AND r.publication_seq<=?
                  AND NOT EXISTS (SELECT 1 FROM operation_revision n WHERE n.operation_id=r.operation_id
                    AND n.available_at<=? AND n.revision_at<=? AND n.publication_seq<=?
                    AND (n.publication_seq>r.publication_seq OR (n.publication_seq=r.publication_seq AND n.id>r.id)))
                ORDER BY r.business_date DESC, r.id
                """, context.dishId(), context.historyCutoff(), context.mealPeriod(), context.mealPeriod(),
                cutoff, cutoff, context.publicationWatermark(), cutoff, cutoff, context.publicationWatermark());
        var totals = new LinkedHashMap<LocalDate, int[]>();
        var ids = new java.util.ArrayList<Long>();
        var evidence = new java.util.ArrayList<Map<String, Object>>();
        var scopes = new java.util.HashMap<LocalDate, java.util.Set<String>>();
        for (var row : versions) {
            var day = ((java.sql.Date) row.get("business_date")).toLocalDate();
            if (!totals.containsKey(day) && totals.size() >= 7) continue;
            var meals = scopes.computeIfAbsent(day, ignored -> new java.util.HashSet<>());
            String meal = String.valueOf(row.get("meal_period"));
            if (meals.contains(meal) || (!meals.isEmpty() && ("全日".equals(meal) || meals.contains("全日"))))
                throw new IllegalArgumentException(day + "台账存在重复或全日/分餐次混录，请先核对原始记录");
            meals.add(meal);
            var sum = totals.computeIfAbsent(day, ignored -> new int[2]);
            sum[0] += ((Number) row.get("sold_qty")).intValue();
            sum[1] += ((Number) row.get("prepared_qty")).intValue();
            ids.add(((Number) row.get("id")).longValue());
            var evidenceRow = new java.util.LinkedHashMap<String, Object>();
            Object sourceId = row.get("source_evidence_id");
            evidenceRow.put("revisionId", ((Number) row.get("id")).longValue());
            evidenceRow.put("sourceEvidenceId", sourceId == null ? null : ((Number) sourceId).longValue());
            evidenceRow.put("sourceRowNo", row.get("source_row_no") == null ? null : ((Number) row.get("source_row_no")).intValue());
            evidenceRow.put("verificationStatus", row.get("source_verification_status"));
            evidenceRow.put("sourceSha256", row.get("source_sha256"));
            evidenceRow.put("fileName", row.get("file_name"));
            evidenceRow.put("sourceName", row.get("source_name"));
            evidenceRow.put("provider", row.get("provider"));
            evidenceRow.put("declaredRegion", row.get("declared_region"));
            evidenceRow.put("authorizationReference", row.get("authorization_reference"));
            evidenceRow.put("evidenceStatus", row.get("evidence_status"));
            evidence.add(java.util.Collections.unmodifiableMap(evidenceRow));
        }
        return new LedgerHistory(totals.entrySet().stream().map(e ->
                new org.foodwise.prediction.SalesObservation(e.getKey(), e.getValue()[0], e.getValue()[1])).toList(),
                List.copyOf(ids), List.copyOf(evidence));
    }

    public void saveOperationFeedback(long operationId, String operatorName, boolean safetyConfirmed,
                                      String note, String submissionType) {
        jdbcTemplate.update("""
                INSERT INTO operation_feedback_record(operation_id, operator_name, safety_confirmed,
                    submission_note, submission_type)
                VALUES (?, ?, ?, ?, ?)
                """, operationId, operatorName, safetyConfirmed, note, submissionType);
    }

    public void saveLearningLog(long operationId, long dishId, String methodName, int sampleCount,
                                BigDecimal baselineBefore, BigDecimal baselineAfter,
                                BigDecimal adjustmentRate) {
        jdbcTemplate.update("""
                INSERT INTO model_learning_log(operation_id, dish_id, method_name, sample_count,
                    baseline_before, baseline_after, adjustment_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, operationId, dishId, methodName, sampleCount, baselineBefore, baselineAfter, adjustmentRate);
    }

    public Map<String, Object> learningStatus() {
        return jdbcTemplate.queryForMap("""
                SELECT COUNT(*) AS learning_updates,
                       COUNT(DISTINCT dish_id) AS learned_dishes,
                       COALESCE(MAX(created_at), CURRENT_TIMESTAMP) AS latest_update,
                       COALESCE(AVG(ABS(adjustment_rate)), 0) AS average_adjustment
                FROM model_learning_log
                """);
    }

    public List<Map<String, Object>> recentOperationFeedback() {
        var rows = jdbcTemplate.queryForList("""
                SELECT f.id, f.operation_id, f.submission_type, f.operator_name, f.safety_confirmed,
                       f.submission_note, f.submitted_at, o.business_date, o.meal_period, o.dish_id,
                       o.planned_qty, o.prepared_qty, o.sold_qty, o.discount_sold_qty,
                       o.leftover_qty, o.revenue, o.weather, o.event_tag, o.recommendation_adopted,
                       d.name AS dish_name, s.name AS stall_name,
                       l.baseline_before, l.baseline_after, l.adjustment_rate
                FROM operation_feedback_record f
                JOIN daily_operation o ON o.id = f.operation_id
                JOIN dish d ON d.id = o.dish_id
                JOIN stall s ON s.id = d.stall_id
                LEFT JOIN model_learning_log l ON l.id = (
                    SELECT MAX(l2.id) FROM model_learning_log l2 WHERE l2.operation_id = o.id
                )
                ORDER BY f.submitted_at DESC, f.id DESC
                LIMIT 12
                """);
        rows.forEach(row -> row.put("business_date", String.valueOf(row.get("business_date"))));
        return rows;
    }

    public void replaceOperationAlerts(LocalDate businessDate, long dishId, int preparedQty,
                                       int soldQty, int leftoverQty) {
        jdbcTemplate.update("DELETE FROM operation_alert WHERE business_date=? AND dish_id=? AND status='待处理'",
                businessDate, dishId);
        double leftoverRate = preparedQty == 0 ? 0 : leftoverQty * 100.0 / preparedQty;
        if (leftoverQty >= 7 || leftoverRate >= 10) {
            jdbcTemplate.update("""
                    INSERT INTO operation_alert(business_date, dish_id, alert_type, risk_level,
                        alert_message, status)
                    VALUES (?, ?, '剩余偏高', ?, ?, '待处理')
                    """, businessDate, dishId, leftoverRate >= 15 ? "高" : "中",
                    "闭餐剩余" + leftoverQty + "份，剩余率" + BigDecimal.valueOf(leftoverRate).setScale(1, RoundingMode.HALF_UP) + "%");
        }
        double sellThrough = preparedQty == 0 ? 0 : soldQty * 100.0 / preparedQty;
        if (preparedQty > 0 && sellThrough >= 98) {
            jdbcTemplate.update("""
                    INSERT INTO operation_alert(business_date, dish_id, alert_type, risk_level,
                        alert_message, status)
                    VALUES (?, ?, '售罄风险', '中', ?, '待处理')
                    """, businessDate, dishId, "售罄率达到" + BigDecimal.valueOf(sellThrough).setScale(1, RoundingMode.HALF_UP) + "% ，建议关注供餐连续性");
        }
    }

    public List<Map<String, Object>> alerts() {
        return jdbcTemplate.queryForList("""
                SELECT a.id, a.business_date, a.dish_id, a.alert_type, a.risk_level, a.alert_message,
                       a.status, a.handled_at, a.created_at, d.name AS dish_name,
                       s.name AS stall_name
                FROM operation_alert a
                LEFT JOIN dish d ON d.id=a.dish_id
                LEFT JOIN stall s ON s.id=d.stall_id
                ORDER BY CASE a.status WHEN '待处理' THEN 0 ELSE 1 END,
                         CASE a.risk_level WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END,
                         a.created_at DESC
                """);
    }

    public int pendingAlertCount() {
        Integer count = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM operation_alert WHERE status='待处理'", Integer.class);
        return count == null ? 0 : count;
    }

    public int resolveAlert(long alertId) {
        return jdbcTemplate.update("""
                UPDATE operation_alert SET status='已处理', handled_at=CURRENT_TIMESTAMP
                WHERE id=? AND status='待处理'
                """, alertId);
    }

    public List<Map<String, Object>> operationExportRows() {
        return jdbcTemplate.queryForList("""
                SELECT o.business_date, o.meal_period, s.name AS stall_name, d.name AS dish_name, o.phase,
                       o.planned_qty, o.prepared_qty, o.sold_qty, o.discount_sold_qty,
                       o.leftover_qty, o.revenue, o.weather, o.event_tag,
                       o.recommendation_adopted
                FROM daily_operation o
                JOIN dish d ON d.id=o.dish_id
                JOIN stall s ON s.id=d.stall_id
                ORDER BY o.business_date DESC, s.id, d.id
                """);
    }

    public long savePrediction(long dishId, LocalDate targetDate, int low, int mid, int high,
                               int firstBatch, int replenish, BigDecimal confidence,
                               BigDecimal weatherFactor, BigDecimal calendarFactor, BigDecimal trendFactor,
                               String traceId, String idempotencyKey, String operatorName) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO prediction_record(target_date, dish_id, predicted_low, predicted_mid,
                        predicted_high, first_batch, replenish_qty, confidence, weather_factor,
                        calendar_factor, trend_factor, trace_id, idempotency_key, operator_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            statement.setObject(1, targetDate);
            statement.setLong(2, dishId);
            statement.setInt(3, low);
            statement.setInt(4, mid);
            statement.setInt(5, high);
            statement.setInt(6, firstBatch);
            statement.setInt(7, replenish);
            statement.setBigDecimal(8, confidence);
            statement.setBigDecimal(9, weatherFactor);
            statement.setBigDecimal(10, calendarFactor);
            statement.setBigDecimal(11, trendFactor);
            statement.setString(12, traceId);
            statement.setString(13, idempotencyKey);
            statement.setString(14, operatorName);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        return key == null ? 0 : key.longValue();
    }

    public List<Map<String, Object>> orderByPickupCode(String pickupCode) {
        return jdbcTemplate.queryForList("""
                SELECT o.id, o.order_no, o.student_alias, o.quantity, o.amount, o.pickup_code,
                       o.status, o.created_at, o.verified_at, f.title, d.name AS dish_name,
                       f.pickup_location
                FROM meal_order o
                JOIN discount_offer f ON f.id = o.offer_id
                JOIN dish d ON d.id = f.dish_id
                WHERE o.pickup_code = ?
                ORDER BY o.created_at DESC LIMIT 1
                """, pickupCode);
    }

    public void savePredictionSnapshot(long predictionId, String modelVersion,
                                       org.foodwise.prediction.PredictionContext context,
                                       org.foodwise.model.PredictionResult result) {
        Long modelVersionId = jdbcTemplate.queryForObject(
                "SELECT id FROM model_version WHERE model_key='demand' AND version=?",
                Long.class, modelVersion);
        var frozenHistory = ledgerHistory(context);
        if (!frozenHistory.revisionIds().equals(context.selectedRevisionIds()))
            throw new IllegalStateException("预测计算与存档台账版本不一致");
        String ledgerFeatures = new tools.jackson.databind.ObjectMapper().writeValueAsString(
                org.foodwise.prediction.FeatureBuilder.build(frozenHistory.observations()));
        String inputJson = "{\"dishId\":" + context.dishId() + ",\"weather\":\"" + json(context.weather())
                + "\",\"examWeek\":" + context.examWeek() + ",\"campusEvent\":" + context.campusEvent()
                + ",\"targetDate\":\"" + context.targetDate() + "\",\"historyCutoff\":\"" + context.historyCutoff()
                + "\",\"mealPeriod\":\"" + json(context.mealPeriod()) + "\",\"sourceNature\":\"" + json(context.sourceNature())
                + "\",\"predictionCutoffAt\":\"" + context.predictionCutoffAt()
                + "\",\"replayScope\":\"committed_publication_snapshot\",\"publicationWatermark\":" + context.publicationWatermark()
                + ",\"ledgerFeatures\":" + ledgerFeatures + ",\"sourceEvidence\":"
                + new tools.jackson.databind.ObjectMapper().writeValueAsString(frozenHistory.sourceEvidence())
                + ",\"revisionIds\":"
                + java.util.Objects.requireNonNull(context.selectedRevisionIds(), "Prediction revisions must be frozen before saving") + "}";
        String outputJson = "{\"predictionId\":" + result.predictionId() + ",\"predictedMid\":"
                + result.predictedMid() + ",\"firstBatch\":" + result.firstBatch() + ",\"replenishQty\":"
                + result.replenishQty() + "}";
        jdbcTemplate.update("""
                INSERT INTO prediction_input_snapshot(prediction_id, model_version_id, input_json, output_json)
                VALUES (?, ?, ?, ?)
                """, predictionId, modelVersionId, inputJson, outputJson);
    }

    public Map<String, Object> replayPredictionInputs(long predictionId) {
        var rows = jdbcTemplate.queryForList("SELECT input_json, output_json FROM prediction_input_snapshot WHERE prediction_id=? ORDER BY id DESC LIMIT 1", predictionId);
        if (rows.isEmpty()) throw new IllegalArgumentException("未找到该预测的输入快照");
        var mapper = new tools.jackson.databind.ObjectMapper();
        var input = mapper.readTree(String.valueOf(rows.get(0).get("input_json")));
        if (!input.has("publicationWatermark") || input.path("publicationWatermark").isNull() || !input.has("ledgerFeatures"))
            throw new IllegalArgumentException("该旧预测未留存已提交版本边界及特征，无法严格回放；保留原记录供查阅");
        var context = new org.foodwise.prediction.PredictionContext(input.path("dishId").asLong(),
                input.path("weather").asText(), input.path("examWeek").asBoolean(), input.path("campusEvent").asBoolean(),
                "replay", null, "replay", LocalDate.parse(input.path("targetDate").asText()),
                input.path("mealPeriod").asText(), input.path("sourceNature").asText(),
                java.time.Instant.parse(input.path("predictionCutoffAt").asText()))
                .withPublicationBoundary(input.path("publicationWatermark").asLong(),
                        java.time.Instant.parse(input.path("predictionCutoffAt").asText()));
        var history = ledgerHistory(context);
        var expected = new java.util.ArrayList<Long>();
        input.path("revisionIds").forEach(node -> expected.add(node.asLong()));
        if (!expected.equals(history.revisionIds())) throw new IllegalArgumentException("原预测的版本边界无法核对，不能用当前台账替代历史输入");
        if (input.has("sourceEvidence") && !sameSourceEvidence(input.path("sourceEvidence"), history.sourceEvidence()))
            throw new IllegalArgumentException("原预测的来源证据与留存版本不一致，请检查来源登记或台账版本");
        var features = org.foodwise.prediction.FeatureBuilder.build(history.observations());
        if (!mapper.valueToTree(features).equals(input.path("ledgerFeatures")))
            throw new IllegalArgumentException("原预测特征与留存版本不一致，请检查数据或特征实现的变更");
        return Map.of("predictionId", predictionId, "dataVerified", true,
                "predictionCutoffAt", context.predictionCutoffAt(), "revisionIds", history.revisionIds(),
                "observations", history.observations(), "features", features, "publicationWatermark", context.publicationWatermark(),
                "sourceEvidence", history.sourceEvidence(),
                "savedOutput", mapper.readTree(String.valueOf(rows.get(0).get("output_json"))),
                "scope", "仅核对原预测的台账输入，不代表模型有效性或现场效果验证");
    }

    private String json(String value) {
        String encoded = new tools.jackson.databind.ObjectMapper().writeValueAsString(value == null ? "" : value);
        return encoded.substring(1, encoded.length() - 1);
    }

    private boolean sameSourceEvidence(tools.jackson.databind.JsonNode saved, List<Map<String, Object>> current) {
        if (!saved.isArray() || saved.size() != current.size()) return false;
        for (int i = 0; i < current.size(); i++) {
            var row = current.get(i);
            var node = saved.get(i);
            if (!sameNumber(node.get("revisionId"), row.get("revisionId"))
                    || !sameNumber(node.get("sourceEvidenceId"), row.get("sourceEvidenceId"))
                    || !sameNumber(node.get("sourceRowNo"), row.get("sourceRowNo"))
                    || !sameText(node.get("verificationStatus"), row.get("verificationStatus"))
                    || !sameText(node.get("sourceSha256"), row.get("sourceSha256"))) return false;
            for (String key : List.of("fileName", "sourceName", "provider", "declaredRegion", "authorizationReference", "evidenceStatus"))
                if (!sameText(node.get(key), row.get(key))) return false;
        }
        return true;
    }

    private boolean sameNumber(tools.jackson.databind.JsonNode node, Object value) {
        if (node == null || node.isNull()) return value == null;
        return value instanceof Number number && node.asLong() == number.longValue();
    }

    private boolean sameText(tools.jackson.databind.JsonNode node, Object value) {
        if (node == null || node.isNull()) return value == null;
        return value != null && node.asText().equals(String.valueOf(value));
    }

    public Map<String, Object> trialEffectiveness() {
        Map<String, Object> metrics = jdbcTemplate.queryForMap("""
                SELECT COUNT(*) AS matched_predictions,
                       COALESCE(ROUND(AVG(ABS(p.predicted_mid - o.sold_qty)), 2), 0) AS mae,
                       COALESCE(ROUND(SUM(ABS(p.predicted_mid - o.sold_qty)) * 100.0 /
                           NULLIF(SUM(o.sold_qty), 0), 2), 0) AS wape,
                       COALESCE(ROUND(SUM(o.leftover_qty) * 100.0 /
                           NULLIF(SUM(o.prepared_qty), 0), 2), 0) AS leftover_rate,
                       COALESCE(ROUND(SUM(o.sold_qty) * 100.0 /
                           NULLIF(SUM(o.prepared_qty), 0), 2), 0) AS sell_through_rate,
                       COALESCE(SUM(f.adopted_feedback), 0) AS adopted_feedback,
                       COALESCE(SUM(f.feedback_count), 0) AS feedback_count
                FROM prediction_record p
                JOIN daily_operation o ON o.dish_id = p.dish_id AND o.business_date = p.target_date
                LEFT JOIN (
                    SELECT prediction_id,
                           SUM(CASE WHEN adopted THEN 1 ELSE 0 END) AS adopted_feedback,
                           COUNT(*) AS feedback_count
                    FROM prediction_feedback
                    GROUP BY prediction_id
                ) f ON f.prediction_id = p.id
                WHERE p.id = (SELECT MAX(p2.id) FROM prediction_record p2
                              WHERE p2.dish_id = p.dish_id AND p2.target_date = p.target_date)
                """);
        List<Map<String, Object>> phases = jdbcTemplate.queryForList("""
                SELECT phase, COUNT(*) AS records,
                       ROUND(SUM(leftover_qty) * 100.0 / NULLIF(SUM(prepared_qty), 0), 2) AS leftover_rate,
                       ROUND(SUM(sold_qty) * 100.0 / NULLIF(SUM(prepared_qty), 0), 2) AS sell_through_rate
                FROM daily_operation GROUP BY phase ORDER BY phase
                """);
        Map<String, Object> result = new LinkedHashMap<>(metrics);
        result.put("adoption_rate", longValue(metrics.get("feedback_count")) == 0 ? 0 :
                round(longValue(metrics.get("adopted_feedback")) * 100.0 / longValue(metrics.get("feedback_count")), 2));
        result.put("phase_comparison", phases);
        return result;
    }

    private long longValue(Object value) {
        return value instanceof Number number
                ? number.longValue()
                : value == null ? 0 : Long.parseLong(String.valueOf(value));
    }

    private double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }

    public long createSourceEvidence(String sha256, String fileName, String sourceName, String provider,
                                     String region, String authorizationReference, String createdBy) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO source_evidence(source_sha256, file_name, source_name, provider, declared_region,
                        authorization_reference, verification_status, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, 'DECLARED_UNVERIFIED', ?)
                    """, new String[]{"id"});
            statement.setString(1, sha256);
            statement.setString(2, fileName);
            statement.setString(3, sourceName);
            statement.setString(4, provider);
            statement.setString(5, region);
            statement.setString(6, authorizationReference);
            statement.setString(7, createdBy);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("来源证据登记失败");
        return key.longValue();
    }

    public List<Map<String, Object>> sourceEvidenceRecords() {
        return jdbcTemplate.queryForList("""
                SELECT id AS source_evidence_id, source_sha256, file_name, source_name, provider,
                       declared_region, authorization_reference, verification_status, created_by, created_at
                FROM source_evidence ORDER BY id DESC LIMIT 100
                """);
    }

    @Transactional
    public long upsertSchoolProfile(String schoolName, String schoolCode, String authorizationReference,
                                    String dataPurpose, String retentionPeriod, String operatorName) {
        int updated = jdbcTemplate.update("""
                UPDATE school_profile SET school_name=?, school_code=?, authorization_reference=?,
                    data_purpose=?, retention_period=?, verification_status='DECLARED_UNVERIFIED',
                    created_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=1
                """, schoolName, schoolCode, authorizationReference, dataPurpose, retentionPeriod, operatorName);
        if (updated == 0) {
            jdbcTemplate.update("""
                    INSERT INTO school_profile (id, school_name, school_code, authorization_reference,
                        data_purpose, retention_period, verification_status, created_by, created_at, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, 'DECLARED_UNVERIFIED', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, schoolName, schoolCode, authorizationReference, dataPurpose, retentionPeriod, operatorName);
        }
        return 1L;
    }

    public long createStall(String name, String category, String location, String managerName) {
        KeyHolder holder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO stall(name, category, location, manager_name, status, rating)
                    VALUES (?, ?, ?, ?, '待核对', 5.0)
                    """, new String[]{"id"});
            ps.setString(1, name); ps.setString(2, category); ps.setString(3, location); ps.setString(4, managerName);
            return ps;
        }, holder);
        Number key = holder.getKey();
        if (key == null) throw new IllegalStateException("档口建档失败");
        return key.longValue();
    }

    public long createDish(long stallId, String name, String category, BigDecimal price, BigDecimal unitCost,
                           int prepMinutes, String quantityUnit) {
        KeyHolder holder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO dish(stall_id, name, category, price, unit_cost, prep_minutes, active, color, quantity_unit)
                    VALUES (?, ?, ?, ?, ?, ?, TRUE, '#1f8a70', ?)
                    """, new String[]{"id"});
            ps.setLong(1, stallId); ps.setString(2, name); ps.setString(3, category); ps.setBigDecimal(4, price);
            ps.setBigDecimal(5, unitCost); ps.setInt(6, prepMinutes); ps.setString(7, quantityUnit);
            return ps;
        }, holder);
        Number key = holder.getKey();
        if (key == null) throw new IllegalStateException("菜品建档失败");
        return key.longValue();
    }

    public long createImportBatch(String fileName, String operatorName, long sourceEvidenceId) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO operation_import_batch(file_name, operator_name, status, source_evidence_id)
                    VALUES (?, ?, 'PROCESSING', ?)
                    """, new String[]{"id"});
            statement.setString(1, fileName == null || fileName.isBlank() ? "operations.csv" : fileName);
            statement.setString(2, operatorName == null || operatorName.isBlank() ? "运营人员" : operatorName);
            statement.setLong(3, sourceEvidenceId);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        return key == null ? 0 : key.longValue();
    }

    public void validateMealScope(LocalDate businessDate, String mealPeriod, long dishId) {
        Integer count = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM daily_operation WHERE business_date=? AND dish_id=?
                AND meal_period<>? AND (?='全日' OR meal_period='全日')
                """, Integer.class, businessDate, dishId, mealPeriod, mealPeriod);
        if (count != null && count > 0) throw new IllegalArgumentException("同一菜品同一天不能混录全日汇总与分餐次台账，请统一统计口径");
    }

    public boolean operationExists(LocalDate businessDate, String mealPeriod, long dishId) {
        Integer count = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM daily_operation WHERE business_date = ? AND meal_period = ? AND dish_id = ?
                """, Integer.class, businessDate, mealPeriod, dishId);
        return count != null && count > 0;
    }

    public void saveImportRow(long batchId, int rowNumber, String status, LocalDate businessDate,
                              Long dishId, String sourceKey, String errorMessage) {
        jdbcTemplate.update("""
                INSERT INTO operation_import_row(batch_id, row_no, status, business_date, dish_id, source_key, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batchId, rowNumber, status, businessDate, dishId, sourceKey, errorMessage);
    }

    public void completeImportBatch(long batchId, int totalRows, int importedRows, int rejectedRows, int duplicateRows) {
        jdbcTemplate.update("""
                UPDATE operation_import_batch
                SET status = ?, total_rows = ?, imported_rows = ?, rejected_rows = ?, duplicate_rows = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, rejectedRows > 0 ? "COMPLETED_WITH_ERRORS" : "COMPLETED",
                totalRows, importedRows, rejectedRows, duplicateRows, batchId);
    }

    public List<Map<String, Object>> predictionReviews() {
        var rows = jdbcTemplate.queryForList("""
                SELECT p.id AS prediction_id, p.dish_id, p.target_date, p.predicted_mid, p.created_at,
                       d.name AS dish_name, s.input_json, f.adopted, f.adjusted_qty, f.reason
                FROM prediction_record p JOIN dish d ON d.id=p.dish_id
                JOIN prediction_input_snapshot s ON s.prediction_id=p.id
                LEFT JOIN prediction_feedback f ON f.id=(SELECT MAX(f2.id) FROM prediction_feedback f2 WHERE f2.prediction_id=p.id)
                ORDER BY p.id DESC LIMIT 100
                """);
        for (var row : rows) {
            row.put("target_date", String.valueOf(row.get("target_date")));
            var snapshot = new tools.jackson.databind.ObjectMapper().readTree(String.valueOf(row.remove("input_json")));
            String meal = snapshot.path("mealPeriod").asText("");
            row.put("meal_period", meal);
            row.put("history_cutoff", snapshot.path("historyCutoff").asText("未记录"));
            row.put("source_nature", snapshot.path("sourceNature").asText("未核验"));
            var operations = jdbcTemplate.queryForList("""
                    SELECT prepared_qty, sold_qty, leftover_qty FROM daily_operation
                    WHERE dish_id=? AND business_date=? AND meal_period=?
                    """, row.get("dish_id"), row.get("target_date"), meal);
            if (!operations.isEmpty()) {
                var operation = operations.get(0);
                row.putAll(operation);
                row.put("prediction_error", ((Number) operation.get("sold_qty")).intValue() - ((Number) row.get("predicted_mid")).intValue());
                row.put("execution_error", row.get("adjusted_qty") == null ? null :
                        ((Number) operation.get("prepared_qty")).intValue() - ((Number) row.get("adjusted_qty")).intValue());
            }
        }
        return rows;
    }

    public Map<String, Object> predictionFeedbackContext(long predictionId) {
        var rows = jdbcTemplate.queryForList("""
                SELECT p.dish_id, p.target_date, p.predicted_mid, s.input_json,
                       (SELECT planned_total FROM preparation_plan WHERE prediction_id=p.id ORDER BY id DESC LIMIT 1) AS constrained_total
                FROM prediction_record p JOIN prediction_input_snapshot s ON s.prediction_id=p.id
                WHERE p.id=?
                """, predictionId);
        if (rows.isEmpty()) throw new IllegalArgumentException("预测记录不存在或缺少可追溯快照");
        return rows.get(0);
    }

    public void savePredictionFeedback(long predictionId, boolean adopted, Integer adjustedQty,
                                       String reason, String operatorName) {
        jdbcTemplate.update("""
                INSERT INTO prediction_feedback(prediction_id, adopted, adjusted_qty, reason, operator_name)
                VALUES (?, ?, ?, ?, ?)
                """, predictionId, adopted, adjustedQty, reason,
                operatorName == null || operatorName.isBlank() ? "运营人员" : operatorName);
    }

    public long saveAdvice(String scenario, String title, String summary, String riskLevel,
                           String source, boolean aiGenerated, String inputSnapshot, String structuredResult) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO ai_advice_record(scenario, title, summary, risk_level, source,
                        ai_generated, input_snapshot, structured_result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            statement.setString(1, scenario);
            statement.setString(2, title);
            statement.setString(3, summary);
            statement.setString(4, riskLevel);
            statement.setString(5, source);
            statement.setBoolean(6, aiGenerated);
            statement.setString(7, inputSnapshot);
            statement.setString(8, structuredResult);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        return key == null ? 0 : key.longValue();
    }

    public void saveAdviceFeedback(long adviceId, boolean adopted, String adjustedValue, String rejectReason) {
        jdbcTemplate.update("""
                INSERT INTO advice_feedback(advice_id, adopted, adjusted_value, reject_reason, operator_name)
                VALUES (?, ?, ?, ?, '档口操作员')
                """, adviceId, adopted, adjustedValue, rejectReason);
    }

    public int verifyOrder(long orderId, String operator) {
        int updated = jdbcTemplate.update("""
                UPDATE meal_order SET status = '已核销', verified_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = '待取餐'
                """, orderId);
        if (updated == 1) {
            jdbcTemplate.update("""
                    INSERT INTO verification_record(order_id, result, operator_name, remark)
                    VALUES (?, '成功', ?, '档口取餐核销')
                    """, orderId, operator);
        }
        return updated;
    }

        /**
     * 统计该菜品从最近一次模型更新到现在的反馈记录数
     */
    public long countFeedbackSinceLastUpdate(long dishId) {
        Long count = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM operation_feedback_record f
                JOIN daily_operation o ON o.id = f.operation_id
                WHERE o.dish_id = ?
                  AND f.submitted_at > COALESCE((
                      SELECT MAX(created_at) FROM model_learning_log
                      WHERE dish_id = ?
                  ), '2000-01-01')
                """, Long.class, dishId, dishId);
        return count == null ? 0 : count;
    }

    /**
     * 获取菜品最近的操作记录（用于反馈闭环重新计算天气因子）
     */
    public List<Map<String, Object>> recentOperationsByDish(long dishId) {
        return jdbcTemplate.queryForList("""
                SELECT business_date, weather, sold_qty, prepared_qty
                FROM daily_operation
                WHERE dish_id = ?
                ORDER BY business_date DESC
                LIMIT 5
                """, dishId);
    }

    public record OperationSaveResult(long operationId, boolean updated) {
    }


    // ====== DTO 强类型查询方法（逐步替换 Map 版本） ======

    public DashboardSummary dashboardSummaryDto() {
        Map<String, Object> raw = dashboardSummary();
        return new DashboardSummary(
            ((Number) raw.get("prepared")).intValue(),
            ((Number) raw.get("sold")).intValue(),
            ((Number) raw.get("leftover")).intValue(),
            ((Number) raw.get("rescued")).intValue(),
            (BigDecimal) raw.get("revenue"),
            (BigDecimal) raw.get("accuracy"),
            0L, 0L, 0L
        );
    }

    public List<TrendPoint> trendDto() {
        return jdbcTemplate.query("""
                SELECT business_date AS business_day,
                       SUM(prepared_qty) AS prepared,
                       SUM(sold_qty) AS sold,
                       SUM(leftover_qty) AS leftover,
                       SUM(discount_sold_qty) AS rescued
                FROM daily_operation
                GROUP BY business_date
                ORDER BY business_date
                """, DtoMappers.trendPoint());
    }

    public List<StallInfo> stallsDto() {
        return jdbcTemplate.query("""
                SELECT s.id, s.name, s.category, s.location, s.manager_name, s.status, s.rating,
                       COUNT(DISTINCT d.id) AS dish_count,
                       COALESCE(SUM(CASE WHEN o.business_date = (SELECT MAX(business_date) FROM daily_operation) THEN o.revenue ELSE 0 END), 0) AS today_revenue,
                       COALESCE(SUM(CASE WHEN o.business_date = (SELECT MAX(business_date) FROM daily_operation) THEN o.leftover_qty ELSE 0 END), 0) AS today_leftover
                FROM stall s
                LEFT JOIN dish d ON d.stall_id = s.id
                LEFT JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY s.id, s.name, s.category, s.location, s.manager_name, s.status, s.rating
                ORDER BY s.id
                """, DtoMappers.stallInfo());
    }

    public List<DishInfo> dishesDto() {
        return jdbcTemplate.query("""
                SELECT d.id, d.name, d.category, d.price, d.unit_cost, d.prep_minutes, d.quantity_unit,
                       d.active, d.color, s.name AS stall_name,
                       COALESCE(AVG(o.sold_qty), 0) AS avg_sales,
                       COALESCE(AVG(CASE WHEN o.prepared_qty = 0 THEN 0
                           ELSE o.leftover_qty * 100.0 / o.prepared_qty END), 0) AS leftover_rate
                FROM dish d
                JOIN stall s ON s.id = d.stall_id
                LEFT JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY d.id, d.name, d.category, d.price, d.unit_cost, d.prep_minutes, d.quantity_unit,
                         d.active, d.color, s.name
                ORDER BY d.id
                """, DtoMappers.dishInfo());
    }

    public ReportSummary reportSummaryDto() {
        return jdbcTemplate.queryForObject("""
                SELECT ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.leftover_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '基线期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS baseline_waste_rate,
                       ROUND(SUM(CASE WHEN o.phase = '干预期' THEN o.leftover_qty ELSE 0 END) * 100.0 /
                           NULLIF(SUM(CASE WHEN o.phase = '干预期' THEN o.prepared_qty ELSE 0 END), 0), 1) AS intervention_waste_rate,
                       SUM(CASE WHEN o.phase = '基线期' THEN o.leftover_qty ELSE 0 END) AS baseline_leftover,
                       SUM(CASE WHEN o.phase = '干预期' THEN o.leftover_qty ELSE 0 END) AS intervention_leftover,
                       SUM(CASE WHEN o.phase = '基线期' THEN o.sold_qty ELSE 0 END) AS baseline_pieces,
                       SUM(CASE WHEN o.phase = '干预期' THEN o.sold_qty ELSE 0 END) AS intervention_pieces,
                       COUNT(*) AS records,
                       COUNT(DISTINCT CASE WHEN o.phase = '基线期' THEN o.business_date END) AS baseline_days,
                       COUNT(DISTINCT CASE WHEN o.phase = '干预期' THEN o.business_date END) AS intervention_days,
                       ROUND(SUM(CASE WHEN o.phase = '基线期' THEN o.leftover_qty * d.unit_cost ELSE 0 END) -
                             SUM(CASE WHEN o.phase = '干预期' THEN o.leftover_qty * d.unit_cost ELSE 0 END), 2) AS avoided_loss
                FROM daily_operation o
                JOIN dish d ON d.id = o.dish_id
                """, DtoMappers.reportSummary());
    }

    public List<OperationRow> operationRowsDto() {
        return jdbcTemplate.query("""
                SELECT o.id AS operation_id, o.dish_id, o.meal_period, s.name AS stall_name, d.name AS dish_name, o.phase,
                       o.planned_qty, o.prepared_qty, o.sold_qty, o.discount_sold_qty,
                       o.leftover_qty, o.revenue, o.business_date, o.weather, o.event_tag,
                       o.recommendation_adopted
                FROM daily_operation o
                JOIN dish d ON d.id=o.dish_id
                JOIN stall s ON s.id=d.stall_id
                ORDER BY o.business_date, s.id, d.id
                """, DtoMappers.operationRow());
    }

    public List<StallEfficiency> stallEfficiencyDto() {
        return jdbcTemplate.query("""
                SELECT s.name AS stall_name,
                       ROUND(SUM(o.sold_qty) * 100.0 / NULLIF(SUM(o.prepared_qty), 0), 1) AS sold_rate,
                       ROUND(SUM(o.revenue) * 100.0 / NULLIF(SUM(SUM(o.revenue)) OVER (), 0), 1) AS revenue_share,
                       ROUND(SUM(o.leftover_qty) * 100.0 / NULLIF(SUM(o.prepared_qty), 0), 1) AS leftover_rate,
                       SUM(o.prepared_qty) AS total_prepared,
                       SUM(o.sold_qty) AS total_sold
                FROM stall s
                JOIN dish d ON d.stall_id = s.id
                JOIN daily_operation o ON o.dish_id = d.id
                GROUP BY s.id, s.name
                ORDER BY s.id
                """, DtoMappers.stallEfficiency());
    }

    public List<AlertInfo> alertsDto() {
        return jdbcTemplate.query("""
                SELECT a.id, a.dish_id, d.name AS dish_name, s.name AS stall_name,
                       a.alert_type, a.risk_level, a.status, a.message, a.suggestion,
                       a.created_at, a.current_leftover, a.threshold
                FROM alert a
                JOIN dish d ON d.id = a.dish_id
                JOIN stall s ON s.id = d.stall_id
                ORDER BY a.created_at DESC
                """, DtoMappers.alertInfo());
    }

    public List<OfferInfo> offersDto() {
        return jdbcTemplate.query("""
                SELECT f.id, f.dish_id, f.title, d.name AS dish_name, f.status, f.pickup_location,
                       f.original_price, f.offer_price, f.total_qty AS quantity,
                       f.total_qty - f.remaining_qty AS sold_count,
                       f.start_time, f.end_time, f.created_at
                FROM discount_offer f
                JOIN dish d ON d.id = f.dish_id
                ORDER BY f.created_at DESC
                """, DtoMappers.offerInfo());
    }

    public DataMetadata dataMetadataDto() {
        Map<String, Object> summary = dataMetadataSummary();
        List<String> src = dataSources().stream().map(m -> String.valueOf(m.get("name"))).toList();
        return new DataMetadata(
            ((Number) summary.get("records")).longValue(),
            ((Number) summary.get("dishes")).longValue(),
            ((Number) summary.get("stalls")).longValue(),
            0L, 0L,
            ((Number) summary.get("conservation_violations")).longValue(),
            ((Number) summary.get("discount_violations")).longValue(),
            (LocalDate) summary.get("period_start"),
            (LocalDate) summary.get("period_end"),
            "",
            "",
            String.join(", ", src),
            "",
            0.0
        );
    }


}

