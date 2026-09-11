package com.stockplatform.controller;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import com.stockplatform.entity.PredictionRecord;
import com.stockplatform.entity.StockSignal;
import com.stockplatform.entity.WatchedStock;
import com.stockplatform.repository.PredictionRepository;
import com.stockplatform.repository.StockSignalRepository;
import com.stockplatform.repository.WatchedStockRepository;
import com.stockplatform.service.PythonDataService;

import jakarta.annotation.PostConstruct;

@Controller
public class DashboardController {

    private static final int MAX_WATCHLIST_SIZE = 10;

    @Value("${app.watchlist:VNM,VCB,HPG,FPT,MWG}")
    private String defaultWatchlist;

    private final StockSignalRepository signalRepo;
    private final WatchedStockRepository watchedStockRepo;
    private final PredictionRepository predictionRepo;
    private final PythonDataService pythonDataService;

    public DashboardController(
            StockSignalRepository signalRepo,
            WatchedStockRepository watchedStockRepo,
            PredictionRepository predictionRepo,
            PythonDataService pythonDataService) {

        this.signalRepo = signalRepo;
        this.watchedStockRepo = watchedStockRepo;
        this.predictionRepo = predictionRepo;
        this.pythonDataService = pythonDataService;
    }

    // =========================================================
    // KHỞI TẠO WATCHLIST MẶC ĐỊNH
    // =========================================================

    @PostConstruct
    public void initializeDefaultWatchlist() {

        List<WatchedStock> existing =
                watchedStockRepo.findRecentlyWatched();

        // -----------------------------------------------------
        // DATABASE CHƯA CÓ WATCHLIST
        // -----------------------------------------------------
        if (existing.isEmpty()) {

            List<String> defaults = Arrays.stream(defaultWatchlist.split(","))
                    .map(String::trim)
                    .map(String::toUpperCase)
                    .filter(s -> !s.isEmpty())
                    .distinct()
                    .limit(5)
                    .collect(Collectors.toList());

            LocalDateTime now = LocalDateTime.now();

            List<WatchedStock> defaultStocks = new ArrayList<>();

            for (int i = 0; i < defaults.size(); i++) {

                WatchedStock stock =
                        new WatchedStock(defaults.get(i));

                stock.setLastViewedAt(
                        now.minusSeconds(i)
                );

                // Default stock chưa được user xem
                stock.setViewCount(0);

                defaultStocks.add(stock);
            }
            watchedStockRepo.saveAll(defaultStocks);
            return;
        }

        // -----------------------------------------------------
        // DATABASE ĐANG CÓ QUÁ 10 MÃ
        // -----------------------------------------------------

        if (existing.size() > MAX_WATCHLIST_SIZE) {

            List<WatchedStock> stocksToDelete =
                    existing.subList(
                            MAX_WATCHLIST_SIZE,
                            existing.size()
                    );
            watchedStockRepo.deleteAll(stocksToDelete);
        }
    }

    // =========================================================
    // DASHBOARD
    // =========================================================

    @GetMapping("/")
    public String dashboard(Model model) {

        List<WatchedStock> recentlyWatched =
                watchedStockRepo.findRecentlyWatched()
                        .stream()
                        .limit(MAX_WATCHLIST_SIZE)
                        .collect(Collectors.toList());

        // -----------------------------------------------------
        // TẠO DANH SÁCH SYMBOL
        // -----------------------------------------------------

        List<String> symbols = recentlyWatched.stream()
                .map(WatchedStock::getSymbol)
                .map(String::toUpperCase)
                .collect(Collectors.toList());

        // -----------------------------------------------------
        // LẤY DỮ LIỆU CHO TỪNG STOCK
        // -----------------------------------------------------

        List<DashboardRow> rows = new ArrayList<>();

        for (String symbol : symbols) {

            // =================================================
            // 1. LẤY SIGNAL MỚI NHẤT
            // =================================================

            StockSignal sig =
                    signalRepo
                            .findTopBySymbolOrderByCalculatedAtDesc(symbol)
                            .orElse(null);

            if (sig == null) {

                try {
                    pythonDataService.fetchAndSaveHistory(
                            symbol,
                            90
                    );

                    sig =
                            pythonDataService.fetchAndSaveSignal(
                                    symbol
                            );

                } catch (Exception e) {}
            }

            // =================================================
            // 2. LẤY PREDICTION MỚI NHẤT
            // =================================================

            Optional<PredictionRecord> pred =
                    predictionRepo
                            .findBySymbolAndForDate(
                                    symbol,
                                    LocalDate.now()
                            )
                            .or(() ->
                                    predictionRepo
                                            .findTop10BySymbolOrderByForDateDesc(
                                                    symbol
                                            )
                                            .stream()
                                            .findFirst()
                            );

            // =================================================
            // 3. TẠO DASHBOARD ROW
            // =================================================

            DashboardRow row = new DashboardRow();

            row.setSymbol(symbol);

            // -------------------------------------------------
            // ƯU TIÊN PREDICTION RECORD
            // -------------------------------------------------

            if (pred.isPresent()) {

                PredictionRecord p = pred.get();

                row.setSignal(
                        p.getPrediction()
                );

                row.setConfidence(
                        p.getConfidence()
                );

                row.setTechnicalLabel(
                        p.getTechnicalLabel()
                );

                row.setExtendedLabel(
                        p.getExtendedLabel()
                );

                row.setMlLabel(
                        p.getMlLabel()
                );

                row.setForDate(
                        p.getForDate()
                );

                row.setPrediction(true);

            }

            // -------------------------------------------------
            // FALLBACK SANG STOCK SIGNAL
            // -------------------------------------------------

            else if (sig != null) {

                row.setSignal(
                        sig.getSignal()
                );

                row.setPrediction(false);
            }

            // =================================================
            // 4. THÔNG TIN KỸ THUẬT
            // =================================================

            if (sig != null) {

                row.setCurrentPrice(
                        sig.getCurrentPrice()
                );

                row.setRsi(
                        sig.getRsi()
                );

                row.setMacd(
                        sig.getMacd()
                );

                row.setMa20(
                        sig.getMa20()
                );

                row.setCalculatedAt(
                        sig.getCalculatedAt()
                );
            }

            rows.add(row);
        }

        // =====================================================
        // SẮP XẾP THEO THỜI GIAN XEM
        // =====================================================

        if (!recentlyWatched.isEmpty()) {

            Map<String, LocalDateTime> viewTimeMap =
                    recentlyWatched.stream()
                            .collect(Collectors.toMap(
                                    WatchedStock::getSymbol,
                                    WatchedStock::getLastViewedAt,
                                    (a, b) -> a
                            ));

            rows.sort((a, b) -> {

                LocalDateTime ta =
                        viewTimeMap.getOrDefault(
                                a.symbol,
                                LocalDateTime.MIN
                        );

                LocalDateTime tb =
                        viewTimeMap.getOrDefault(
                                b.symbol,
                                LocalDateTime.MIN
                        );

                return tb.compareTo(ta);
            });
        }

        // =====================================================
        // ĐẾM TĂNG / GIỮ NGUYÊN / GIẢM
        // =====================================================

        long buyCount =
                rows.stream()
                        .filter(r -> "TĂNG".equals(r.signal))
                        .count();

        long holdCount =
                rows.stream()
                        .filter(r -> "GIỮ NGUYÊN".equals(r.signal))
                        .count();

        long sellCount =
                rows.stream()
                        .filter(r -> "GIẢM".equals(r.signal))
                        .count();

        // =====================================================
        // WATCHLIST CHO FRONTEND
        // =====================================================

        List<String> watchlist =
                recentlyWatched.stream()
                        .map(WatchedStock::getSymbol)
                        .collect(Collectors.toList());

        // =====================================================
        // GỬI DATA SANG THYMELEAF
        // =====================================================

        model.addAttribute(
                "rows",
                rows
        );

        model.addAttribute(
                "buyCount",
                buyCount
        );

        model.addAttribute(
                "holdCount",
                holdCount
        );

        model.addAttribute(
                "sellCount",
                sellCount
        );

        model.addAttribute(
                "watchlist",
                watchlist
        );

        model.addAttribute(
                "pythonUp",
                pythonDataService.isPythonServiceUp()
        );

        return "dashboard";
    }

