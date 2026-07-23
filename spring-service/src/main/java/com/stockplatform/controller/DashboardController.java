package com.stockplatform.controller;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import com.stockplatform.entity.StockSignal;
import com.stockplatform.entity.WatchedStock;
import com.stockplatform.repository.StockSignalRepository;
import com.stockplatform.repository.WatchedStockRepository;
import com.stockplatform.service.PythonDataService;

@Controller
public class DashboardController {

    private final StockSignalRepository  signalRepo;
    private final WatchedStockRepository watchedStockRepo;
    private final PythonDataService      pythonDataService;

    @Value("${app.watchlist:VNM,VCB,HPG,FPT,MWG,TCB,VIC,ACB}")
    private String defaultWatchlist;

    public DashboardController(StockSignalRepository signalRepo,
                               WatchedStockRepository watchedStockRepo,
                               PythonDataService pythonDataService) {
        this.signalRepo       = signalRepo;
        this.watchedStockRepo = watchedStockRepo;
        this.pythonDataService = pythonDataService;
    }

    @GetMapping("/")
    public String dashboard(Model model) {

        // ── Lấy danh sách đã xem gần nhất từ DB ──────────────────────────────
        List<WatchedStock> recentlyWatched = watchedStockRepo.findRecentlyWatched();

        // ── Lấy tín hiệu của các cổ phiếu đã xem ─────────────────────────────
        List<StockSignal> signals;
        if (recentlyWatched.isEmpty()) {
            // Lần đầu vào — chưa xem gì → dùng default watchlist
            List<String> defaultSymbols = Arrays.stream(defaultWatchlist.split(","))
                .map(String::trim)
                .collect(Collectors.toList());
            signals = signalRepo.findBySymbolInOrderByCalculatedAtDesc(defaultSymbols);
        } else {
            // Đã có lịch sử → lấy tín hiệu của các cổ phiếu đã xem
            List<String> watchedSymbols = recentlyWatched.stream()
                .map(WatchedStock::getSymbol)
                .collect(Collectors.toList());
            signals = signalRepo.findBySymbolInOrderByCalculatedAtDesc(watchedSymbols);

            // Sort theo thứ tự lastViewedAt (mới xem nhất lên đầu)
            Map<String, LocalDateTime> viewTimeMap = recentlyWatched.stream()
                .collect(Collectors.toMap(
                    WatchedStock::getSymbol,
                    WatchedStock::getLastViewedAt
                ));
            signals.sort((a, b) -> {
                java.time.LocalDateTime ta = viewTimeMap.getOrDefault(a.getSymbol(), java.time.LocalDateTime.MIN);
                java.time.LocalDateTime tb = viewTimeMap.getOrDefault(b.getSymbol(), java.time.LocalDateTime.MIN);
                return tb.compareTo(ta); // mới nhất lên đầu
            });
        }

        // ── Thống kê tín hiệu ─────────────────────────────────────────────────
        long buyCount  = signals.stream().filter(s -> "BUY".equals(s.getSignal())).count();
        long holdCount = signals.stream().filter(s -> "HOLD".equals(s.getSignal())).count();
        long sellCount = signals.stream().filter(s -> "SELL".equals(s.getSignal())).count();

        // ── Quick access: gộp default + đã xem, bỏ duplicate ─────────────────
        Set<String> quickSet = new LinkedHashSet<>(
            Arrays.stream(defaultWatchlist.split(","))
                .map(String::trim)
                .collect(Collectors.toList())
        );
        recentlyWatched.stream()
            .map(WatchedStock::getSymbol)
            .forEach(quickSet::add);

        model.addAttribute("signals",   signals);
        model.addAttribute("buyCount",  buyCount);
        model.addAttribute("holdCount", holdCount);
        model.addAttribute("sellCount", sellCount);
        model.addAttribute("watchlist", new ArrayList<>(quickSet));
        model.addAttribute("pythonUp",  pythonDataService.isPythonServiceUp());

        return "dashboard";
    }
}