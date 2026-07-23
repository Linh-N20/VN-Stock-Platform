package com.stockplatform.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

/**
 * Lưu lịch sử cổ phiếu người dùng đã xem.
 * Mỗi lần user vào trang /stocks/{symbol} → symbol được ghi vào đây.
 * Dashboard đọc bảng này để hiển thị watchlist động.
 */
@Entity
@Table(name = "watched_stocks",
       uniqueConstraints = @UniqueConstraint(columnNames = "symbol"))
public class WatchedStock {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 20)
    private String symbol;

    @Column(nullable = false)
    private LocalDateTime lastViewedAt = LocalDateTime.now();

    @Column(nullable = false)
    private Integer viewCount = 1;

    public WatchedStock() {}

    public WatchedStock(String symbol) {
        this.symbol       = symbol;
        this.lastViewedAt = LocalDateTime.now();
        this.viewCount    = 1;
    }

    public Long          getId()           { return id; }
    public String        getSymbol()       { return symbol; }
    public LocalDateTime getLastViewedAt() { return lastViewedAt; }
    public Integer       getViewCount()    { return viewCount; }

    public void setSymbol(String v)              { this.symbol = v; }
    public void setLastViewedAt(LocalDateTime v) { this.lastViewedAt = v; }
    public void setViewCount(Integer v)          { this.viewCount = v; }
}