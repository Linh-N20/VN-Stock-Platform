package com.stockplatform.entity;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Lưu lịch sử dự đoán Tăng/Giảm/Giữ nguyên cho từng cổ phiếu.
 * Sau khi có kết quả thực tế → cập nhật actualDirection và isCorrect.
 */
@Entity
@Table(name = "prediction_records",
       uniqueConstraints = @UniqueConstraint(columnNames = {"symbol", "for_date"}))
public class PredictionRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 20)
    private String symbol;

    @Column(name = "for_date", nullable = false)
    private LocalDate forDate;          // ngày dự đoán cho (phiên hôm sau)

    @Column(nullable = false, length = 20)
    private String prediction;          // "TĂNG" / "GIẢM" / "GIỮ NGUYÊN"

    @Column(nullable = false)
    private Double confidence;          // 0.0 - 1.0

    @Column(length = 20)
    private String technicalLabel;      // kết quả từng model
    @Column(length = 20)
    private String extendedLabel;
    @Column(length = 20)
    private String mlLabel;

    // Điền sau khi có kết quả thực tế
    @Column(length = 20)
    private String actualDirection;     // "TĂNG" / "GIẢM" / "GIỮ NGUYÊN"

    private Double actualChangePct;     // % thay đổi thực tế

    private Boolean isCorrect;          // dự đoán có đúng không

    @Column(nullable = false)
    private LocalDateTime predictedAt = LocalDateTime.now();

    private LocalDateTime verifiedAt;   // thời điểm đối chiếu kết quả

    public PredictionRecord() {}

    // Getters & Setters
    public Long          getId()               { return id; }
    public String        getSymbol()           { return symbol; }
    public LocalDate     getForDate()          { return forDate; }
    public String        getPrediction()       { return prediction; }
    public Double        getConfidence()       { return confidence; }
    public String        getTechnicalLabel()   { return technicalLabel; }
    public String        getExtendedLabel()    { return extendedLabel; }
    public String        getMlLabel()          { return mlLabel; }
    public String        getActualDirection()  { return actualDirection; }
    public Double        getActualChangePct()  { return actualChangePct; }
    public Boolean       getIsCorrect()        { return isCorrect; }
    public LocalDateTime getPredictedAt()      { return predictedAt; }
    public LocalDateTime getVerifiedAt()       { return verifiedAt; }

    public void setSymbol(String v)            { this.symbol = v; }
    public void setForDate(LocalDate v)        { this.forDate = v; }
    public void setPrediction(String v)        { this.prediction = v; }
    public void setConfidence(Double v)        { this.confidence = v; }
    public void setTechnicalLabel(String v)    { this.technicalLabel = v; }
    public void setExtendedLabel(String v)     { this.extendedLabel = v; }
    public void setMlLabel(String v)           { this.mlLabel = v; }
    public void setActualDirection(String v)   { this.actualDirection = v; }
    public void setActualChangePct(Double v)   { this.actualChangePct = v; }
    public void setIsCorrect(Boolean v)        { this.isCorrect = v; }
    public void setPredictedAt(LocalDateTime v){ this.predictedAt = v; }
    public void setVerifiedAt(LocalDateTime v) { this.verifiedAt = v; }
}
