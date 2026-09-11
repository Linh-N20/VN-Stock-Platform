package com.stockplatform.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "stock_signals")
public class StockSignal {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 20)
    private String symbol;

    // TĂNG / GIẢM / GIỮ NGUYÊN
    @Column(nullable = false, length = 20)
    private String signal;

    private Integer score;
    private Double  currentPrice;
    private Double  rsi;
    private Double  macd;
    private Double  macdSignal;
    private Double  ma20;
    private Double  ma50;
    private Double  bbUpper;
    private Double  bbLower;

    @Column(length = 2000)
    private String reasons;

    @Column(nullable = false)
    private LocalDateTime calculatedAt = LocalDateTime.now();

    // ── Getters ──────────────────────────────────────────────────────────────
    public Long          getId()           { return id; }
    public String        getSymbol()       { return symbol; }
    public String        getSignal()       { return signal; }
    public Integer       getScore()        { return score; }
    public Double        getCurrentPrice() { return currentPrice; }
    public Double        getRsi()          { return rsi; }
    public Double        getMacd()         { return macd; }
    public Double        getMacdSignal()   { return macdSignal; }
    public Double        getMa20()         { return ma20; }
    public Double        getMa50()         { return ma50; }
    public Double        getBbUpper()      { return bbUpper; }
    public Double        getBbLower()      { return bbLower; }
    public String        getReasons()      { return reasons; }
    public LocalDateTime getCalculatedAt() { return calculatedAt; }

    // ── Setters ──────────────────────────────────────────────────────────────
    public void setSymbol(String v)           { this.symbol = v; }
    public void setSignal(String v)           { this.signal = v; }
    public void setScore(Integer v)           { this.score = v; }
    public void setCurrentPrice(Double v)     { this.currentPrice = v; }
    public void setRsi(Double v)              { this.rsi = v; }
    public void setMacd(Double v)             { this.macd = v; }
    public void setMacdSignal(Double v)       { this.macdSignal = v; }
    public void setMa20(Double v)             { this.ma20 = v; }
    public void setMa50(Double v)             { this.ma50 = v; }
    public void setBbUpper(Double v)          { this.bbUpper = v; }
    public void setBbLower(Double v)          { this.bbLower = v; }
    public void setReasons(String v)          { this.reasons = v; }
    public void setCalculatedAt(LocalDateTime v) { this.calculatedAt = v; }

    // ── Helper UI ─────────────────────────────────────────────────────────────
    public String getSignalColor() {
        return switch (signal != null ? signal : "") {
            case "TĂNG"       -> "success";
            case "GIẢM"       -> "danger";
            case "GIỮ NGUYÊN" -> "warning";
            default           -> "secondary";
        };
    }

    public String getSignalIcon() {
        return switch (signal != null ? signal : "") {
            case "TĂNG"       -> "bi-graph-up-arrow";
            case "GIẢM"       -> "bi-graph-down-arrow";
            case "GIỮ NGUYÊN" -> "bi-dash-circle";
            default           -> "bi-question-circle";
        };
    }
}