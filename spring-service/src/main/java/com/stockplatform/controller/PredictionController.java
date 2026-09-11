package com.stockplatform.controller;

import com.stockplatform.entity.PredictionRecord;
import com.stockplatform.service.PredictionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/predict")
public class PredictionController {

    private final PredictionService predictionService;

    public PredictionController(PredictionService predictionService) {
        this.predictionService = predictionService;
    }

    /** Tạo dự đoán cho 1 mã, trả về kết quả ngay */
    @PostMapping("/{symbol}")
    public ResponseEntity<?> predict(@PathVariable String symbol) {
        PredictionRecord rec = predictionService.createPrediction(symbol);
        if (rec == null) {
            return ResponseEntity.status(503)
                .body(Map.of("error", "Không thể tạo dự đoán cho " + symbol));
        }
        return ResponseEntity.ok(Map.of(
            "symbol",        rec.getSymbol(),
            "prediction",    rec.getPrediction(),
            "confidence",    rec.getConfidence(),
            "confidencePct", Math.round(rec.getConfidence() * 1000) / 10.0,
            "forDate",       rec.getForDate().toString(),
            "models", Map.of(
                "technical", rec.getTechnicalLabel() != null ? rec.getTechnicalLabel() : "—",
                "extended",  rec.getExtendedLabel()  != null ? rec.getExtendedLabel()  : "—",
                "ml",        rec.getMlLabel()         != null ? rec.getMlLabel()         : "—"
            ),
            "predictedAt", rec.getPredictedAt().toString()
        ));
    }

    /** Lấy lịch sử dự đoán của 1 mã */
    @GetMapping("/history/{symbol}")
    public ResponseEntity<?> history(@PathVariable String symbol) {
        List<PredictionRecord> list = predictionService.getHistory(symbol);
        return ResponseEntity.ok(Map.of("symbol", symbol, "history", list));
    }

    /** Accuracy của 1 mã */
    @GetMapping("/accuracy/{symbol}")
    public ResponseEntity<?> accuracy(@PathVariable String symbol) {
        return ResponseEntity.ok(predictionService.getAccuracy(symbol));
    }

    /** Accuracy tổng thể */
    @GetMapping("/accuracy")
    public ResponseEntity<?> overallAccuracy() {
        return ResponseEntity.ok(predictionService.getOverallAccuracy());
    }
}
