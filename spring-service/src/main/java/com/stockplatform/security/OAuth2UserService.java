package com.stockplatform.security;

import com.stockplatform.entity.AppUser;
import com.stockplatform.repository.AppUserRepository;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserRequest;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * Google dùng OIDC (OpenID Connect) nên phải implement OidcUserService,
 * không phải DefaultOAuth2UserService.
 */
@Service
public class OAuth2UserService
        extends OidcUserService {

    private final AppUserRepository userRepository;

    public OAuth2UserService(AppUserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public OidcUser loadUser(OidcUserRequest request) {
        OidcUser oidcUser = super.loadUser(request);

        String provider   = request.getClientRegistration().getRegistrationId();
        String providerId = oidcUser.getSubject();
        String email      = oidcUser.getEmail();
        String name       = oidcUser.getFullName();
        String picture    = oidcUser.getPicture();

        AppUser user = userRepository
            .findByProviderAndProviderId(provider, providerId)
            .orElseGet(() -> {
                AppUser newUser = new AppUser();
                newUser.setProvider(provider);
                newUser.setProviderId(providerId);
                newUser.setEmail(email);
                newUser.setName(name);
                newUser.setPicture(picture);
                newUser.setRole(AppUser.Role.USER);
                return newUser;
            });

        user.setName(name);
        user.setPicture(picture);
        user.setLastLoginAt(LocalDateTime.now());
        userRepository.save(user);

        return new CustomOAuth2User(oidcUser, user);
    }
}