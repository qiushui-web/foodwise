package org.foodwise.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.Customizer;
import org.springframework.http.HttpMethod;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

import java.util.ArrayList;
import java.util.List;

@Configuration
@ConditionalOnProperty(name = "foodwise.security.enabled", havingValue = "true")
public class SecurityConfig {

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    UserDetailsService userDetailsService(
            PasswordEncoder passwordEncoder,
            @Value("${foodwise.security.admin-user:foodwise-admin}") String username,
            @Value("${foodwise.security.admin-password:}") String password,
            @Value("${foodwise.security.operator-user:}") String operatorUser,
            @Value("${foodwise.security.operator-password:}") String operatorPassword,
            @Value("${foodwise.security.analyst-user:}") String analystUser,
            @Value("${foodwise.security.analyst-password:}") String analystPassword) {
        if (password == null || password.length() < 10) {
            throw new IllegalStateException("启用登录保护时，FOODWISE_ADMIN_PASSWORD至少需要10位");
        }
        List<org.springframework.security.core.userdetails.UserDetails> users = new ArrayList<>();
        users.add(User.withUsername(username)
                .password(passwordEncoder.encode(password))
                .roles("ADMIN")
                .build());
        addOptionalUser(users, passwordEncoder, operatorUser, operatorPassword, "OPERATOR");
        addOptionalUser(users, passwordEncoder, analystUser, analystPassword, "ANALYST");
        return new InMemoryUserDetailsManager(users);
    }

    private void addOptionalUser(List<org.springframework.security.core.userdetails.UserDetails> users,
                                 PasswordEncoder encoder, String username, String password, String role) {
        if (username == null || username.isBlank()) return;
        if (password == null || password.length() < 10) {
            throw new IllegalStateException(role + "账号密码至少需要10位");
        }
        users.add(User.withUsername(username).password(encoder.encode(password)).roles(role).build());
    }

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/login", "/api/health", "/css/**", "/images/**", "/build/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/**").hasAnyRole("ADMIN", "OPERATOR", "ANALYST")
                        .requestMatchers(HttpMethod.POST, "/api/v1/predictions", "/api/v1/offers", "/api/v1/intelligence/**",
                                "/api/v1/orders/*/verify", "/api/v1/alerts/*/resolve", "/api/v1/operations/feedback")
                        .hasAnyRole("ADMIN", "OPERATOR")
                        .requestMatchers(HttpMethod.POST, "/api/v1/operations/import/preview").hasAnyRole("ADMIN", "OPERATOR", "ANALYST")
                        .requestMatchers(HttpMethod.POST, "/api/v1/operations/import").hasAnyRole("ADMIN", "OPERATOR")
                        .requestMatchers(HttpMethod.POST, "/api/v1/**").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.PUT, "/api/v1/**").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.DELETE, "/api/v1/**").hasRole("ADMIN")
                        .requestMatchers("/api/**").hasAnyRole("ADMIN", "OPERATOR", "ANALYST")
                        .anyRequest().authenticated())
                .csrf(csrf -> csrf.ignoringRequestMatchers("/api/**", "/login"))
                .httpBasic(Customizer.withDefaults())
                .formLogin(form -> form.loginPage("/login").defaultSuccessUrl("/dashboard", true).permitAll())
                .logout(logout -> logout.logoutSuccessUrl("/login?logout").permitAll())
                .build();
    }
}

