package com.stockplatform.security;

import java.time.LocalDateTime;

import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

import com.stockplatform.entity.AppUser;
import com.stockplatform.repository.AppUserRepository;

/**
 * Xử lý sau khi Google xác thực thành công.
 *
 * Luồng hoạt động:
 * 1. User click "Login with Google"
 * 2. Google xác thực → trả về thông tin user (email, name, picture)
 * 3. Class này nhận thông tin đó
 * 4. Tìm user trong DB → nếu chưa có thì tạo mới
 * 5. Cập nhật lastLoginAt
 * 6. Trả về CustomOAuth2User để Spring Security dùng
 */
@Service
public class OAuth2UserService extends DefaultOAuth2UserService {

    private final AppUserRepository userRepository;

    public OAuth2UserService(AppUserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public OAuth2User loadUser(OAuth2UserRequest request) {
        // Lấy thông tin từ Google
        OAuth2User oAuth2User = super.loadUser(request);

        String provider   = request.getClientRegistration().getRegistrationId(); // "google"
        String providerId = oAuth2User.getAttribute("sub");   // Google unique ID
        String email      = oAuth2User.getAttribute("email");
        String name       = oAuth2User.getAttribute("name");
        String picture    = oAuth2User.getAttribute("picture");

        // Tìm hoặc tạo user trong database
        AppUser user = userRepository
            .findByProviderAndProviderId(provider, providerId)
            .orElseGet(() -> {
                // Lần đầu đăng nhập → tạo user mới
                AppUser newUser = new AppUser();
                newUser.setProvider(provider);
                newUser.setProviderId(providerId);
                newUser.setEmail(email);
                newUser.setName(name);
                newUser.setPicture(picture);
                newUser.setRole(AppUser.Role.USER);
                return newUser;
            });

        // Cập nhật thông tin mới nhất từ Google (tên, avatar có thể thay đổi)
        user.setName(name);
        user.setPicture(picture);
        user.setLastLoginAt(LocalDateTime.now());
        userRepository.save(user);

        return new CustomOAuth2User(oAuth2User, user);
    }
}