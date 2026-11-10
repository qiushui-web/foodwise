package org.foodwise.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.csv.CSVFormat;
import org.apache.poi.ss.usermodel.*;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;

/** All formats produce the same canonical columns before business validation and writes. */
@Component
public class OperationImportReader {
    private static final int MAX_ROWS = 10_000;
    private static final int MAX_COLUMNS = 100;
    private static final long MAX_BYTES = 10 * 1024 * 1024;
    private static final Map<String, String> ALIASES = aliases();

    public record DataRow(int number, List<String> values) {}
    public record Table(String format, String sheetName, List<String> headers, List<DataRow> rows) {}

    public Table read(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new IllegalArgumentException("请上传非空经营数据文件");
        if (file.getSize() > MAX_BYTES) throw new IllegalArgumentException("导入文件不能超过10MB");
        String name = Optional.ofNullable(file.getOriginalFilename()).orElse("").toLowerCase(Locale.ROOT);
        try {
            Table table;
            if (name.endsWith(".csv")) table = delimited(file, ',', "CSV");
            else if (name.endsWith(".tsv")) table = delimited(file, '\t', "TSV");
            else if (name.endsWith(".xlsx") || name.endsWith(".xls")) table = excel(file);
            else if (name.endsWith(".json")) table = json(file);
            else throw new IllegalArgumentException("支持Excel（.xlsx/.xls）、CSV、TSV和JSON文件");
            if (table.headers().isEmpty()) throw new IllegalArgumentException("文件缺少表头或记录字段");
            if (table.rows().isEmpty()) throw new IllegalArgumentException("文件没有可导入的数据记录");
            return table;
        } catch (IOException exception) {
            throw new IllegalArgumentException("无法读取数据文件，请检查格式、编码及文件内容", exception);
        } catch (RuntimeException exception) {
            if (exception instanceof IllegalArgumentException illegal) throw illegal;
            throw new IllegalArgumentException("无法解析数据文件；请检查格式，Excel请使用未加密的工作簿", exception);
        }
    }

    private Table delimited(MultipartFile file, char delimiter, String format) throws IOException {
        String content = decode(file.getBytes());
        var options = CSVFormat.DEFAULT.builder().setDelimiter(delimiter).setIgnoreEmptyLines(true).get();
        try (var parser = options.parse(new StringReader(content))) {
            var iterator = parser.iterator();
            if (!iterator.hasNext()) throw new IllegalArgumentException("文件缺少表头");
            List<String> headers = canonical(iterator.next().toList());
            List<DataRow> rows = new ArrayList<>();
            while (iterator.hasNext()) {
                var row = iterator.next();
                List<String> values = row.toList();
                if (values.stream().allMatch(String::isBlank)) continue;
                if (values.size() != headers.size())
                    throw new IllegalArgumentException("第" + row.getRecordNumber() + "条记录列数与表头不一致");
                add(rows, new DataRow((int) row.getRecordNumber(), values));
            }
            return new Table(format, "", headers, rows);
        }
    }

    private Table excel(MultipartFile file) throws IOException {
        try (InputStream stream = file.getInputStream(); Workbook workbook = WorkbookFactory.create(stream)) {
            DataFormatter formatter = new DataFormatter(Locale.ROOT);
            for (Sheet sheet : workbook) {
                List<String> headers = null;
                List<DataRow> rows = new ArrayList<>();
                for (Row row : sheet) {
                    int width = row.getLastCellNum();
                    if (width < 0) continue;
                    if (width > MAX_COLUMNS) throw new IllegalArgumentException("表格不能超过100列");
                    List<String> values = new ArrayList<>();
                    for (int i = 0; i < width; i++) values.add(cell(row.getCell(i), formatter, row.getRowNum() + 1));
                    if (values.stream().allMatch(String::isBlank)) continue;
                    if (headers == null) {
                        while (!values.isEmpty() && values.getLast().isBlank()) values.removeLast();
                        headers = canonical(values);
                    } else {
                        if (values.size() > headers.size() && values.subList(headers.size(), values.size()).stream().anyMatch(v -> !v.isBlank()))
                            throw new IllegalArgumentException("第" + (row.getRowNum() + 1) + "行存在无表头的数据列");
                        while (values.size() < headers.size()) values.add("");
                        add(rows, new DataRow(row.getRowNum() + 1, List.copyOf(values.subList(0, headers.size()))));
                    }
                }
                if (headers != null) return new Table("EXCEL", sheet.getSheetName(), headers, rows);
            }
            throw new IllegalArgumentException("Excel工作簿没有非空工作表");
        }
    }

