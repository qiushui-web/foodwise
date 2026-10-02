package org.foodwise.service;

import org.foodwise.model.OperationLearningResult;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
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

    private final OperationFeedbackService feedbackService;
    private final FoodwiseRepository repository;

    public OperationImportService(OperationFeedbackService feedbackService, FoodwiseRepository repository) {
        this.feedbackService = feedbackService;
        this.repository = repository;
    }

    public Map<String, Object> previewCsv(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new IllegalArgumentException("请上传非空CSV文件");
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(file.getInputStream(), StandardCharsets.UTF_8))) {
            String headerLine = reader.readLine();
            if (headerLine == null) throw new IllegalArgumentException("CSV文件缺少表头");
            List<String> headers = parseLine(stripBom(headerLine)).stream().map(String::trim).toList();
            List<List<String>> rows = new ArrayList<>();
            String line;
            while (rows.size() < 20 && (line = reader.readLine()) != null) {
                if (!line.isBlank()) rows.add(parseLine(line));
            }
            List<String> missing = REQUIRED.stream().filter(name -> !headers.contains(name)).toList();
            return Map.of("headers", headers, "sampleRows", rows, "sampleCount", rows.size(),
                    "requiredFields", REQUIRED, "missingFields", missing, "ready", missing.isEmpty());
        } catch (IOException | RuntimeException exception) {
            if (exception instanceof IllegalArgumentException illegal) throw illegal;
            throw new IllegalArgumentException("读取CSV文件失败: " + exception.getMessage(), exception);
        }
    }

    @Transactional
    public Map<String, Object> importCsv(MultipartFile file, String operatorName, boolean safetyConfirmed) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("请上传非空CSV文件");
        }
        if (!safetyConfirmed) {
            throw new IllegalArgumentException("批量导入前请确认数据对应真实经营记录和食品安全边界");
        }

        List<String> errors = new ArrayList<>();
        int imported = 0;
        int duplicates = 0;
        int lineNumber = 1;
        long batchId = repository.createImportBatch(file.getOriginalFilename(), operatorName);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(file.getInputStream(), StandardCharsets.UTF_8))) {
            String headerLine = reader.readLine();
            if (headerLine == null) throw new IllegalArgumentException("CSV文件缺少表头");
            List<String> headers = parseLine(stripBom(headerLine));
            Map<String, Integer> positions = new LinkedHashMap<>();
            for (int i = 0; i < headers.size(); i++) positions.put(headers.get(i).trim(), i);
            List<String> missing = REQUIRED.stream().filter(name -> !positions.containsKey(name)).toList();
            if (!missing.isEmpty()) throw new IllegalArgumentException("缺少字段: " + String.join(", ", missing));

            String line;
            while ((line = reader.readLine()) != null) {
                lineNumber++;
                if (line.isBlank()) continue;
                try {
                    List<String> values = parseLine(line);
                    String eventTag = value(values, positions, "event_tag");
                    LocalDate businessDate = LocalDate.parse(value(values, positions, "business_date"));
                    long dishId = Long.parseLong(value(values, positions, "dish_id"));
                    String mealPeriod = defaultValue(value(values, positions, "meal_period"), "未标注");
                    boolean duplicate = repository.operationExists(businessDate, mealPeriod, dishId);
                    boolean adopted = Boolean.parseBoolean(defaultValue(value(values, positions, "recommendation_adopted"), "false"));
                    feedbackService.submit(
                            businessDate, mealPeriod, dishId,
                            Integer.parseInt(value(values, positions, "planned_qty")),
                            Integer.parseInt(value(values, positions, "prepared_qty")),
                            Integer.parseInt(value(values, positions, "sold_qty")),
                            Integer.parseInt(value(values, positions, "discount_sold_qty")),
                            Integer.parseInt(value(values, positions, "leftover_qty")),
                            new BigDecimal(value(values, positions, "revenue")),
                            value(values, positions, "weather"), eventTag, adopted,
                            true, operatorName, "CSV批量导入");
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
        } catch (IOException exception) {
            throw new IllegalArgumentException("读取CSV文件失败: " + exception.getMessage(), exception);
        }
        int totalRows = imported + errors.size();
        repository.completeImportBatch(batchId, totalRows, imported, errors.size(), duplicates);
        return Map.of("batchId", batchId, "imported", imported, "rejected", errors.size(),
                "duplicates", duplicates, "errors", errors, "totalRows", totalRows);
    }

    private String value(List<String> values, Map<String, Integer> positions, String name) {
        Integer index = positions.get(name);
        return index != null && index < values.size() ? values.get(index).trim() : "";
    }

    private String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private String stripBom(String value) {
        return value.startsWith("\uFEFF") ? value.substring(1) : value;
    }

    private List<String> parseLine(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    field.append('"');
                    i++;
                } else quoted = !quoted;
            } else if (c == ',' && !quoted) {
                fields.add(field.toString());
                field.setLength(0);
            } else field.append(c);
        }
        if (quoted) throw new IllegalArgumentException("CSV引号未闭合");
        fields.add(field.toString());
        return fields;
    }
}

