package org.foodwise.service;

import org.foodwise.model.OperationLearningResult;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class OperationImportService {
    private static final List<String> REQUIRED = List.of(
            "business_date", "dish_id", "planned_qty", "prepared_qty", "sold_qty",
            "discount_sold_qty", "leftover_qty", "revenue", "weather");

    private final OperationImportReader reader;
    private final OperationFeedbackService feedbackService;
    private final FoodwiseRepository repository;

    public OperationImportService(OperationFeedbackService feedbackService, FoodwiseRepository repository, OperationImportReader reader) {
        this.reader = reader;
        this.feedbackService = feedbackService;
        this.repository = repository;
    }

    public Map<String, Object> preview(MultipartFile file) {
        var table = reader.read(file);
        List<String> missing = REQUIRED.stream().filter(name -> !table.headers().contains(name)).toList();
        return Map.of("headers", table.headers(), "sampleRows", table.rows().stream().limit(20).map(OperationImportReader.DataRow::values).toList(),
                "sampleCount", Math.min(20, table.rows().size()), "totalRows", table.rows().size(),
                "format", table.format(), "sheetName", table.sheetName(),
                "requiredFields", REQUIRED, "missingFields", missing, "ready", missing.isEmpty());
    }

    public Map<String, Object> previewCsv(MultipartFile file) { return preview(file); }

    @Transactional
    public Map<String, Object> importData(MultipartFile file, String operatorName, boolean safetyConfirmed,
                                        String sourceName, String provider, String region, String authorizationReference) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("请上传非空经营数据文件");
        }
        if (!safetyConfirmed) {
            throw new IllegalArgumentException("批量导入前请确认数据对应真实经营记录和食品安全边界");
        }
        requireSourceDeclaration(sourceName, "来源名称");
        requireSourceDeclaration(provider, "来源提供方");
        requireSourceDeclaration(region, "来源地域或范围");
        requireSourceDeclaration(authorizationReference, "授权或许可引用");
        requireSourceDeclaration(operatorName, "导入记录人");
        if (sourceName.trim().length() > 160 || provider.trim().length() > 160 || region.trim().length() > 160
                || operatorName.trim().length() > 80) throw new IllegalArgumentException("来源字段或记录人超出允许长度");

        var table = reader.read(file);
        List<String> missing = REQUIRED.stream().filter(name -> !table.headers().contains(name)).toList();
        if (!missing.isEmpty()) throw new IllegalArgumentException("缺少字段: " + String.join(", ", missing));

        byte[] rawFile;
        try { rawFile = file.getBytes(); }
        catch (IOException exception) { throw new IllegalArgumentException("读取数据文件失败: " + exception.getMessage(), exception); }
        String sourceSha256 = sha256(rawFile);
        String fileName = file.getOriginalFilename() == null || file.getOriginalFilename().isBlank()
                ? "operations" : file.getOriginalFilename();
        long sourceEvidenceId = repository.createSourceEvidence(sourceSha256, fileName, sourceName.trim(),
                provider.trim(), region.trim(), authorizationReference.trim(), operatorName.trim());

        List<String> errors = new ArrayList<>();
        int imported = 0;
        int duplicates = 0;
        long batchId = repository.createImportBatch(fileName, operatorName, sourceEvidenceId);
        Map<String, Integer> positions = new LinkedHashMap<>();
        for (int i = 0; i < table.headers().size(); i++) positions.put(table.headers().get(i), i);
        for (var row : table.rows()) {
            int lineNumber = row.number();
            try {
                List<String> values = row.values();
                String eventTag = value(values, positions, "event_tag");
                LocalDate businessDate = LocalDate.parse(value(values, positions, "business_date"));
                long dishId = new BigDecimal(value(values, positions, "dish_id")).longValueExact();
                String mealPeriod = defaultValue(value(values, positions, "meal_period"), "未标注");
                boolean duplicate = repository.operationExists(businessDate, mealPeriod, dishId);
                boolean adopted = parseBoolean(value(values, positions, "recommendation_adopted"));
                feedbackService.submit(
                        businessDate, mealPeriod, dishId,
                        new BigDecimal(value(values, positions, "planned_qty")).intValueExact(),
                        new BigDecimal(value(values, positions, "prepared_qty")).intValueExact(),
                        new BigDecimal(value(values, positions, "sold_qty")).intValueExact(),
                        new BigDecimal(value(values, positions, "discount_sold_qty")).intValueExact(),
                        new BigDecimal(value(values, positions, "leftover_qty")).intValueExact(),
                        new BigDecimal(value(values, positions, "revenue")),
                        value(values, positions, "weather"), eventTag, adopted,
                        true, operatorName, table.format() + "批量导入", sourceEvidenceId, lineNumber);
                imported++;
                String sourceKey = businessDate + ":" + mealPeriod + ":" + dishId;
                repository.saveImportRow(batchId, lineNumber, duplicate ? "DUPLICATE_UPDATED" : "IMPORTED",
                        businessDate, dishId, sourceKey, duplicate ? "同营业日和菜品已有记录，本次已更新" : null);
                if (duplicate) duplicates++;
            } catch (RuntimeException exception) {
                errors.add("第" + lineNumber + "行: " + exception.getMessage());
                repository.saveImportRow(batchId, lineNumber, "REJECTED", null, null, null, exception.getMessage());
            }
        }
        int totalRows = imported + errors.size();
        repository.completeImportBatch(batchId, totalRows, imported, errors.size(), duplicates);
        return Map.of("batchId", batchId, "sourceEvidenceId", sourceEvidenceId, "sourceSha256", sourceSha256,
                "sourceVerificationStatus", "DECLARED_UNVERIFIED", "imported", imported, "rejected", errors.size(),
                "duplicates", duplicates, "errors", errors, "totalRows", totalRows);
    }

    @Transactional
    public Map<String, Object> importCsv(MultipartFile file, String operatorName, boolean safetyConfirmed,
                                          String sourceName, String provider, String region, String authorizationReference) {
        return importData(file, operatorName, safetyConfirmed, sourceName, provider, region, authorizationReference);
    }

    /** Compatibility for internal callers; it remains explicitly unverified. */
    @Transactional
    public Map<String, Object> importCsv(MultipartFile file, String operatorName, boolean safetyConfirmed) {
        return importData(file, operatorName, safetyConfirmed, "未登记来源（兼容调用）", "待核验提供方",
                "待核验地域", "授权引用待核验");
    }

    private void requireSourceDeclaration(String value, String label) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException("请填写" + label + "；未知时请明确填写“待核验”，不能留空");
        if (value.trim().length() > 300) throw new IllegalArgumentException(label + "不能超过300个字符");
    }

    private String sha256(byte[] content) {
        try { return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content)); }
        catch (NoSuchAlgorithmException impossible) { throw new IllegalStateException("SHA-256不可用", impossible); }
    }

    private String value(List<String> values, Map<String, Integer> positions, String name) {
        Integer index = positions.get(name);
        return index != null && index < values.size() ? values.get(index).trim() : "";
    }

    private String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private boolean parseBoolean(String value) {
        return switch (value.trim().toLowerCase(java.util.Locale.ROOT)) {
            case "", "false", "否", "0" -> false;
            case "true", "是", "1" -> true;
            default -> throw new IllegalArgumentException("是否采用建议须填写true/false、是/否或1/0");
        };
    }
}
