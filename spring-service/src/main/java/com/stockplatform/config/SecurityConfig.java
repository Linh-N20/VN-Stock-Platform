package com.stockplatform.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.client.RestTemplate;

import com.stockplatform.security.OAuth2UserService;
import com.stockplatform.security.RateLimitFilter;

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
            .addFilterBefore(rateLimitFilter, UsernamePasswordAuthenticationFilter.class)

            .authorizeHttpRequests(auth -> auth
                .requestMatchers(
                    "/", "/market", "/stocks/**", "/learn/**",
                    "/search", "/login",
                    "/css/**", "/js/**", "/images/**",
                    "/h2-console/**", "/error",
                    "/api/favorites/check/**", "/api/predict/history/**", 
                    "/api/predict/accuracy/**", "api/company/**"
                ).permitAll()
                .requestMatchers("/profile", "/profile/**").authenticated()
                .requestMatchers("/api/favorites/**").authenticated()
                .anyRequest().permitAll()
            )

            .exceptionHandling(ex -> ex
                // API endpoints trả JSON 401 thay vì redirect về login page
                .authenticationEntryPoint((request, response, authException) -> {
                    String path = request.getRequestURI();
                    if (path.startsWith("/api/")) {
                        response.setStatus(401);
                        response.setContentType("application/json;charset=UTF-8");
                        response.getWriter().write("{\"error\":\"Chưa đăng nhập\",\"status\":401}");
                    } else {
                        response.sendRedirect("/login");
                    }
                })
            )

            .oauth2Login(oauth2 -> oauth2
                .loginPage("/login")
                .userInfoEndpoint(ui -> ui
                    .oidcUserService(oAuth2UserService)
                )
                .defaultSuccessUrl("/", true)
                .failureUrl("/login?error=true")
            )

            .logout(logout -> logout
                .logoutUrl("/logout")
                .logoutSuccessUrl("/")
                .deleteCookies("JSESSIONID")
                .invalidateHttpSession(true)
                .clearAuthentication(true)
                .permitAll()
            )

            .csrf(csrf -> csrf
                .ignoringRequestMatchers("/h2-console/**", "/api/**")
            )

            .headers(headers -> headers
                .frameOptions(f -> f.sameOrigin())
                .contentTypeOptions(c -> {})
                .referrerPolicy(r ->
                    r.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
                .contentSecurityPolicy(csp -> csp
                    .policyDirectives(
                        "default-src 'self'; " +
                        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " +
                        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " +
                        "font-src 'self' https://cdn.jsdelivr.net data:; " +
                        "img-src 'self' data: https://lh3.googleusercontent.com https://cdn.jsdelivr.net; " +
                        "connect-src 'self' http://localhost:8000 https://cdn.jsdelivr.net; " +
                        "frame-ancestors 'self'"
                    )
                )
            );

        return http.build();
    }
}