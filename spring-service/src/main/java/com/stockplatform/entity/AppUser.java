package com.stockplatform.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * Người dùng đăng nhập qua Google OAuth2.
 * Không lưu password — Google xác thực thay cho chúng ta.
 *
 * Tại sao dùng OAuth2 thay vì username/password?
 * - Không phải tự quản lý password → không lo bị đánh cắp hash
 * - Google đã làm 2FA, brute-force protection thay cho mình
 * - Người dùng tin tưởng Google hơn là website mới
 */
@Entity
@Table(name = "app_users")
public class AppUser {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false)
    private String email;

    @Column(nullable = false)
    private String name;

    private String picture;          // avatar từ Google

    @Column(nullable = false)
    private String provider;         // "google"

    @Column(nullable = false)
    private String providerId;       // Google user ID

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role = Role.USER;

    @Column(nullable = false)
    private LocalDateTime createdAt  = LocalDateTime.now();

    private LocalDateTime lastLoginAt;

    public enum Role { USER, ADMIN }

    // ── Getters / Setters ─────────────────────────────────────────────────────
    public Long          getId()           { return id; }
    public String        getEmail()        { return email; }
    public String        getName()         { return name; }
    public String        getPicture()      { return picture; }
    public String        getProvider()     { return provider; }
    public String        getProviderId()   { return providerId; }
    public Role          getRole()         { return role; }
    public LocalDateTime getCreatedAt()    { return createdAt; }
    public LocalDateTime getLastLoginAt()  { return lastLoginAt; }

    public void setEmail(String v)        { this.email = v; }
    public void setName(String v)         { this.name = v; }
    public void setPicture(String v)      { this.picture = v; }
    public void setProvider(String v)     { this.provider = v; }
    public void setProviderId(String v)   { this.providerId = v; }
    public void setRole(Role v)           { this.role = v; }
    public void setCreatedAt(LocalDateTime v) { this.createdAt = v; }
    public void setLastLoginAt(LocalDateTime v) { this.lastLoginAt = v; }
}