package org.foodwise.api;

public class ApiIdempotencyException extends IllegalStateException {
    public ApiIdempotencyException(String message) {
        super(message);
    }
}

