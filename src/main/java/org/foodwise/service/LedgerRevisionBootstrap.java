package org.foodwise.service;

import org.foodwise.repository.FoodwiseRepository;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(20)
public class LedgerRevisionBootstrap implements ApplicationRunner {
    private final FoodwiseRepository repository;
    public LedgerRevisionBootstrap(FoodwiseRepository repository) { this.repository = repository; }
    @Override
    public void run(ApplicationArguments args) { repository.captureUnversionedOperations(); }
}