    private String cell(Cell cell, DataFormatter formatter, int row) {
        if (cell == null) return "";
        if (cell.getCellType() == CellType.FORMULA)
            throw new IllegalArgumentException("第" + row + "行包含公式，请将公式转为数值后导入");
        if (cell.getCellType() == CellType.ERROR)
            throw new IllegalArgumentException("第" + row + "行包含Excel错误值");
        if (cell.getCellType() == CellType.NUMERIC) {
            if (DateUtil.isCellDateFormatted(cell)) return cell.getLocalDateTimeCellValue().toLocalDate().toString();
            return java.math.BigDecimal.valueOf(cell.getNumericCellValue()).stripTrailingZeros().toPlainString();
        }
        return formatter.formatCellValue(cell).trim();
    }

    private Table json(MultipartFile file) throws IOException {
        JsonNode root = new ObjectMapper().readTree(decode(file.getBytes()));
        JsonNode records = root != null && root.isObject() ? root.get("records") : root;
        if (records == null || !records.isArray()) throw new IllegalArgumentException("JSON须为对象数组或包含records数组的对象");
        if (records.size() > MAX_ROWS) throw new IllegalArgumentException("每次最多导入10000条记录");
        LinkedHashSet<String> keys = new LinkedHashSet<>();
        for (JsonNode row : records) {
            if (!row.isObject()) throw new IllegalArgumentException("JSON每条记录须为对象");
            row.fieldNames().forEachRemaining(keys::add);
            if (keys.size() > MAX_COLUMNS) throw new IllegalArgumentException("记录字段不能超过100列");
        }
        List<String> original = new ArrayList<>(keys);
        List<String> headers = canonical(original);
        List<DataRow> rows = new ArrayList<>();
        int number = 0;
        for (JsonNode row : records) {
            List<String> values = new ArrayList<>();
            for (String key : original) {
                JsonNode value = row.get(key);
                if (value != null && value.isContainerNode()) throw new IllegalArgumentException("JSON字段须为文本、数字、布尔值或null");
                values.add(value == null || value.isNull() ? "" : value.asText());
            }
            add(rows, new DataRow(++number, values));
        }
        return new Table("JSON", "", headers, rows);
    }

    private List<String> canonical(List<String> columns) {
        if (columns.size() > MAX_COLUMNS) throw new IllegalArgumentException("表格不能超过100列");
        List<String> result = new ArrayList<>();
        for (String column : columns) {
            String key = column.replace("\uFEFF", "").trim().toLowerCase(Locale.ROOT);
            if (key.isBlank()) throw new IllegalArgumentException("表头不能为空");
            key = ALIASES.getOrDefault(key, key);
            if (result.contains(key)) throw new IllegalArgumentException("存在重复字段：" + key);
            result.add(key);
        }
        return List.copyOf(result);
    }

    private void add(List<DataRow> rows, DataRow row) {
        if (rows.size() >= MAX_ROWS) throw new IllegalArgumentException("每次最多导入10000条记录，请拆分文件");
        if (row.values().stream().anyMatch(v -> v.length() > 32_768)) throw new IllegalArgumentException("单个字段内容过长");
        rows.add(row);
    }

    private String decode(byte[] bytes) {
        // Accept common Excel exports without silently replacing invalid characters.
        for (Charset charset : List.of(StandardCharsets.UTF_8, Charset.forName("GB18030"))) {
            try {
                return charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString().replaceFirst("^\\uFEFF", "");
            } catch (CharacterCodingException ignored) { }
        }
        throw new IllegalArgumentException("文本文件请使用UTF-8或GB18030编码");
    }

    private static Map<String, String> aliases() {
        Map<String, String> map = new HashMap<>();
        map.put("营业日期", "business_date"); map.put("日期", "business_date");
        map.put("菜品id", "dish_id"); map.put("菜品编号", "dish_id");
        map.put("建议备餐", "planned_qty"); map.put("计划备餐", "planned_qty");
        map.put("实际备餐", "prepared_qty"); map.put("制作数量", "prepared_qty");
        map.put("售出", "sold_qty"); map.put("实际售出", "sold_qty");
        map.put("优惠售出", "discount_sold_qty");
        map.put("闭餐剩余", "leftover_qty"); map.put("剩余", "leftover_qty");
        map.put("收入", "revenue"); map.put("营业收入", "revenue");
        map.put("天气", "weather"); map.put("餐次", "meal_period");
        map.put("现场情况", "event_tag"); map.put("是否采用建议", "recommendation_adopted");
        return Map.copyOf(map);
    }
}
