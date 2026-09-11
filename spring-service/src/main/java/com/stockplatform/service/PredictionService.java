package com.stockplatform.service;

import com.stockplatform.entity.PredictionRecord;
import com.stockplatform.repository.PredictionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class PredictionService {

    private static final Logger log = LoggerFactory.getLogger(PredictionService.class);

    private final PredictionRepository predictionRepo;
    private final RestTemplate         restTemplate;

    @Value("${app.python-service.url}")
    private String pythonServiceUrl;

    public PredictionService(PredictionRepository predictionRepo,
                             RestTemplate restTemplate) {
        this.predictionRepo = predictionRepo;
        this.restTemplate   = restTemplate;
    }

    /**
     * Tạo dự đoán cho 1 mã cổ phiếu, lưu vào DB.
     * Nếu đã có dự đoán cho ngày này → bỏ qua.
     */
    @Transactional
    public PredictionRecord createPrediction(String symbol) {
        symbol = symbol.toUpperCase().trim();
        LocalDate tomorrow = LocalDate.now().plusDays(1);

        // Đã có dự đoán cho ngày mai → bỏ qua
        if (predictionRepo.findBySymbolAndForDate(symbol, tomorrow).isPresent()) {
            log.info("Prediction already exists for {} on {}", symbol, tomorrow);
            return predictionRepo.findBySymbolAndForDate(symbol, tomorrow).get();
        }

        try {
            String url = pythonServiceUrl + "/stocks/predict/" + symbol;
            Map<?, ?> data = restTemplate.getForObject(url, Map.class);

            if (data == null || data.containsKey("detail")) {
                log.warn("No prediction data for {}", symbol);
                return null;
            }

            PredictionRecord record = new PredictionRecord();
            record.setSymbol(symbol);
            record.setForDate(tomorrow);
            record.setPrediction((String) data.get("prediction"));
            record.setConfidence(((Number) data.get("confidence")).doubleValue());
            record.setPredictedAt(LocalDateTime.now());

            // Lưu kết quả từng model
            Map<?, ?> models = (Map<?, ?>) data.get("models");
            if (models != null) {
                Map<?, ?> tech = (Map<?, ?>) models.get("technical");
                Map<?, ?> ext  = (Map<?, ?>) models.get("extended");
                Map<?, ?> ml   = (Map<?, ?>) models.get("ml");
                if (tech != null) record.setTechnicalLabel((String) tech.get("label"));
                if (ext  != null) record.setExtendedLabel((String) ext.get("label"));
                if (ml   != null) record.setMlLabel((String) ml.get("label"));
            }

            return predictionRepo.save(record);

        } catch (Exception e) {
            log.error("Failed to create prediction for {}: {}", symbol, e.getMessage());
            return null;
        }
    }

    /**
     * Đối chiếu kết quả thực tế cho các dự đoán chưa verified.
     * Gọi mỗi buổi sáng sau khi có giá đóng cửa ngày hôm qua.
     */
    @Transactional
    public int verifyPredictions() {
        List<PredictionRecord> pending =
            predictionRepo.findByActualDirectionIsNullAndForDateBefore(LocalDate.now());

        int verified = 0;
        for (PredictionRecord rec : pending) {
            try {
                // Lấy lịch sử giá để tính thay đổi thực tế
                String url = pythonServiceUrl + "/stocks/history/" + rec.getSymbol() + "?days=5";
                Map<?, ?> data = restTemplate.getForObject(url, Map.class);

                if (data == null) continue;

                List<?> history = (List<?>) data.get("history");
                if (history == null || history.size() < 2) continue;

                // Tìm giá ngày forDate và ngày trước đó
                Double priceOn    = null;
                Double priceBefore = null;

                for (Object entry : history) {
                    Map<?, ?> row = (Map<?, ?>) entry;
                    String date   = (String) row.get("date");
                    if (date == null) continue;

                    LocalDate d = LocalDate.parse(date);
                    if (d.equals(rec.getForDate())) {
                        priceOn = ((Number) row.get("close")).doubleValue();
                    } else if (d.equals(rec.getForDate().minusDays(1)) ||
                               d.equals(rec.getForDate().minusDays(2)) ||
                               d.equals(rec.getForDate().minusDays(3))) {
                        if (priceBefore == null)
                            priceBefore = ((Number) row.get("close")).doubleValue();
                    }
                }

                if (priceOn == null || priceBefore == null) continue;

                double changePct = (priceOn - priceBefore) / priceBefore * 100;
                String actual;
                if      (changePct > 0.5)  actual = "TĂNG";
                else if (changePct < -0.5) actual = "GIẢM";
                else                       actual = "GIỮ NGUYÊN";

                rec.setActualDirection(actual);
                rec.setActualChangePct(Math.round(changePct * 100.0) / 100.0);
                rec.setIsCorrect(actual.equals(rec.getPrediction()));
                rec.setVerifiedAt(LocalDateTime.now());
                predictionRepo.save(rec);
                verified++;

            } catch (Exception e) {
                log.warn("Failed to verify prediction for {} on {}: {}",
                    rec.getSymbol(), rec.getForDate(), e.getMessage());
            }
        }

        log.info("Verified {} predictions", verified);
        return verified;
    }

    public List<PredictionRecord> getHistory(String symbol) {
        return predictionRepo.findTop10BySymbolOrderByForDateDesc(symbol.toUpperCase());
    }

    public Map<String, Object> getAccuracy(String symbol) {
        Object[] stats = predictionRepo.getAccuracyStats(symbol.toUpperCase());
        long total   = stats[0] != null ? ((Number) stats[0]).longValue() : 0;
        long correct = stats[1] != null ? ((Number) stats[1]).longValue() : 0;
        double pct   = total > 0 ? (double) correct / total * 100 : 0;
        return Map.of("symbol", symbol, "total", total,
                      "correct", correct, "accuracy", Math.round(pct * 10) / 10.0);
    }

    public Map<String, Object> getOverallAccuracy() {
        Object[] stats = predictionRepo.getOverallAccuracyStats();
        long total   = stats[0] != null ? ((Number) stats[0]).longValue() : 0;
        long correct = stats[1] != null ? ((Number) stats[1]).longValue() : 0;
        double pct   = total > 0 ? (double) correct / total * 100 : 0;
        return Map.of("total", total, "correct", correct,
                      "accuracy", Math.round(pct * 10) / 10.0);
    }
}
