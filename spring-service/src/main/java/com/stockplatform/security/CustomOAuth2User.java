package com.stockplatform.security;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.oidc.OidcIdToken;
import org.springframework.security.oauth2.core.oidc.OidcUserInfo;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;

import com.stockplatform.entity.AppUser;

/**
 * Implement OidcUser (không phải OAuth2User) vì Google dùng OIDC.
 */
public class CustomOAuth2User implements OidcUser {

    private final OidcUser  oidcUser;
    private final AppUser   appUser;

    public CustomOAuth2User(OidcUser oidcUser, AppUser appUser) {
        this.oidcUser = oidcUser;
        this.appUser  = appUser;
    }

    // ── OidcUser methods ──────────────────────────────────────────────────────
    @Override public OidcIdToken  getIdToken()   { return oidcUser.getIdToken(); }
    @Override public OidcUserInfo getUserInfo()  { return oidcUser.getUserInfo(); }
    @Override public Map<String, Object> getClaims() { return oidcUser.getClaims(); }

    // ── OAuth2User methods ────────────────────────────────────────────────────
    @Override
    public Map<String, Object> getAttributes() { return oidcUser.getAttributes(); }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + appUser.getRole().name()));
    }

    @Override
    public String getName() { return appUser.getEmail(); }

    // ── Tiện ích ──────────────────────────────────────────────────────────────
    public AppUser getAppUser()  { return appUser; }
    public String  getEmail()    { return appUser.getEmail(); }
    public String  getFullName() { return appUser.getName(); }
    public String  getPicture()  { return appUser.getPicture(); }
    public boolean isAdmin()     { return appUser.getRole() == AppUser.Role.ADMIN; }
}