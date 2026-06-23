package com.stockplatform.scheduler;

import com.stockplatform.service.PythonDataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Tự động fetch dữ liệu theo lịch.
 *
 * Tại sao cần scheduler?
 * - Thị trường VN đóng cửa lúc 15:00, dữ liệu cuối ngày available ~15:30
 * - Chạy lúc 18:00 mỗi ngày để đảm bảo có đủ dữ liệu
 * - ApplicationReadyEvent: fetch một lần lúc khởi động app (populate DB)
 */
@Component
public class DataScheduler {

    private static final Logger log = LoggerFactory.getLogger(DataScheduler.class);

    private final PythonDataService pythonDataService;

    @Value("${app.watchlist}")
    private String watchlistConfig;

    @Value("${app.scheduler.enabled:true}")
    private boolean schedulerEnabled;

    public DataScheduler(PythonDataService pythonDataService) {
        this.pythonDataService = pythonDataService;
    }

    /**
     * Chạy một lần khi app khởi động.
     * Delay 5 giây để Spring context ổn định trước.
     */
    @EventListener(ApplicationReadyEvent.class)
    public void onStartup() {
        if (!schedulerEnabled) return;
        log.info("App started — checking Python service...");

        if (!pythonDataService.isPythonServiceUp()) {
            log.warn("Python service not running at startup. Data fetch skipped.");
            log.warn("Start it with: uvicorn main:app --port 8000");
            return;
        }

        log.info("Python service OK. Fetching initial data...");
        fetchAll();
    }

    /**
     * Chạy lúc 18:00 mỗi ngày từ thứ 2 đến thứ 6.
     * Cron format: giây phút giờ ngày tháng ngày-tuần
     */
    @Scheduled(cron = "0 0 18 * * MON-FRI")
    public void scheduledFetch() {
        if (!schedulerEnabled) return;
        if (!pythonDataService.isPythonServiceUp()) {
            log.warn("Scheduled fetch skipped: Python service is down");
            return;
        }
        log.info("Running scheduled data fetch...");
        fetchAll();
    }

    private void fetchAll() {
        List<String> symbols = List.of(watchlistConfig.split(","));
        for (String symbol : symbols) {
            try {
                log.info("Fetching data for {}", symbol);
                pythonDataService.fetchAndSaveHistory(symbol.trim(), 90);
                pythonDataService.fetchAndSaveSignal(symbol.trim());
                Thread.sleep(500); // tránh spam API
            } catch (Exception e) {
                log.error("Error processing {}: {}", symbol, e.getMessage());
            }
        }
        log.info("Data fetch complete for {} symbols.", symbols.size());
    }
}
