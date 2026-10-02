package org.foodwise.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

/**
 * 本地缓存配置：使用 Caffeine 缓存经营数据、分析结果等高频读取内容。
 * 缓存名称: dashboard, analytics, backtest, metadata, stalls, dishes, offers
 */
@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    public CacheManager cacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager(
                "dashboard", "analytics", "backtest", "metadata",
                "stalls", "dishes", "offers", "predictions", "weather"
        );
        manager.setCaffeine(Caffeine.newBuilder()
                .maximumSize(200)
                .expireAfterWrite(5, TimeUnit.MINUTES)
                .recordStats());
        manager.setAllowNullValues(false);
        return manager;
    }
}

