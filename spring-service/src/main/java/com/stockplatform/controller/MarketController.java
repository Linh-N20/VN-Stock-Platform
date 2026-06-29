package com.stockplatform.controller;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.client.RestTemplate;

import com.stockplatform.service.PythonDataService;

@Controller
@RequestMapping("/market")
public class MarketController {

    private static final Logger log = LoggerFactory.getLogger(MarketController.class);

    private final PythonDataService pythonDataService;
    private final RestTemplate      restTemplate;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public MarketController(PythonDataService pythonDataService,
                            RestTemplate restTemplate) {
        this.pythonDataService = pythonDataService;
        this.restTemplate      = restTemplate;
    }

    @GetMapping
    public String market(
            @RequestParam(required = false) String sector,
            @RequestParam(required = false) String signal,
            @RequestParam(defaultValue = "symbol")  String sortBy,
            @RequestParam(defaultValue = "asc")     String sortDir,
            @RequestParam(defaultValue = "10")      int limit,
            Model model) {

        List<Map<String, Object>> stocks  = new ArrayList<>();
        List<String>              sectors = new ArrayList<>();

        try {
            StringBuilder url = new StringBuilder(pythonServiceUrl + "/stocks/market?");
            url.append("sort_by=symbol&sort_dir=asc");
            url.append("&limit=").append(limit);
            if (sector != null && !sector.isBlank())
                url.append("&sector=").append(URLEncoder.encode(sector, StandardCharsets.UTF_8).replace("+", "%20"));
            if (signal != null && !signal.isBlank())
                url.append("&signal=").append(URLEncoder.encode(signal, StandardCharsets.UTF_8).replace("+", "%20"));

            log.info("Calling: {}", url);
            Map<String, Object> response = restTemplate.getForObject(url.toString(), Map.class);

            if (response != null) {
                stocks  = (List<Map<String, Object>>) response.getOrDefault("data",    new ArrayList<>());
                sectors = (List<String>)              response.getOrDefault("sectors", new ArrayList<>());
                log.info("Got {} stocks", stocks.size());
            }

            // Sort ở Java tránh lỗi kiểu Object từ JSON
            boolean reverse = "desc".equals(sortDir);
            stocks.sort((a, b) -> {
                Object va = a.get(sortBy);
                Object vb = b.get(sortBy);
                if (va == null && vb == null) return 0;
                if (va == null) return reverse ? -1 : 1;
                if (vb == null) return reverse ? 1 : -1;
                int cmp = (va instanceof Number na && vb instanceof Number nb)
                    ? Double.compare(na.doubleValue(), nb.doubleValue())
                    : va.toString().compareToIgnoreCase(vb.toString());
                return reverse ? -cmp : cmp;
            });

        } catch (Exception e) {
            log.error("Market error: {}", e.getMessage());
            model.addAttribute("error", "Lỗi: " + e.getMessage());
        }

        model.addAttribute("stocks",         stocks);
        model.addAttribute("sectors",        sectors);
        model.addAttribute("buyCount",       stocks.stream().filter(s -> "BUY".equals(s.get("signal"))).count());
        model.addAttribute("sellCount",      stocks.stream().filter(s -> "SELL".equals(s.get("signal"))).count());
        model.addAttribute("holdCount",      stocks.stream().filter(s -> "HOLD".equals(s.get("signal"))).count());
        model.addAttribute("pythonUp",       pythonDataService.isPythonServiceUp());
        model.addAttribute("currentSector",  sector);
        model.addAttribute("currentSignal",  signal);
        model.addAttribute("currentSortBy",  sortBy);
        model.addAttribute("currentSortDir", sortDir);
        model.addAttribute("currentLimit",   limit);

        return "market";
    }
}