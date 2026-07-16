package com.stockplatform.security;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Rate Limiting — giới hạn số request mỗi IP.
 *
 * Tại sao cần rate limiting?
 * - Chặn DDoS: hacker gửi hàng nghìn request/giây để làm sập server
 * - Chặn brute force: thử mật khẩu hàng nghìn lần tự động
 * - Chặn scraping: bot lấy toàn bộ dữ liệu của mình
 * - Bảo vệ VCI API quota: mỗi user chỉ được refresh giá X lần/phút
 *
 * Thuật toán Token Bucket:
 * - Mỗi IP có một "xô" chứa N token
 * - Mỗi request tiêu 1 token
 * - Token được nạp lại M token/phút
 * - Xô hết token → trả về 429 Too Many Requests
 */
@Component
public class RateLimitFilter implements Filter {

    // Lưu bucket cho từng IP — ConcurrentHashMap để thread-safe
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest  request  = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;

        String ip = getClientIP(request);
        String path = request.getRequestURI();

        Bucket bucket = buckets.computeIfAbsent(ip, k -> createBucket(path));

        if (bucket.tryConsume(1)) {
            // Còn token → cho qua, thêm header thông tin
            response.setHeader("X-RateLimit-Remaining",
                String.valueOf(bucket.getAvailableTokens()));
            chain.doFilter(req, res);
        } else {
            // Hết token → từ chối
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setContentType("application/json");
            response.getWriter().write(
                "{\"error\":\"Too many requests. Please wait before trying again.\","
                + "\"status\":429}"
            );
        }
    }

    private Bucket createBucket(String path) {
        // Endpoint nhạy cảm hơn → limit chặt hơn
        if (path.startsWith("/login") || path.startsWith("/oauth2")) {
            // Login: 10 lần/phút
            return Bucket.builder()
                .addLimit(Bandwidth.classic(10, Refill.greedy(10, Duration.ofMinutes(1))))
                .build();
        }
        // API thường: 60 lần/phút
        return Bucket.builder()
            .addLimit(Bandwidth.classic(60, Refill.greedy(60, Duration.ofMinutes(1))))
            .build();
    }

    private String getClientIP(HttpServletRequest request) {
        // Lấy IP thật khi dùng proxy/nginx
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isEmpty()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}