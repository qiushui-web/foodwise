package org.foodwise.api;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice(basePackages = "org.foodwise.api.v1")
public class ApiExceptionHandler {
    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    public ResponseEntity<ApiResponse<Void>> businessError(RuntimeException exception, HttpServletRequest request) {
        String traceId = ApiTrace.id(request);
        return ResponseEntity.badRequest().body(ApiResponse.failure("BUSINESS_RULE", exception.getMessage(), traceId));
    }

    @ExceptionHandler(ApiIdempotencyException.class)
    public ResponseEntity<ApiResponse<Void>> idempotencyError(ApiIdempotencyException exception,
                                                               HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(ApiResponse.failure("IDEMPOTENCY_CONFLICT", exception.getMessage(), ApiTrace.id(request)));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> validationError(MethodArgumentNotValidException exception,
                                                              HttpServletRequest request) {
        String message = exception.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .findFirst().orElse("请求参数校验失败");
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.failure("VALIDATION_ERROR", message, ApiTrace.id(request)));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiResponse<Void>> malformedRequest(HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiResponse.failure("MALFORMED_REQUEST", "请求体格式无效", ApiTrace.id(request)));
    }
}

