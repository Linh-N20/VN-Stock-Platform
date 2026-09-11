package com.stockplatform.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import com.stockplatform.entity.StockData;
import com.stockplatform.entity.StockSignal;
import com.stockplatform.entity.WatchedStock;
import com.stockplatform.repository.StockDataRepository;
import com.stockplatform.repository.StockSignalRepository;
import com.stockplatform.repository.WatchedStockRepository;

@Service
public class PythonDataService {

    private static final Logger log = LoggerFactory.getLogger(PythonDataService.class);

    private final RestTemplate           restTemplate;
    private final StockDataRepository    stockDataRepo;
    private final StockSignalRepository  signalRepo;
    private final WatchedStockRepository watchedStockRepo;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public PythonDataService(StockDataRepository stockDataRepo,
                             StockSignalRepository signalRepo,
                             WatchedStockRepository watchedStockRepo,
                             RestTemplate restTemplate) {
        this.restTemplate     = restTemplate;
        this.stockDataRepo    = stockDataRepo;
        this.signalRepo       = signalRepo;
        this.watchedStockRepo = watchedStockRepo;
    }

    public boolean isPythonServiceUp() {
        try {
            restTemplate.getForObject(pythonServiceUrl + "/health", Map.class);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public Map<String, Object> getQuote(String symbol) {
        try {
            String url = pythonServiceUrl + "/stocks/quote/" + symbol.toUpperCase();
            return restTemplate.getForObject(url, Map.class);
        } catch (ResourceAccessException e) {
            log.error("Python service unreachable: {}", e.getMessage());
            return fallbackQuote(symbol);
        } catch (Exception e) {
            log.error("Error fetching quote for {}: {}", symbol, e.getMessage());
            return fallbackQuote(symbol);
        }
    }

    @Transactional
    public List<StockData> fetchAndSaveHistory(String symbol, int days) {
        symbol = symbol.toUpperCase();
        log.info("Fetching {}d history for {}", days, symbol);

        try {
            String url = pythonServiceUrl + "/stocks/history/" + symbol + "?days=" + days;
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);

            if (response == null || !response.containsKey("data")) {
                return stockDataRepo.findBySymbolOrderByDateAsc(symbol);
            }

            List<Map<String, Object>> dataList =
                (List<Map<String, Object>>) response.get("data");
            int saved = 0;

            for (Map<String, Object> row : dataList) {
                String dateStr = (String) row.get("date");
                if (dateStr == null) continue;

                LocalDate date = LocalDate.parse(
                    dateStr.length() > 10 ? dateStr.substring(0, 10) : dateStr
                );
                if (stockDataRepo.existsBySymbolAndDate(symbol, date)) continue;

                StockData sd = new StockData(
                    symbol, date,
                    toDouble(row.get("open")), toDouble(row.get("high")),
                    toDouble(row.get("low")),  toDouble(row.get("close")),
                    toDouble(row.get("volume"))
                );
                stockDataRepo.save(sd);
                saved++;
            }
            log.info("Saved {} new records for {}", saved, symbol);

        } catch (ResourceAccessException e) {
            log.error("Python service unreachable when fetching history for {}", symbol);
        } catch (Exception e) {
            log.error("Error fetching history for {}: {}", symbol, e.getMessage());
        }

        return stockDataRepo.findBySymbolAndDateAfter(
            symbol, LocalDate.now().minusDays(days)
        );
    }

    @Transactional
    public StockSignal fetchAndSaveSignal(String symbol) {
        symbol = symbol.toUpperCase();
        log.info("Computing signal for {}", symbol);

        try {
            String url = pythonServiceUrl + "/stocks/indicators/" + symbol;
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);

            if (response == null) return getLatestSignal(symbol);

            Map<String, Object> indicators =
                (Map<String, Object>) response.getOrDefault("indicators", Map.of());

            // ── Fix: reasons có thể là String hoặc List ───────────────────
            String reasonsStr = "";
            Object reasonsRaw = response.get("reasons");
            if (reasonsRaw instanceof List<?> list) {
                reasonsStr = String.join("|", list.stream()
                    .map(Object::toString).toList());
            } else if (reasonsRaw instanceof String s) {
                reasonsStr = s;
            }

            StockSignal signal = new StockSignal();
            signal.setSymbol(symbol);
            // ── Fix: signal label mới TĂNG/GIẢM/GIỮ NGUYÊN ──────────────
            String rawSignal = (String) response.getOrDefault("signal", "GIỮ NGUYÊN");
            signal.setSignal(rawSignal);
            signal.setScore(toInt(response.get("score")));
            signal.setCurrentPrice(toDouble(response.get("currentPrice")));
            signal.setRsi(toDouble(indicators.get("rsi")));
            signal.setMacd(toDouble(indicators.get("macd")));
            signal.setMacdSignal(toDouble(indicators.get("macdSignal")));
            signal.setMa20(toDouble(indicators.get("ma20")));
            signal.setMa50(toDouble(indicators.get("ma50")));
            signal.setBbUpper(toDouble(indicators.get("bbUpper")));
            signal.setBbLower(toDouble(indicators.get("bbLower")));
            signal.setReasons(reasonsStr);

            return signalRepo.save(signal);

        } catch (ResourceAccessException e) {
            log.error("Python service unreachable when computing signal for {}", symbol);
            return getLatestSignal(symbol);
        } catch (Exception e) {
            log.error("Error computing signal for {}: {}", symbol, e.getMessage());
            return getLatestSignal(symbol);
        }
    }

