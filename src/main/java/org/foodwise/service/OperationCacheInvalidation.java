package org.foodwise.service;

import org.springframework.cache.CacheManager;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class OperationCacheInvalidation {
    private final CacheManager caches;
    public OperationCacheInvalidation(CacheManager caches) { this.caches = caches; }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void committed(OperationDataChanged event) {
        for (String name : new String[]{"dashboard", "analytics", "backtest", "metadata", "stalls", "dishes", "offers", "predictions"}) {
            var cache = caches.getCache(name);
            if (cache != null) cache.clear();
        }
    }
}
