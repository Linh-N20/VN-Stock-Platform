package com.stockplatform.controller;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.client.RestTemplate;

@Controller
public class SearchController {

    private final RestTemplate restTemplate;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public SearchController(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @GetMapping("/search")
    public String search(@RequestParam(required = false) String q, Model model) {
        // Nếu query trống
        if (q == null || q.isBlank()) {
            return "redirect:/";
        }

        q = q.trim().toUpperCase();

        // Nếu query là mã cổ phiếu hợp lệ (1-10 ký tự chữ cái) → chuyển thẳng đến trang detail
        if (q.matches("[A-Z0-9]{1,10}")) {
            return "redirect:/stocks/" + q;
        }

        // Tìm kiếm qua Python service
        try {
            String url = pythonServiceUrl + "/stocks/search?q=" + q;
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);

            if (response != null) {
                List<Map<String, Object>> results =
                    (List<Map<String, Object>>) response.getOrDefault("results", List.of());

                // Nếu chỉ có 1 kết quả → chuyển thẳng đến trang detail
                if (results.size() == 1) {
                    String symbol = (String) results.get(0).get("symbol");
                    return "redirect:/stocks/" + symbol;
                }

                model.addAttribute("results", results);
                model.addAttribute("query",   q);
            }
        } catch (Exception e) {
            model.addAttribute("error", "Không thể tìm kiếm. Python service chưa chạy.");
        }

        return "search";
    }
}