    /**
     * Lưu cổ phiếu vào lịch sử xem — gọi khi user vào trang detail.
     * Nếu đã có → cập nhật lastViewedAt và tăng viewCount.
     */
    @Transactional
    public void recordWatchedStock(String symbol) {
        symbol = symbol.toUpperCase().trim();
        String finalSymbol = symbol;
        WatchedStock watched = watchedStockRepo.findBySymbol(symbol)
            .orElse(new WatchedStock(finalSymbol));
        watched.setLastViewedAt(LocalDateTime.now());
        watched.setViewCount(watched.getViewCount() + 1);
        watchedStockRepo.save(watched);
        log.debug("Recorded watched stock: {}", symbol);
    }

    public StockSignal getLatestSignal(String symbol) {
        return signalRepo.findTopBySymbolOrderByCalculatedAtDesc(symbol.toUpperCase())
            .orElse(null);
    }

    public List<Map<String, Object>> getWatchlist(List<String> symbols) {
        try {
            String url = pythonServiceUrl + "/stocks/watchlist?symbols=" +
                String.join(",", symbols);
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            if (response != null && response.containsKey("watchlist")) {
                return (List<Map<String, Object>>) response.get("watchlist");
            }
        } catch (Exception e) {
            log.error("Error fetching watchlist: {}", e.getMessage());
        }
        return List.of();
    }

    public List<Map<String, Object>> search(String query) {
        try {
            String url = pythonServiceUrl + "/stocks/search?q=" + query;
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            if (response != null && response.containsKey("results")) {
                return (List<Map<String, Object>>) response.get("results");
            }
        } catch (Exception e) {
            log.error("Error searching: {}", e.getMessage());
        }
        return List.of();
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private Double toDouble(Object val) {
        if (val == null) return null;
        try { return ((Number) val).doubleValue(); }
        catch (Exception e) { return null; }
    }

    private Integer toInt(Object val) {
        if (val == null) return 0;
        try { return ((Number) val).intValue(); }
        catch (Exception e) { return 0; }
    }

    private Map<String, Object> fallbackQuote(String symbol) {
        Map<String, Object> fallback = new HashMap<>();
        fallback.put("symbol", symbol);
        fallback.put("error", "Python service chưa chạy");
        fallback.put("currentPrice", null);
        return fallback;
    }
}