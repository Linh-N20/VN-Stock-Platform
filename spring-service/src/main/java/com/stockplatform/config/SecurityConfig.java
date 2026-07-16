package com.stockplatform.config;

import com.stockplatform.security.OAuth2UserService;
import com.stockplatform.security.RateLimitFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.client.RestTemplate;

/**
 * Cấu hình bảo mật trung tâm của ứng dụng.
 *
 * Các quyết định thiết kế:
 * 1. OAuth2 Only — không có username/password tự quản lý
 * 2. Public routes — trang chủ, học chứng khoán ai cũng xem được
 * 3. Protected routes — chỉ user đăng nhập mới refresh/xem portfolio
 * 4. Security headers — chặn XSS, clickjacking, MIME sniffing
 * 5. Rate limiting — chặn DDoS và brute force
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final OAuth2UserService oAuth2UserService;
    private final RateLimitFilter   rateLimitFilter;

    public SecurityConfig(OAuth2UserService oAuth2UserService,
                          RateLimitFilter rateLimitFilter) {
        this.oAuth2UserService = oAuth2UserService;
        this.rateLimitFilter   = rateLimitFilter;
    }

    @Bean
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(120_000);
        return new RestTemplate(factory);
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            // ── Rate limiting: chạy trước mọi filter khác ─────────────────
            .addFilterBefore(rateLimitFilter, UsernamePasswordAuthenticationFilter.class)

            // ── Phân quyền truy cập ────────────────────────────────────────
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(
                    "/",
                    "/market",
                    "/stocks/**",
                    "/learn/**",
                    "/search",
                    "/login",
                    "/css/**", "/js/**", "/images/**",
                    "/h2-console/**",
                    "/error"
                ).permitAll()
                .requestMatchers("/profile", "/profile/**").authenticated()
                .anyRequest().permitAll()
            )

            // ── OAuth2 Login (Google) ──────────────────────────────────────
            .oauth2Login(oauth2 -> oauth2
                .loginPage("/login")                     // trang login tự tạo (đẹp hơn default)
                .userInfoEndpoint(ui -> ui
                    .userService(oAuth2UserService)      // class xử lý sau khi Google xác thực
                )
                .defaultSuccessUrl("/", true)            // sau login → về trang chủ
                .failureUrl("/login?error=true")         // login thất bại → báo lỗi
            )

            // ── Logout ────────────────────────────────────────────────────
            .logout(logout -> logout
                .logoutUrl("/logout")
                .logoutSuccessUrl("/")
                .deleteCookies("JSESSIONID")
                .invalidateHttpSession(true)
                .clearAuthentication(true)
                .permitAll()
            )

            // ── CSRF Protection ───────────────────────────────────────────
            // Bật CSRF cho form POST (chặn Cross-Site Request Forgery)
            // H2 console cần disable CSRF và frameOptions nên tạm thời disable
            // TODO: bật lại khi bỏ H2 console (production)
            .csrf(csrf -> csrf
                .ignoringRequestMatchers("/h2-console/**")
            )

            // ── Security Headers ──────────────────────────────────────────
            // Các header này chặn nhiều loại tấn công phổ biến
            .headers(headers -> headers
                // Chặn clickjacking: không cho nhúng site trong iframe
                .frameOptions(f -> f.sameOrigin())  // cho phép h2-console (same origin)
                // Chặn MIME sniffing: browser không đoán content type
                .contentTypeOptions(c -> {})
                // Buộc HTTPS (chỉ bật khi production có SSL)
                // .httpStrictTransportSecurity(hsts -> hsts.maxAgeInSeconds(31536000))
                // Referrer policy: không leak URL khi click link ngoài
                .referrerPolicy(r ->
                    r.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
                // Content Security Policy: chỉ load resource từ nguồn tin cậy
                .contentSecurityPolicy(csp -> csp
                    .policyDirectives(
                        "default-src 'self'; " +
                        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " +
                        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " +
                        "font-src 'self' https://cdn.jsdelivr.net data:; " +
                        "img-src 'self' data: https://lh3.googleusercontent.com https://cdn.jsdelivr.net; " +
                        "connect-src 'self' http://localhost:8000; " +
                        "frame-ancestors 'self'"
                    )
                )
            );

        return http.build();
    }
}