package com.stockplatform.scheduler;

import java.util.Arrays;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.stockplatform.service.PythonDataService;

@Component
public class DataScheduler {

    private static final Logger log = LoggerFactory.getLogger(DataScheduler.class);

    private final PythonDataService pythonDataService;

    @Value("${app.watchlist:VNM,VCB,HPG,FPT,MWG,TCB,VIC,ACB}")
    private String defaultWatchlist;

    @Value("${app.scheduler.enabled:true}")
    private boolean schedulerEnabled;

    public DataScheduler(PythonDataService pythonDataService) {
        this.pythonDataService = pythonDataService;
    }

    /**
     * Fetch data cho default watchlist khi app khởi động xong.
     * Chạy async để không block startup.
     */
    @Async
    @EventListener(ApplicationReadyEvent.class)
    public void fetchOnStartup() {
        if (!schedulerEnabled) return;

        // Chờ Python service sẵn sàng
        boolean pythonUp = false;
        for (int i = 0; i < 10; i++) {
            if (pythonDataService.isPythonServiceUp()) {
                pythonUp = true;
                break;
            }
            log.info("Waiting for Python service... ({}/10)", i + 1);
            try { Thread.sleep(3000); } catch (InterruptedException e) { return; }
        }

        if (!pythonUp) {
            log.warn("Python service not available at startup. Data will be fetched on first visit.");
            return;
        }

        log.info("Python service is UP. Fetching default watchlist data...");
        List<String> symbols = Arrays.stream(defaultWatchlist.split(","))
            .map(String::trim).toList();

        for (String symbol : symbols) {
            try {
                pythonDataService.fetchAndSaveHistory(symbol, 90);
                pythonDataService.fetchAndSaveSignal(symbol);
                log.info("Loaded: {}", symbol);
                Thread.sleep(2000); // rate limit
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception e) {
                log.warn("Failed to load {}: {}", symbol, e.getMessage());
            }
        }
        log.info("Startup data fetch complete.");
    }

    /**
     * Refresh signal mỗi 18:00 T2-T6 (sau khi thị trường đóng cửa).
     */
    @Scheduled(cron = "0 0 18 * * MON-FRI")
    public void refreshDailySignals() {
        if (!schedulerEnabled) return;
        if (!pythonDataService.isPythonServiceUp()) return;

        log.info("=== [Scheduler] Daily signal refresh ===");
        List<String> symbols = Arrays.stream(defaultWatchlist.split(","))
            .map(String::trim).toList();

        for (String symbol : symbols) {
            try {
                pythonDataService.fetchAndSaveHistory(symbol, 90);
                pythonDataService.fetchAndSaveSignal(symbol);
                Thread.sleep(3000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception e) {
                log.warn("Refresh failed for {}: {}", symbol, e.getMessage());
            }
        }
        log.info("Daily refresh complete.");
    }
}