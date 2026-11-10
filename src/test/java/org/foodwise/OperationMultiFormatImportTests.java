package org.foodwise;

import org.apache.poi.hssf.usermodel.HSSFWorkbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.apache.poi.ss.usermodel.*;
import org.foodwise.service.OperationImportReader;
import org.foodwise.service.OperationImportService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:multi-format-import;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
@Transactional
class OperationMultiFormatImportTests {
    @Autowired OperationImportService importer;
    @Autowired OperationImportReader reader;
    @Autowired JdbcTemplate jdbc;
    private static final String[] HEADERS = {"营业日期","餐次","菜品编号","建议备餐","实际备餐","售出","优惠售出","闭餐剩余","收入","天气","是否采用建议"};
    private static final String[] VALUES = {"2026-09-20","早餐","1","10","10","8","1","2","80.50","晴","是"};

    private MockMultipartFile text(String name, String content) {
        return new MockMultipartFile("file", name, "application/octet-stream", content.getBytes(StandardCharsets.UTF_8));
    }
    private Map<String,Object> write(MockMultipartFile file) {
        return importer.importData(file,"导入测试",true,"合成格式验收","本地测试","构造数据","无外部授权材料");
    }
    private void assertAccepted(MockMultipartFile file) {
        var preview=importer.preview(file);
        assertEquals(true,preview.get("ready"));
        assertEquals(1,preview.get("totalRows"));
        var result=write(file);
        assertEquals(1,result.get("imported"));
        assertEquals(0,result.get("rejected"));
        assertEquals(8,jdbc.queryForObject("SELECT sold_qty FROM daily_operation WHERE business_date='2026-09-20' AND meal_period='早餐' AND dish_id=1",Integer.class));
        String sha=java.util.HexFormat.of().formatHex(assertDoesNotThrow(() -> java.security.MessageDigest.getInstance("SHA-256").digest(file.getBytes())));
        assertEquals(sha,result.get("sourceSha256"));
    }
    private MockMultipartFile workbook(boolean xlsx, boolean formula) throws Exception {
        try(Workbook book=xlsx ? new XSSFWorkbook() : new HSSFWorkbook();var stream=new ByteArrayOutputStream()) {
            book.createSheet("空白页");
            Sheet sheet=book.createSheet("经营台账");Row header=sheet.createRow(0);Row row=sheet.createRow(1);
            for(int i=0;i<HEADERS.length;i++){header.createCell(i).setCellValue(HEADERS[i]);row.createCell(i).setCellValue(VALUES[i]);}
            row.getCell(0).setCellValue(java.sql.Date.valueOf(LocalDate.of(2026,9,20)));
            var style=book.createCellStyle();style.setDataFormat(book.createDataFormat().getFormat("yyyy/m/d"));row.getCell(0).setCellStyle(style);
            row.getCell(2).setCellValue(1);row.getCell(8).setCellValue(80.5);
            if(formula)row.getCell(5).setCellFormula("4+4");
            book.write(stream);
            return new MockMultipartFile("file",xlsx?"台账.xlsx":"台账.xls","application/octet-stream",stream.toByteArray());
        }
    }
    @Test void xlsxUsesNumericCellsDatesAndFirstNonEmptySheet() throws Exception {assertAccepted(workbook(true,false));}
    @Test void legacyXlsUsesTheSameValidationAndWrites() throws Exception {assertAccepted(workbook(false,false));}
    @Test void tsvWithChineseHeadersImports() {assertAccepted(text("台账.tsv",String.join("\t",HEADERS)+"\n"+String.join("\t",VALUES)));}
    @Test void jsonRecordsEnvelopeImports() {
        var data=new LinkedHashMap<String,Object>();for(int i=0;i<HEADERS.length;i++)data.put(HEADERS[i],VALUES[i]);
        String json=assertDoesNotThrow(()->new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(Map.of("records",List.of(data))));
        assertAccepted(text("台账.json",json));
    }
    @Test void csvHandlesQuotedMultilineAndChineseEncoding() {
        String csv=String.join(",",HEADERS)+",event_tag\r\n"+String.join(",",VALUES)+",\"活动,\r\n备注\"\r\n";
        var file=new MockMultipartFile("file","台账.csv","text/csv",csv.getBytes(java.nio.charset.Charset.forName("GB18030")));
        assertAccepted(file);
        assertTrue(jdbc.queryForObject("SELECT event_tag FROM daily_operation WHERE business_date='2026-09-20' AND dish_id=1",String.class).contains("活动,"));
    }
    @Test void formulasFailBeforeAnyImportBatchIsCreated() throws Exception {
        int before=jdbc.queryForObject("SELECT COUNT(*) FROM operation_import_batch",Integer.class);
        var file=workbook(true,true);
        assertThrows(IllegalArgumentException.class,()->importer.preview(file));
        assertThrows(IllegalArgumentException.class,()->write(file));
        assertEquals(before,jdbc.queryForObject("SELECT COUNT(*) FROM operation_import_batch",Integer.class));
    }
    @Test void missingFieldsAndDuplicateAliasesAreRejected() {
        assertEquals(false,importer.preview(text("missing.json","[{\"日期\":\"2026-09-20\"}]")).get("ready"));
        assertThrows(IllegalArgumentException.class,()->reader.read(text("duplicate.csv","日期,business_date\n2026-09-20,2026-09-20")));
        assertThrows(IllegalArgumentException.class,()->write(text("missing.json","[{\"日期\":\"2026-09-20\"}]")));
    }
    @Test void unsupportedMalformedAndEmptyInputsAreRejected() {
        assertThrows(IllegalArgumentException.class,()->reader.read(text("page.html","<html>")));
        assertThrows(IllegalArgumentException.class,()->reader.read(text("bad.json","[{}")));
        assertThrows(IllegalArgumentException.class,()->reader.read(text("empty.json","[]")));
        assertThrows(IllegalArgumentException.class,()->reader.read(text("nested.json","[{\"日期\":{\"x\":1}}]")));
        assertThrows(IllegalArgumentException.class,()->reader.read(text("bad.csv","日期,天气\n2026-09-20,\"未闭合")));
    }
    @Test void jsonMixedRowsKeepAcceptedRecordsAndReportBadRows() {
        String keys=String.join(",",HEADERS);
        var row=new LinkedHashMap<String,Object>();for(int i=0;i<HEADERS.length;i++)row.put(HEADERS[i],VALUES[i]);
        var bad=new LinkedHashMap<>(row);bad.put("餐次","晚餐");bad.put("闭餐剩余",9);
        var file=text("mixed.json",assertDoesNotThrow(()->new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(List.of(row,bad))));
        var result=write(file);
        assertEquals(1,result.get("imported"));assertEquals(1,result.get("rejected"));
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM daily_operation WHERE business_date='2026-09-20' AND meal_period='晚餐' AND dish_id=1",Integer.class));
    }
}
