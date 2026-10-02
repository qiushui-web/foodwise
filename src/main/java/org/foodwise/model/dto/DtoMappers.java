package org.foodwise.model.dto;

import org.springframework.jdbc.core.RowMapper;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Objects;

/**
 * 为所有 DTO Record 提供 Spring JDBC RowMapper 实现的工具类。
 * 每个方法返回对应的 RowMapper，可在 JdbcTemplate.query() 中直接使用。
 */
public final class DtoMappers {

    private DtoMappers() {}

    public static RowMapper<DashboardSummary> dashboardSummary() {
        return (rs, rowNum) -> new DashboardSummary(
                rs.getInt("prepared"),
                rs.getInt("sold"),
                rs.getInt("leftover"),
                rs.getInt("rescued"),
                nullableDecimal(rs, "revenue"),
                nullableDecimal(rs, "accuracy"),
                rs.getLong("cost_saved"),
                rs.getLong("carbon_saved"),
                rs.getLong("water_saved")
        );
    }

    public static RowMapper<TrendPoint> trendPoint() {
        return (rs, rowNum) -> new TrendPoint(
                nullableDate(rs, "business_day"),
                rs.getInt("prepared"),
                rs.getInt("sold"),
                rs.getInt("leftover"),
                rs.getInt("rescued")
        );
    }

    public static RowMapper<StallInfo> stallInfo() {
        return (rs, rowNum) -> new StallInfo(
                rs.getLong("id"),
                rs.getString("name"),
                rs.getString("category"),
                rs.getString("location"),
                rs.getString("manager_name"),
                rs.getString("status"),
                rs.getInt("rating"),
                rs.getInt("dish_count"),
                nullableDecimal(rs, "today_revenue"),
                nullableDecimal(rs, "today_leftover")
        );
    }

    public static RowMapper<DishInfo> dishInfo() {
        return (rs, rowNum) -> new DishInfo(
                rs.getLong("id"),
                rs.getString("name"),
                rs.getString("category"),
                nullableDecimal(rs, "price"),
                nullableDecimal(rs, "unit_cost"),
                rs.getInt("prep_minutes"),
                rs.getBoolean("active"),
                Objects.requireNonNullElse(rs.getString("color"), ""),
                rs.getString("stall_name"),
                rs.getDouble("avg_sales"),
                rs.getDouble("leftover_rate")
        );
    }

    public static RowMapper<DishDetail> dishDetail() {
        return (rs, rowNum) -> new DishDetail(
                rs.getLong("id"), rs.getLong("stall_id"), rs.getString("name"),
                rs.getString("category"), nullableDecimal(rs, "price"),
                nullableDecimal(rs, "unit_cost"), rs.getInt("prep_minutes"),
                rs.getBoolean("active"), Objects.requireNonNullElse(rs.getString("color"), ""),
                rs.getString("stall_name"));
    }

    public static RowMapper<LatestDishOperation> latestDishOperation() {
        return (rs, rowNum) -> new LatestDishOperation(
                nullableDate(rs, "business_date"), rs.getInt("prepared_qty"),
                rs.getInt("sold_qty"), rs.getInt("leftover_qty"),
                rs.getInt("discount_sold_qty"), Objects.requireNonNullElse(rs.getString("weather"), ""),
                Objects.requireNonNullElse(rs.getString("event_tag"), ""));
    }

    public static RowMapper<DishOperation> dishOperation() {
        return (rs, rowNum) -> new DishOperation(
                nullableDate(rs, "business_date"),
                rs.getInt("prepared_qty"),
                rs.getInt("sold_qty"),
                rs.getInt("leftover_qty"),
                rs.getInt("discount_sold_qty"),
                Objects.requireNonNullElse(rs.getString("weather"), ""),
                Objects.requireNonNullElse(rs.getString("event_tag"), "")
        );
    }

    public static RowMapper<OfferInfo> offerInfo() {
        return (rs, rowNum) -> new OfferInfo(
                rs.getLong("id"),
                rs.getLong("dish_id"),
                rs.getString("title"),
                rs.getString("dish_name"),
                rs.getString("status"),
                rs.getString("pickup_location"),
                nullableDecimal(rs, "original_price"),
                nullableDecimal(rs, "offer_price"),
                rs.getInt("quantity"),
                rs.getInt("sold_count"),
                nullableDateTime(rs, "start_time"),
                nullableDateTime(rs, "end_time"),
                nullableDateTime(rs, "created_at")
        );
    }

