package com.stockplatform.security;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.user.OAuth2User;

import com.stockplatform.entity.AppUser;

/**
 * Wrapper kết hợp OAuth2User (từ Google) + AppUser (từ DB của mình).
 * Spring Security dùng class này để biết user là ai và có quyền gì.
 *
 * Tại sao cần wrap?
 * - OAuth2User chỉ có thông tin từ Google (email, name, picture)
 * - AppUser có thêm role, id, createdAt từ DB của mình
 * - CustomOAuth2User kết hợp cả hai → dùng được ở mọi nơi
 */
public class CustomOAuth2User implements OAuth2User {

    private final OAuth2User  oauth2User;
    private final AppUser     appUser;

    public CustomOAuth2User(OAuth2User oauth2User, AppUser appUser) {
        this.oauth2User = oauth2User;
        this.appUser    = appUser;
    }

    @Override
    public Map<String, Object> getAttributes() {
        return oauth2User.getAttributes();
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        // Chuyển role từ DB thành Spring Security authority
        // ROLE_USER hoặc ROLE_ADMIN
        return List.of(new SimpleGrantedAuthority("ROLE_" + appUser.getRole().name()));
    }

    @Override
    public String getName() {
        return appUser.getEmail();
    }

    // Tiện ích để lấy thông tin user ở controller/template
    public AppUser  getAppUser()  { return appUser; }
    public String   getEmail()    { return appUser.getEmail(); }
    public String   getFullName() { return appUser.getName(); }
    public String   getPicture()  { return appUser.getPicture(); }
    public boolean  isAdmin()     { return appUser.getRole() == AppUser.Role.ADMIN; }
}