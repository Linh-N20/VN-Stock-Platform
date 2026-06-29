package com.stockplatform.service;

import com.stockplatform.entity.StockData;
import com.stockplatform.entity.StockSignal;
import com.stockplatform.repository.StockDataRepository;
import com.stockplatform.repository.StockSignalRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.ResourceAccessException;

import java.time.LocalDate;
import java.util.*;

/**
 * Gọi Python FastAPI service để lấy dữ liệu và lưu vào database.
 *
 * Đây là "cầu nối" giữa Java và Python:
 * Spring Boot → HTTP → FastAPI → VNStock → dữ liệu thô
 *                 ↓
 *           lưu vào H2/MySQL
 */
@Service
public class PythonDataService {

    private static final Logger log = LoggerFactory.getLogger(PythonDataService.class);

    private final RestTemplate          restTemplate;
    private final StockDataRepository   stockDataRepo;
    private final StockSignalRepository signalRepo;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public PythonDataService(StockDataRepository stockDataRepo,
                             StockSignalRepository signalRepo,
                             RestTemplate restTemplate) {
        this.restTemplate  = restTemplate;
        this.stockDataRepo = stockDataRepo;
        this.signalRepo    = signalRepo;
    }

    /** Kiểm tra Python service có đang chạy không */
    public boolean isPythonServiceUp() {
        try {
            restTemplate.getForObject(pythonServiceUrl + "/health", Map.class);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Lấy quote hiện tại từ Python service.
     * Trả về Map thô — controller/template xử lý hiển thị.
     */
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

    /**
     * Lấy lịch sử giá và lưu vào DB nếu chưa có.
     */
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

            List<Map<String, Object>> dataList = (List<Map<String, Object>>) response.get("data");
            int saved = 0;

            for (Map<String, Object> row : dataList) {
                String dateStr = (String) row.get("date");
                if (dateStr == null) continue;

                // Chỉ lấy phần ngày nếu có timestamp
                LocalDate date = LocalDate.parse(dateStr.length() > 10 ? dateStr.substring(0, 10) : dateStr);

                if (stockDataRepo.existsBySymbolAndDate(symbol, date)) continue;

                StockData sd = new StockData(
                    symbol, date,
                    toDouble(row.get("open")),
                    toDouble(row.get("high")),
                    toDouble(row.get("low")),
                    toDouble(row.get("close")),
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

    /**
     * Lấy tín hiệu phân tích kỹ thuật từ Python và lưu vào DB.
     */
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
            List<String> reasons = (List<String>) response.getOrDefault("reasons", List.of());

            StockSignal signal = new StockSignal();
            signal.setSymbol(symbol);
            signal.setSignal((String) response.getOrDefault("signal", "HOLD"));
            signal.setScore(toInt(response.get("score")));
            signal.setCurrentPrice(toDouble(response.get("currentPrice")));
            signal.setRsi(toDouble(indicators.get("rsi")));
            signal.setMacd(toDouble(indicators.get("macd")));
            signal.setMacdSignal(toDouble(indicators.get("macdSignal")));
            signal.setMa20(toDouble(indicators.get("ma20")));
            signal.setMa50(toDouble(indicators.get("ma50")));
            signal.setBbUpper(toDouble(indicators.get("bbUpper")));
            signal.setBbLower(toDouble(indicators.get("bbLower")));
            signal.setReasons(String.join("|", reasons));

            return signalRepo.save(signal);

        } catch (ResourceAccessException e) {
            log.error("Python service unreachable when computing signal for {}", symbol);
            return getLatestSignal(symbol);
        } catch (Exception e) {
            log.error("Error computing signal for {}: {}", symbol, e.getMessage());
            return getLatestSignal(symbol);
        }
    }

    /** Lấy tín hiệu mới nhất đã lưu trong DB */
    public StockSignal getLatestSignal(String symbol) {
        return signalRepo.findTopBySymbolOrderByCalculatedAtDesc(symbol.toUpperCase())
                .orElse(null);
    }

    /** Lấy watchlist quotes */
    public List<Map<String, Object>> getWatchlist(List<String> symbols) {
        try {
            String symbolStr = String.join(",", symbols);
            String url = pythonServiceUrl + "/stocks/watchlist?symbols=" + symbolStr;
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            if (response != null && response.containsKey("watchlist")) {
                return (List<Map<String, Object>>) response.get("watchlist");
            }
        } catch (Exception e) {
            log.error("Error fetching watchlist: {}", e.getMessage());
        }
        return List.of();
    }

    /** Search */
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

    // ── Helpers ───────────────────────────────────────────────────────────────

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

    /** Trả về data rỗng khi Python service không chạy */
    private Map<String, Object> fallbackQuote(String symbol) {
        Map<String, Object> fallback = new HashMap<>();
        fallback.put("symbol", symbol);
        fallback.put("error", "Python service chưa chạy. Chạy: uvicorn main:app --port 8000");
        fallback.put("currentPrice", null);
        return fallback;
    }
}