    // =========================================================
    // DTO CHO MỖI HÀNG TRONG DASHBOARD
    // =========================================================

    public static class DashboardRow {

        private String symbol;

        private String signal;

        private Double confidence;

        private String technicalLabel;

        private String extendedLabel;

        private String mlLabel;

        private LocalDate forDate;

        private boolean predictionSource;

        private Double currentPrice;

        private Double rsi;

        private Double macd;

        private Double ma20;

        private LocalDateTime calculatedAt;

        // =====================================================
        // GETTERS
        // =====================================================

        public String getSymbol() {
            return symbol;
        }

        public String getSignal() {
            return signal;
        }

        public Double getConfidence() {
            return confidence;
        }

        public String getTechnicalLabel() {
            return technicalLabel;
        }

        public String getExtendedLabel() {
            return extendedLabel;
        }

        public String getMlLabel() {
            return mlLabel;
        }

        public LocalDate getForDate() {
            return forDate;
        }

        public boolean isPredictionSource() {
            return predictionSource;
        }

        public Double getCurrentPrice() {
            return currentPrice;
        }

        public Double getRsi() {
            return rsi;
        }

        public Double getMacd() {
            return macd;
        }

        public Double getMa20() {
            return ma20;
        }

        public LocalDateTime getCalculatedAt() {
            return calculatedAt;
        }

        // =====================================================
        // SETTERS
        // =====================================================

        public void setSymbol(String v) {
            this.symbol = v;
        }

        public void setSignal(String v) {
            this.signal = v;
        }

        public void setConfidence(Double v) {
            this.confidence = v;
        }

        public void setTechnicalLabel(String v) {
            this.technicalLabel = v;
        }

        public void setExtendedLabel(String v) {
            this.extendedLabel = v;
        }

        public void setMlLabel(String v) {
            this.mlLabel = v;
        }

        public void setForDate(LocalDate v) {
            this.forDate = v;
        }

        public void setPrediction(boolean v) {
            this.predictionSource = v;
        }

        public void setCurrentPrice(Double v) {
            this.currentPrice = v;
        }

        public void setRsi(Double v) {
            this.rsi = v;
        }

        public void setMacd(Double v) {
            this.macd = v;
        }

        public void setMa20(Double v) {
            this.ma20 = v;
        }

        public void setCalculatedAt(LocalDateTime v) {
            this.calculatedAt = v;
        }

        // =====================================================
        // UI HELPERS
        // =====================================================

        public String getSignalColor() {

            return switch (signal != null ? signal : "") {

                case "TĂNG" ->
                        "success";

                case "GIẢM" ->
                        "danger";

                case "GIỮ NGUYÊN" ->
                        "warning";

                default ->
                        "secondary";
            };
        }

        public String getSignalIcon() {

            return switch (signal != null ? signal : "") {

                case "TĂNG" ->
                        "bi-graph-up-arrow";

                case "GIẢM" ->
                        "bi-graph-down-arrow";
                default ->
                        "bi-dash";
            };
        }
    }
}