package com.stockplatform.controller;

import com.stockplatform.entity.StockSignal;
import com.stockplatform.repository.StockSignalRepository;
import com.stockplatform.service.PythonDataService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.*;

@Controller
public class DashboardController {

    private final PythonDataService     pythonDataService;
    private final StockSignalRepository signalRepo;

    @Value("${app.watchlist}")
    private String watchlistConfig;

    public DashboardController(PythonDataService pythonDataService,
                               StockSignalRepository signalRepo) {
        this.pythonDataService = pythonDataService;
        this.signalRepo        = signalRepo;
    }

    @GetMapping("/")
    public String dashboard(Model model) {
        List<String> watchlist = List.of(watchlistConfig.split(","));

        // Tín hiệu mới nhất cho từng cổ phiếu trong watchlist
        List<StockSignal> signals = new ArrayList<>();
        for (String symbol : watchlist) {
            StockSignal sig = pythonDataService.getLatestSignal(symbol.trim());
            if (sig != null) signals.add(sig);
        }

        // Thống kê nhanh
        long buyCount  = signals.stream().filter(s -> "BUY".equals(s.getSignal())).count();
        long sellCount = signals.stream().filter(s -> "SELL".equals(s.getSignal())).count();
        long holdCount = signals.stream().filter(s -> "HOLD".equals(s.getSignal())).count();

        model.addAttribute("signals",       signals);
        model.addAttribute("watchlist",     watchlist);
        model.addAttribute("buyCount",      buyCount);
        model.addAttribute("sellCount",     sellCount);
        model.addAttribute("holdCount",     holdCount);
        model.addAttribute("pythonUp",      pythonDataService.isPythonServiceUp());

        return "dashboard";
    }

    @GetMapping("/search")
    public String search(@RequestParam String q, Model model) {
        List<Map<String, Object>> results = pythonDataService.search(q);
        model.addAttribute("query",   q);
        model.addAttribute("results", results);
        return "search";
    }
}