    public static RowMapper<AlertInfo> alertInfo() {
        return (rs, rowNum) -> new AlertInfo(
                rs.getLong("id"),
                rs.getLong("dish_id"),
                rs.getString("dish_name"),
                rs.getString("stall_name"),
                rs.getString("alert_type"),
                rs.getString("risk_level"),
                rs.getString("status"),
                rs.getString("message"),
                rs.getString("suggestion"),
                nullableDateTime(rs, "created_at"),
                rs.getInt("current_leftover"),
                rs.getInt("threshold")
        );
    }

    public static RowMapper<ReportSummary> reportSummary() {
        return (rs, rowNum) -> new ReportSummary(
                nullableDecimal(rs, "avoided_loss"),
                rs.getDouble("baseline_waste_rate"),
                rs.getDouble("intervention_waste_rate"),
                rs.getInt("baseline_leftover"),
                rs.getInt("intervention_leftover"),
                rs.getInt("baseline_pieces"),
                rs.getInt("intervention_pieces"),
                rs.getLong("records"),
                rs.getInt("baseline_days"),
                rs.getInt("intervention_days")
        );
    }

    public static RowMapper<OperationRow> operationRow() {
        return (rs, rowNum) -> new OperationRow(
                rs.getLong("dish_id"),
                rs.getLong("operation_id"),
                rs.getString("stall_name"),
                rs.getString("dish_name"),
                rs.getString("phase"),
                rs.getString("weather"),
                rs.getString("event_tag"),
                rs.getInt("planned_qty"),
                rs.getInt("prepared_qty"),
                rs.getInt("sold_qty"),
                rs.getInt("discount_sold_qty"),
                rs.getInt("leftover_qty"),
                nullableDecimal(rs, "revenue"),
                nullableDate(rs, "business_date"),
                rs.getBoolean("recommendation_adopted")
        );
    }

    public static RowMapper<DataMetadata> dataMetadata() {
        return (rs, rowNum) -> new DataMetadata(
                rs.getLong("records"),
                rs.getLong("dishes"),
                rs.getLong("stalls"),
                rs.getLong("total_prepared"),
                rs.getLong("total_sold"),
                rs.getLong("conservation_violations"),
                rs.getLong("discount_violations"),
                nullableDate(rs, "min_date"),
                nullableDate(rs, "max_date"),
                rs.getString("nature"),
                rs.getString("source_label"),
                rs.getString("sources"),
                rs.getString("statement"),
                rs.getDouble("validation_rate")
        );
    }

    public static RowMapper<StallEfficiency> stallEfficiency() {
        return (rs, rowNum) -> new StallEfficiency(
                rs.getString("stall_name"),
                rs.getDouble("sold_rate"),
                rs.getDouble("revenue_share"),
                rs.getDouble("leftover_rate"),
                rs.getInt("total_prepared"),
                rs.getInt("total_sold")
        );
    }

    public static RowMapper<CampusSeries> campusSeries() {
        return (rs, rowNum) -> new CampusSeries(
                rs.getString("phase"),
                rs.getLong("dish_id"),
                rs.getString("dish_name"),
                rs.getString("metric"),
                nullableDecimal(rs, "value")
        );
    }

    public static RowMapper<FeatureImportance> featureImportance() {
        return (rs, rowNum) -> new FeatureImportance(
                rs.getString("feature"),
                rs.getDouble("importance")
        );
    }

    // 安全的 NULL 处理

    private static BigDecimal nullableDecimal(ResultSet rs, String column) throws SQLException {
        BigDecimal val = rs.getBigDecimal(column);
        return val != null ? val : BigDecimal.ZERO;
    }

    private static LocalDate nullableDate(ResultSet rs, String column) throws SQLException {
        java.sql.Date date = rs.getDate(column);
        return date != null ? date.toLocalDate() : LocalDate.now();
    }

    private static LocalDateTime nullableDateTime(ResultSet rs, String column) throws SQLException {
        java.sql.Timestamp ts = rs.getTimestamp(column);
        return ts != null ? ts.toLocalDateTime() : LocalDateTime.now();
    }
}

