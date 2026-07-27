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
 * Lưu cổ phiếu yêu thích của từng user.
 * Mỗi user có thể thêm nhiều cổ phiếu vào danh sách yêu thích.
 */
@Entity
@Table(name = "favorite_stocks",
       uniqueConstraints = @UniqueConstraint(columnNames = {"user_email", "symbol"}))
public class FavoriteStock {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_email", nullable = false)
    private String userEmail;

    @Column(nullable = false, length = 20)
    private String symbol;

    @Column(nullable = false)
    private LocalDateTime addedAt = LocalDateTime.now();

    public FavoriteStock() {}

    public FavoriteStock(String userEmail, String symbol) {
        this.userEmail = userEmail;
        this.symbol    = symbol;
        this.addedAt   = LocalDateTime.now();
    }

    public Long          getId()        { return id; }
    public String        getUserEmail() { return userEmail; }
    public String        getSymbol()    { return symbol; }
    public LocalDateTime getAddedAt()   { return addedAt; }

    public void setUserEmail(String v) { this.userEmail = v; }
    public void setSymbol(String v)    { this.symbol = v; }
    public void setAddedAt(LocalDateTime v) { this.addedAt = v; }
}