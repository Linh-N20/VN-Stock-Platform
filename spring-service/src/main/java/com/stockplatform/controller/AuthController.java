package com.stockplatform.controller;

import com.stockplatform.security.CustomOAuth2User;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    @GetMapping("/login")
    public String loginPage(@RequestParam(required = false) String error, Model model) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.isAuthenticated()
                && auth.getPrincipal() instanceof OAuth2User) {
            return "redirect:/";
        }
        if (error != null) {
            model.addAttribute("error", "Đăng nhập thất bại. Vui lòng thử lại.");
        }
        return "auth/login";
    }

    @GetMapping("/profile")
    public String profile(Authentication authentication, Model model) {
        // Log để debug
        if (authentication == null) {
            log.warn("Profile: authentication is NULL");
            return "redirect:/login";
        }

        log.info("Profile: authenticated={}, principalType={}",
            authentication.isAuthenticated(),
            authentication.getPrincipal().getClass().getName());

        if (!authentication.isAuthenticated()) {
            log.warn("Profile: not authenticated");
            return "redirect:/login";
        }

        Object principal = authentication.getPrincipal();

        if (principal instanceof CustomOAuth2User user) {
            log.info("Profile: CustomOAuth2User found, email={}", user.getEmail());
            model.addAttribute("user",     user.getAppUser());
            model.addAttribute("email",    user.getEmail());
            model.addAttribute("fullName", user.getFullName());
            model.addAttribute("picture",  user.getPicture());
            return "auth/profile";
        }

        // Nếu là OAuth2User thông thường (chưa wrap)
        if (principal instanceof OAuth2User oauth2User) {
            log.warn("Profile: plain OAuth2User (not wrapped), name={}", oauth2User.getName());
            model.addAttribute("fullName", oauth2User.getAttribute("name"));
            model.addAttribute("email",    oauth2User.getAttribute("email"));
            model.addAttribute("picture",  oauth2User.getAttribute("picture"));
            model.addAttribute("user",     null);
            return "auth/profile";
        }

        log.warn("Profile: unknown principal type: {}", principal.getClass().getName());
        return "redirect:/";
    }
}