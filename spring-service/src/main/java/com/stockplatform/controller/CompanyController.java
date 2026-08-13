package com.stockplatform.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@RestController
@RequestMapping("/api/company")
public class CompanyController {

    private final RestTemplate restTemplate;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public CompanyController(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @GetMapping("/profile/{symbol}")
    public ResponseEntity<?> getProfile(@PathVariable String symbol) {
        try {
            String url      = pythonServiceUrl + "/stocks/profile/" + symbol.toUpperCase();
            Map<?, ?> data  = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(data);
        } catch (org.springframework.web.client.RestClientException |
                 IllegalArgumentException e) {
            return ResponseEntity.status(503)
                .body(Map.of("error", "Không thể lấy dữ liệu: " + e.getMessage()));
        }
    }
}