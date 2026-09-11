package com.stockplatform.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@Controller
public class CompanyController {

    private final RestTemplate restTemplate;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public CompanyController(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /** Trang company profile */
    @GetMapping("/stocks/{symbol}/profile")
    public String companyProfile(@PathVariable String symbol, Model model) {
        model.addAttribute("symbol", symbol.toUpperCase());
        return "stock/company_profile_page";
    }

    /** Proxy company profile từ Python */
    @GetMapping("/api/company/profile/{symbol}")
    @ResponseBody
    public ResponseEntity<?> getProfile(@PathVariable String symbol) {
        try {
            String url  = pythonServiceUrl + "/stocks/profile/" + symbol.toUpperCase();
            Map<?,?> data = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(data);
        } catch (org.springframework.web.client.RestClientException |
                 IllegalArgumentException e) {
            return ResponseEntity.status(503)
                .body(Map.of("error", "Không thể lấy dữ liệu: " + e.getMessage()));
        }
    }

    /** Proxy indicators từ Python — dùng cho prediction card */
    @GetMapping("/api/company/indicators/{symbol}")
    @ResponseBody
    public ResponseEntity<?> getIndicators(@PathVariable String symbol) {
        try {
            String url  = pythonServiceUrl + "/stocks/indicators/" + symbol.toUpperCase();
            Map<?,?> data = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(data);
        } catch (org.springframework.web.client.RestClientException |
                 IllegalArgumentException e) {
            return ResponseEntity.status(503)
                .body(Map.of("error", "Không thể lấy indicators: " + e.getMessage()));
        }
    }
}