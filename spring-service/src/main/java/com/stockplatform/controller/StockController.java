package com.stockplatform.controller;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import com.stockplatform.entity.StockData;
import com.stockplatform.entity.StockSignal;
import com.stockplatform.service.PythonDataService;

@Controller
@RequestMapping("/stocks")
public class StockController {

    private final PythonDataService pythonDataService;

    public StockController(PythonDataService pythonDataService) {
        this.pythonDataService = pythonDataService;
    }

    @GetMapping("/{symbol}")
    public String stockDetail(@PathVariable String symbol, Model model) {
        symbol = symbol.toUpperCase().trim();

        // ── Ghi lại lịch sử xem → cập nhật watchlist dashboard ───────────
        pythonDataService.recordWatchedStock(symbol);

        // ── Fetch data ─────────────────────────────────────────────────────
        List<StockData> history = pythonDataService.fetchAndSaveHistory(symbol, 90);
        StockSignal signal      = pythonDataService.fetchAndSaveSignal(symbol);

        // Build JSON strings cho chart
        StringBuilder datesJson   = new StringBuilder("[");
        StringBuilder closesJson  = new StringBuilder("[");
        StringBuilder volumesJson = new StringBuilder("[");

        for (int i = 0; i < history.size(); i++) {
            StockData d = history.get(i);
            if (i > 0) {
                datesJson.append(",");
                closesJson.append(",");
                volumesJson.append(",");
            }
            datesJson.append("\"").append(d.getDate()).append("\"");
            closesJson.append(d.getClose()  != null ? d.getClose()  : "null");
            volumesJson.append(d.getVolume() != null ? d.getVolume() : "null");
        }
        datesJson.append("]");
        closesJson.append("]");
        volumesJson.append("]");

        // Parse reasons
        List<String> reasons = new ArrayList<>();
        if (signal != null && signal.getReasons() != null
                && !signal.getReasons().isBlank()) {
            reasons = Arrays.asList(signal.getReasons().split("\\|"));
        }

        model.addAttribute("symbol",      symbol);
        model.addAttribute("signal",      signal);
        model.addAttribute("reasons",     reasons);
        model.addAttribute("datesJson",   datesJson.toString());
        model.addAttribute("closesJson",  closesJson.toString());
        model.addAttribute("volumesJson", volumesJson.toString());
        model.addAttribute("hasData",     !history.isEmpty());

        return "stock/detail";
    }

    @PostMapping("/{symbol}/refresh")
    public String refresh(@PathVariable String symbol, RedirectAttributes ra) {
        pythonDataService.fetchAndSaveHistory(symbol.toUpperCase(), 90);
        pythonDataService.fetchAndSaveSignal(symbol.toUpperCase());
        ra.addFlashAttribute("success",
            "Đã cập nhật dữ liệu cho " + symbol.toUpperCase());
        return "redirect:/stocks/" + symbol.toUpperCase();
    }
}