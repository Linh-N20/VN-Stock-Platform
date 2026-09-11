package com.stockplatform.scheduler;

import com.stockplatform.repository.WatchedStockRepository;
import com.stockplatform.service.PredictionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Component
public class PredictionScheduler {

    private static final Logger log = LoggerFactory.getLogger(PredictionScheduler.class);

    private final PredictionService      predictionService;
    private final WatchedStockRepository watchedStockRepo;

    @Value("${app.watchlist:VNM,VCB,HPG,FPT,MWG,TCB,VIC,ACB}")
    private String defaultWatchlist;

    public PredictionScheduler(PredictionService predictionService,
                               WatchedStockRepository watchedStockRepo) {
        this.predictionService = predictionService;
        this.watchedStockRepo  = watchedStockRepo;
    }

    /**
     * Cuối phiên 14:45 T2–T6: tạo dự đoán cho tất cả mã trong watchlist.
     */
    @Scheduled(cron = "0 45 14 * * MON-FRI")
    public void createDailyPredictions() {
        log.info("=== [Scheduler] Tạo dự đoán cuối phiên ===");

        // Gộp default watchlist + recently watched
        List<String> watched = watchedStockRepo.findRecentlyWatched()
            .stream().map(w -> w.getSymbol()).collect(Collectors.toList());

        List<String> defaults = Arrays.asList(defaultWatchlist.split(","));

        List<String> allSymbols = Stream.concat(defaults.stream(), watched.stream())
            .map(String::trim)
            .distinct()
            .collect(Collectors.toList());

        log.info("Tạo dự đoán cho {} mã: {}", allSymbols.size(), allSymbols);

        int success = 0;
        for (String symbol : allSymbols) {
            try {
                var rec = predictionService.createPrediction(symbol);
                if (rec != null) success++;
                Thread.sleep(2000); // rate limit
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                log.warn("Failed prediction for {}: {}", symbol, e.getMessage());
            }
        }
        log.info("Tạo dự đoán xong: {}/{}", success, allSymbols.size());
    }

    /**
     * Sáng sớm 9:00 T2–T6: đối chiếu kết quả thực tế của ngày hôm qua.
     */
    @Scheduled(cron = "0 0 9 * * MON-FRI")
    public void verifyYesterdayPredictions() {
        log.info("=== [Scheduler] Đối chiếu kết quả dự đoán ===");
        int verified = predictionService.verifyPredictions();
        log.info("Đã đối chiếu {} dự đoán", verified);
    }
}
