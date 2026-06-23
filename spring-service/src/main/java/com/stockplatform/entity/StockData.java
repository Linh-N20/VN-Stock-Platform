package com.stockplatform.entity;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Lưu lịch sử giá OHLCV (Open/High/Low/Close/Volume) mỗi ngày.
 * Đây là bảng dữ liệu chính của toàn bộ hệ thống.
 */
@Entity
@Table(name = "stock_data",
       uniqueConstraints = @UniqueConstraint(columnNames = {"symbol", "date"}))
public class StockData {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 10)
    private String symbol;

    @Column(nullable = false)
    private LocalDate date;

    private Double open;
    private Double high;
    private Double low;
    private Double close;
    private Double volume;

    @Column(nullable = false)
    private LocalDateTime fetchedAt = LocalDateTime.now();

    public StockData() {}

    public StockData(String symbol, LocalDate date,
                     Double open, Double high, Double low,
                     Double close, Double volume) {
        this.symbol    = symbol;
        this.date      = date;
        this.open      = open;
        this.high      = high;
        this.low       = low;
        this.close     = close;
        this.volume    = volume;
        this.fetchedAt = LocalDateTime.now();
    }

    public Long          getId()        { return id; }
    public String        getSymbol()    { return symbol; }
    public LocalDate     getDate()      { return date; }
    public Double        getOpen()      { return open; }
    public Double        getHigh()      { return high; }
    public Double        getLow()       { return low; }
    public Double        getClose()     { return close; }
    public Double        getVolume()    { return volume; }
    public LocalDateTime getFetchedAt() { return fetchedAt; }

    public void setSymbol(String v)    { this.symbol = v; }
    public void setDate(LocalDate v)   { this.date = v; }
    public void setOpen(Double v)      { this.open = v; }
    public void setHigh(Double v)      { this.high = v; }
    public void setLow(Double v)       { this.low = v; }
    public void setClose(Double v)     { this.close = v; }
    public void setVolume(Double v)    { this.volume = v; }
    public void setFetchedAt(LocalDateTime v) { this.fetchedAt = v; }
}
